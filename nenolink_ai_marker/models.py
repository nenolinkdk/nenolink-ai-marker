from dataclasses import asdict, dataclass
from typing import Literal
import re

Position = Literal["top-left", "top-right", "bottom-left", "bottom-right"]


def validated_filename_suffix(value: object) -> str:
    suffix = re.sub(r'[<>:"/\\|?*]', "", str(value or "").strip()).rstrip(". ")
    return suffix if suffix else "_ai"


@dataclass(slots=True)
class MarkerSettings:
    badge_name: str = "ai-assisted.png"
    position: Position = "bottom-right"
    size_percent: int = 20
    margin: int = 20
    opacity: int = 100
    language: str = "en"
    badge_source: str = "standard"
    custom_badge_folder: str = ""
    input_folder: str = ""
    output_preference: str = "subfolder"
    output_folder: str = ""
    output_subfolder: str = "AI-marked"
    include_subfolders: bool = False
    preserve_folder_structure: bool = True
    process_images: bool = True
    process_videos: bool = False
    skip_processed: bool = True
    video_mode: str = "overlay"
    batch_filename_suffix: str = "_ai"

    def validated(self) -> "MarkerSettings":
        positions = {"top-left", "top-right", "bottom-left", "bottom-right"}
        if self.position not in positions:
            self.position = "bottom-right"
        self.size_percent = min(100, max(1, int(self.size_percent)))
        self.margin = min(2000, max(0, int(self.margin)))
        self.opacity = min(100, max(0, int(self.opacity)))
        if self.badge_source not in {"standard", "custom"}:
            self.badge_source = "standard"
        self.language = str(self.language or "en")
        self.custom_badge_folder = str(self.custom_badge_folder or "")
        self.input_folder = str(self.input_folder or "")
        self.output_preference = self.output_preference if self.output_preference in {"subfolder", "separate"} else "subfolder"
        self.output_folder = str(self.output_folder or "")
        self.output_subfolder = str(self.output_subfolder or "AI-marked").strip() or "AI-marked"
        self.include_subfolders = bool(self.include_subfolders)
        self.preserve_folder_structure = bool(self.preserve_folder_structure)
        self.process_images = bool(self.process_images)
        self.process_videos = bool(self.process_videos)
        self.skip_processed = bool(self.skip_processed)
        self.video_mode = str(self.video_mode or "overlay")
        self.batch_filename_suffix = validated_filename_suffix(self.batch_filename_suffix)
        return self

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
