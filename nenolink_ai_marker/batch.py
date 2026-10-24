from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess
import os
import sys
import re
import time
from typing import Callable
from PIL import Image
from io import BytesIO

from .models import MarkerSettings
from .metadata import MarkerMetadata, marker_metadata
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
RECOMMENDED_IMAGE_BYTES = 50 * 1024 * 1024
RECOMMENDED_VIDEO_BYTES = 2 * 1024 * 1024 * 1024

def is_above_recommended_size(path: Path) -> bool:
    limit = RECOMMENDED_IMAGE_BYTES if path.suffix.lower() in SUPPORTED_EXTENSIONS else RECOMMENDED_VIDEO_BYTES
    try:return path.stat().st_size > limit
    except OSError:return False


@dataclass(slots=True)
class FolderScan:
    root: Path
    images: list[Path] = field(default_factory=list)
    videos: list[Path] = field(default_factory=list)
    unsupported: list[Path] = field(default_factory=list)

    def selected(self, settings: MarkerSettings) -> list[Path]:
        return (self.images if settings.process_images else []) + (self.videos if settings.process_videos else [])

    @property
    def oversized(self) -> list[Path]: return [p for p in self.images+self.videos if is_above_recommended_size(p)]


@dataclass(slots=True)
class BatchResult:
    successful: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    metadata_warnings: list[str] = field(default_factory=list)
    cancelled: bool = False


@dataclass(frozen=True, slots=True)
class VideoProcessReceipt:
    """Observable result for one FFmpeg encode attempt."""
    command: tuple[str, ...]
    pid: int
    returncode: int
    stderr: str
    elapsed_seconds: float


def run_ffmpeg_with_receipt(command: list[str]) -> VideoProcessReceipt:
    started = time.perf_counter()
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, **hidden_subprocess_kwargs(),
    )
    _stdout, stderr = process.communicate()
    return VideoProcessReceipt(
        tuple(str(part) for part in command), int(process.pid),
        int(process.returncode), stderr or "", time.perf_counter() - started,
    )


def scan_folder(root: Path, recursive: bool = False) -> FolderScan:
    result = FolderScan(root)
    if not root.is_dir():
        return result
    entries = root.rglob("*") if recursive else root.glob("*")
    for path in sorted((p for p in entries if p.is_file()), key=lambda p: str(p).casefold()):
        suffix = path.suffix.lower()
        if suffix in SUPPORTED_EXTENSIONS:
            result.images.append(path)
        elif suffix in VIDEO_EXTENSIONS:
            result.videos.append(path)
        else:
            result.unsupported.append(path)
    return result


def destination_root(settings: MarkerSettings, input_root: Path) -> Path:
    if settings.output_preference == "separate":
        return Path(settings.output_folder).expanduser()
    return input_root / settings.output_subfolder


def destination_for(source: Path, input_root: Path, output_root: Path, preserve: bool, filename_suffix: str = "_ai") -> Path:
    relative_parent = source.relative_to(input_root).parent if preserve else Path()
    return output_root / relative_parent / f"{source.stem}{filename_suffix}{source.suffix}"


def appears_processed(path: Path, filename_suffix: str = "_ai") -> bool:
    suffix = filename_suffix.casefold()
    stem = path.stem.casefold()
    return stem.endswith(suffix) or f"{suffix}_" in stem


def find_ffmpeg() -> str | None:
    roots=[]
    if getattr(sys,"frozen",False):roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(__file__).resolve().parents[1])
    for root in roots:
        for candidate in (root/"ffmpeg.exe",root/"tools"/"ffmpeg"/"ffmpeg.exe"):
            if candidate.is_file():return str(candidate)
    configured=os.environ.get("NENOLINK_FFMPEG_PATH","").strip()
    if configured and Path(configured).is_file():return configured
    return shutil.which("ffmpeg")


