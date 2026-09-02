from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from .models import MarkerSettings
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
    cancelled: bool = False


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
    return shutil.which("ffmpeg")


class BatchProcessor:
    def __init__(self, image_processor: ImageProcessor | None = None) -> None:
        self.image_processor = image_processor or ImageProcessor()

    def process(
        self, scan: FolderScan, badge: Path, settings: MarkerSettings,
        *, cancelled: Callable[[], bool] = lambda: False,
        progress: Callable[[Path, int, int, BatchResult], None] = lambda *_: None,
    ) -> BatchResult:
        files = scan.selected(settings)
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
                    image = self.image_processor.process(source, badge, settings)
                    self.image_processor.save(image, target)
                    result.successful += 1
                else:
                    self.process_video(source, badge, target, settings)
                    result.successful += 1
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                result.errors.append(f"{source.name}: {error}")
            progress(source, index, len(files), result)
        return result

    @staticmethod
    def process_video(source: Path, badge: Path, target: Path, settings: MarkerSettings) -> None:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise ValueError("FFmpeg was not found. Install FFmpeg and add it to PATH to process videos.")
        positions = {
            "top-left": f"{settings.margin}:{settings.margin}",
            "top-right": f"W-w-{settings.margin}:{settings.margin}",
            "bottom-left": f"{settings.margin}:H-h-{settings.margin}",
            "bottom-right": f"W-w-{settings.margin}:H-h-{settings.margin}",
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        width = max(1, settings.size_percent) / 100
        alpha = settings.opacity / 100
        filter_graph = (
            f"[1:v][0:v]scale2ref=w=main_w*{width}:h=ow/mdar[scaled][video];"
            f"[scaled]format=rgba,colorchannelmixer=aa={alpha}[badge];"
            f"[video][badge]overlay={positions[settings.position]}:shortest=1[outv]"
        )
        completed = subprocess.run(
            [ffmpeg, "-y", "-i", str(source), "-loop", "1", "-i", str(badge), "-filter_complex", filter_graph,
             "-map", "[outv]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy", str(target)],
            capture_output=True, text=True,
        )
        if completed.returncode:
            raise ValueError(completed.stderr.strip().splitlines()[-1] if completed.stderr else "FFmpeg failed")
