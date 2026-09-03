"""Read-only inspection of the Nenolink AI Marker metadata schema."""

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError

from .batch import find_ffmpeg, hidden_subprocess_kwargs

INSPECT_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
INSPECT_VIDEO_EXTENSIONS = {".mp4", ".mov"}
INSPECT_EXTENSIONS = INSPECT_IMAGE_EXTENSIONS | INSPECT_VIDEO_EXTENSIONS
NENOLINK_XMP_NAMESPACE = "https://nenolink.com/ns/ai-marker/1.0/"


@dataclass(frozen=True, slots=True)
class InspectionResult:
    path: Path
    media_format: str
    size: int
    found: bool
    software: str | None = None
    ai_label: str | None = None
    marker_version: str | None = None


def human_file_size(size: int) -> str:
    value = float(size)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "bytes":
                return f"{value:.0f} {unit}"
            amount = f"{value:.1f}".rstrip("0").rstrip(".")
            return f"{amount} {unit}"
        value /= 1024
    return f"{size} bytes"


def _format_name(path: Path) -> str:
    return {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WebP", ".mp4": "MP4", ".mov": "MOV"}[path.suffix.lower()]


def _description_values(description: object) -> tuple[str | None, str | None]:
    if not isinstance(description, str) or not description.startswith("Nenolink AI Marker;"):
        return None, None
    label = re.search(r"(?:^|;)\s*AI Label=([^;]+)", description)
    version = re.search(r"(?:^|;)\s*Version=([^;]+)", description)
    return (label.group(1).strip() if label else None, version.group(1).strip() if version else None)


def _xmp_values(raw: object) -> tuple[bool, str | None, str | None, str | None]:
    if not isinstance(raw, (bytes, bytearray, str)):
        return False, None, None, None
    try:
        root = ElementTree.fromstring(raw)
    except (ElementTree.ParseError, ValueError, TypeError):
        return False, None, None, None
    description = root.find(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description")
    if description is None:
        return False, None, None, None
    get = description.attrib.get
    identifier = get(f"{{{NENOLINK_XMP_NAMESPACE}}}Marker")
    return (
        identifier == "1",
        get("{http://ns.adobe.com/xap/1.0/}CreatorTool"),
        get(f"{{{NENOLINK_XMP_NAMESPACE}}}AILabel"),
        get(f"{{{NENOLINK_XMP_NAMESPACE}}}MarkerVersion"),
    )


def _is_recognized(identifier: bool, software: str | None, label: str | None, version: str | None, structured: bool) -> bool:
    return identifier or structured or (software == "Nenolink AI Marker" and bool(label) and bool(version))


def inspect_image(path: Path) -> InspectionResult:
    try:
        with Image.open(path) as image:
            image.load()
            info = dict(image.info)
            exif = image.getexif()
    except (OSError, UnidentifiedImageError, ValueError) as error:
        raise ValueError(f"Could not read image metadata: {error}") from error
    software = info.get("Software") or exif.get(305)
    label = info.get("AI Label")
    version = info.get("Marker Version")
    identifier = str(info.get("NenolinkAIMarker", "")) == "1"
    description = exif.get(270)
    description_label, description_version = _description_values(description)
    structured = bool(description_label or description_version)
    xmp_id, xmp_software, xmp_label, xmp_version = _xmp_values(info.get("xmp"))
    software = software or xmp_software
    label = label or xmp_label or description_label
    version = version or xmp_version or description_version
    found = _is_recognized(identifier or xmp_id, software, label, version, structured)
    return InspectionResult(path, _format_name(path), path.stat().st_size, found, software if found else None, label if found else None, version if found else None)


def _unescape_ffmetadata(value: str) -> str:
    return re.sub(r"\\([\\;=#])", r"\1", value).strip()


def inspect_video(path: Path) -> InspectionResult:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise ValueError("The bundled video component could not be found")
    completed = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-f", "ffmetadata", "-"],
        capture_output=True, text=True, **hidden_subprocess_kwargs(),
    )
    if completed.returncode:
        reason = completed.stderr.strip().splitlines()[-1] if completed.stderr else "invalid or unreadable video"
        raise ValueError(f"Could not read video metadata: {reason}")
    values: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if not line or line.startswith((";", "#")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.casefold()] = _unescape_ffmetadata(value)
    software = values.get("software")
    label = values.get("ai_label")
    version = values.get("marker_version")
    comment_label, comment_version = _description_values(values.get("comment"))
    structured = bool(comment_label or comment_version)
    label = label or comment_label
    version = version or comment_version
    found = _is_recognized(values.get("nenolink_ai_marker") == "1", software, label, version, structured)
    return InspectionResult(path, _format_name(path), path.stat().st_size, found, software if found else None, label if found else None, version if found else None)


def inspect_file(path: Path) -> InspectionResult:
    path = Path(path)
    if path.suffix.lower() not in INSPECT_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {path.suffix or 'no extension'}")
    if not path.is_file():
        raise ValueError("The selected file no longer exists or cannot be read")
    return inspect_image(path) if path.suffix.lower() in INSPECT_IMAGE_EXTENSIONS else inspect_video(path)