def hidden_subprocess_kwargs(platform: str | None = None) -> dict[str, object]:
    """Prevent console flashes while retaining captured FFmpeg diagnostics."""
    if (platform or os.name) != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": startupinfo}


def video_duration_seconds(ffmpeg: str, source: Path) -> float:
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(source)], capture_output=True, text=True,
        **hidden_subprocess_kwargs(),
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr)
    if not match:
        raise ValueError("FFmpeg could not determine the video duration")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def extract_video_frame(ffmpeg: str, source: Path, timestamp: float = 1.0) -> Image.Image:
    """Extract one representative frame without creating a video-side state owner."""
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", str(max(0.0, timestamp)),
         "-i", str(source), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, **hidden_subprocess_kwargs(),
    )
    if result.returncode != 0 or not result.stdout:
        # Very short videos may not have a frame at t=1; retry at the beginning.
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, **hidden_subprocess_kwargs(),
        )
    if result.returncode != 0 or not result.stdout:
        raise ValueError("FFmpeg could not extract a preview frame")
    with Image.open(BytesIO(result.stdout)) as opened:
        return opened.convert("RGBA")


def normalize_video_timing_mode(mode: str) -> str:
    """Map independent Video badge/logo labels to the shared timing model."""
    return {
        "front": "beginning", "beginning": "beginning",
        "entire": "permanent", "permanent": "permanent",
        "back": "end", "end": "end",
    }.get(str(mode).lower(), str(mode).lower())


def video_overlay_visible_at(mode: str, requested: int, actual: float, timestamp: float) -> bool:
    """Whether an overlay is present at a timestamp under the Save semantics."""
    normalized = normalize_video_timing_mode(mode)
    if normalized == "permanent":
        return True
    duration = min(max(1, int(requested)), max(0.0, float(actual)))
    if normalized == "beginning":
        return 0 <= timestamp <= duration
    if normalized == "end":
        return max(0.0, actual - duration) <= timestamp <= actual
    raise ValueError(f"Unsupported video overlay timing mode: {mode}")


def video_enable_expression(mode: str, requested: int, actual: float) -> str:
    mode = normalize_video_timing_mode(mode)
    duration = min(max(1, requested), actual)
    if mode == "beginning":
        return f":enable='between(t\\,0\\,{duration:g})'"
    if mode == "end":
        return f":enable='gte(t\\,{max(0, actual-duration):g})'"
    return ""


