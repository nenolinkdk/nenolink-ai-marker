from dataclasses import asdict, dataclass
from typing import Literal

Position = Literal["top-left", "top-right", "bottom-left", "bottom-right"]


@dataclass(slots=True)
class MarkerSettings:
    badge_name: str = ""
    position: Position = "bottom-right"
    size_percent: int = 20
    margin: int = 20
    opacity: int = 100
    language: str = "en"
    badge_source: str = "standard"
    custom_badge_folder: str = ""

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
        return self

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