class BatchProcessor:
    def __init__(self, image_processor: ImageProcessor | None = None) -> None:
        self.image_processor = image_processor or ImageProcessor()

    def process(
        self, scan: FolderScan, badge: Path, settings: MarkerSettings,
        *, cancelled: Callable[[], bool] = lambda: False,
        progress: Callable[[Path, int, int, BatchResult], None] = lambda *_: None,
    ) -> BatchResult:
        files = scan.selected(settings)
        metadata = marker_metadata(badge.name)
        output_root = destination_root(settings, scan.root)
        result = BatchResult()
        for index, source in enumerate(files, 1):
            if cancelled():
                result.cancelled = True
                break
            target = destination_for(source, scan.root, output_root, settings.preserve_folder_structure, settings.batch_filename_suffix)
            try:
                if (settings.skip_processed and appears_processed(source, settings.batch_filename_suffix)) or target.exists():
                    result.skipped += 1
                elif source.suffix.lower() in SUPPORTED_EXTENSIONS:
                    logo = Path(settings.logo_path) if settings.logo_enabled and settings.logo_path else None
                    image = self.image_processor.process(source, badge, settings, logo)
                    if not self.image_processor.save(image, target, metadata):
                        result.metadata_warnings.append(source.name)
                    result.successful += 1
                else:
                    if not self.process_video(source, badge, target, settings, metadata):
                        result.metadata_warnings.append(source.name)
                    result.successful += 1
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                result.errors.append(f"{source.name}: {error}")
            progress(source, index, len(files), result)
        return result

    @staticmethod
    def process_video(
        source: Path, badge: Path | None, target: Path, settings: MarkerSettings,
        metadata: MarkerMetadata | None = None, logo: Path | None = None,
        *, on_process: Callable[[VideoProcessReceipt], None] | None = None,
    ) -> bool:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise ValueError("Video processing is unavailable because the required video component could not be found. Reinstall or repair Nenolink AI Marker.")
        def position(name: str, margin: int) -> str:
            return {
                "top-left": f"{margin}:{margin}",
                "top-right": f"W-w-{margin}:{margin}",
                "bottom-left": f"{margin}:H-h-{margin}",
                "bottom-right": f"W-w-{margin}:H-h-{margin}",
                "center": "(W-w)/2:(H-h)/2",
            }[name]
        target.parent.mkdir(parents=True, exist_ok=True)
        overlay = badge or logo
        if overlay is None:
            raise ValueError("At least one overlay is required")
        duration_seconds = None
        def timing(mode: str) -> str:
            nonlocal duration_seconds
            normalized = normalize_video_timing_mode(mode)
            return "" if normalized == "permanent" else video_enable_expression(normalized, settings.video_duration, duration_seconds)
        inputs = [badge, logo] if badge and logo else [overlay]
        # Resolve dimensions from a decoded source frame once. Chaining
        # scale2ref against the already-composited stream can deadlock when
        # two still-image overlays are connected to a looping video graph.
        source_frame = extract_video_frame(ffmpeg, source, timestamp=0.0)
        source_width = source_frame.width
        parts = []
        current = "[0:v]"
        for index, item in enumerate(inputs, start=1):
            is_badge = item is badge
            width = max(1, settings.size_percent if is_badge else settings.logo_size_percent) / 100
            alpha = (settings.opacity if is_badge else settings.logo_opacity) / 100
            overlay_position = position(
                settings.position if is_badge else "top-left",
                settings.margin if is_badge else settings.logo_margin,
            )
            mode = settings.video_mode if is_badge else settings.logo_mode
            if normalize_video_timing_mode(mode) != "permanent" and duration_seconds is None:
                duration_seconds = video_duration_seconds(ffmpeg, source)
            label = f"ov{index}"
            with Image.open(item) as image:
                image_width, image_height = image.size
            rendered_width = max(1, round(source_width * width))
            rendered_height = max(1, round(rendered_width * image_height / max(1, image_width)))
            parts.append(f"[{index}:v]scale={rendered_width}:{rendered_height},format=rgba,colorchannelmixer=aa={alpha}[{label}];{current}[{label}]overlay={overlay_position}:shortest=1{timing(mode)}[{label}out]")
            current = f"[{label}out]"
        filter_graph = ";".join(parts)
        metadata = metadata or marker_metadata(overlay.name)
        base_command = [
            ffmpeg, "-y", "-i", str(source),
            *sum((["-loop", "1", "-i", str(item)] for item in inputs), []),
            "-filter_complex", filter_graph, "-map", current, "-map", "0:a?",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy",
        ]
        metadata_options = [
            "-metadata", f"software={metadata.software}",
            "-metadata", f"ai_label={metadata.ai_label}",
            "-metadata", f"marker_version={metadata.marker_version}",
            "-metadata", f"nenolink_ai_marker={metadata.identifier}",
            "-metadata", f"comment={metadata.description}",
        ]
        if target.suffix.lower() in {".mp4", ".mov"}:
            metadata_options += ["-movflags", "use_metadata_tags"]
        def run(command: list[str]) -> VideoProcessReceipt:
            receipt = run_ffmpeg_with_receipt(command)
            if on_process is not None:
                on_process(receipt)
            return receipt

        completed = run(base_command + metadata_options + [str(target)])
        if completed.returncode:
            retry = run(base_command + [str(target)])
            if not retry.returncode:
                return False
            completed = retry
        if completed.returncode:
            raise ValueError(completed.stderr.strip().splitlines()[-1] if completed.stderr else "FFmpeg failed")
        return True
