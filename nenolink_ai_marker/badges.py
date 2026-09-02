from dataclasses import dataclass
import json
from pathlib import Path


EXPECTED_STANDARD_BADGES = (
    "ai-assisted.png", "ai-generated.png", "ai-modified.png", "human-reviewed.png",
    "ai-image.png", "ai-video.png", "ai-audio.png", "ai-software.png",
    "ai-translation.png", "ai-localization.png",
)


@dataclass(frozen=True, slots=True)
class BadgeInfo:
    id: str
    filename: str
    display_name: str
    category: str
    description: str


class BadgeRepository:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def list_badges(self) -> list[Path]:
        if not self.directory.is_dir():
            return []
        return sorted(
            (path for path in self.directory.iterdir() if path.is_file() and path.suffix.lower() == ".png"),
            key=lambda path: path.name.casefold(),
        )

    def display_badges(self) -> list[Path]:
        """Return standard badges in the documented UI order, then any extras."""
        badges = self.list_badges()
        rank = {name: index for index, name in enumerate(EXPECTED_STANDARD_BADGES)}
        return sorted(badges, key=lambda path: (rank.get(path.name, len(rank)), path.name.casefold()))

    def display_name(self, name: str) -> str:
        info = self.metadata(name)
        return info.display_name if info else Path(name).stem.replace("-", " ").title()

    def find(self, name: str) -> Path | None:
        return next((path for path in self.list_badges() if path.name == name), None)

    def metadata(self, name: str) -> BadgeInfo | None:
        metadata_path = self.directory / "badges.json"
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            entries = payload.get("badges", payload) if isinstance(payload, dict) else payload
            for item in entries:
                if item.get("filename") == name:
                    return BadgeInfo(
                        str(item["id"]), name, str(item["display_name"]),
                        str(item["category"]), str(item["description"]),
                    )
        except (OSError, ValueError, TypeError, KeyError):
            return None
        return None


class BadgeSourceManager:
    def __init__(self, standard_directory: Path) -> None:
        self.standard_directory = standard_directory
        self.source = "standard"
        self.custom_directory: Path | None = None
        self.fallback_reason = ""

    def configure(self, source: str, custom_folder: str = "") -> Path:
        self.source = source if source in {"standard", "custom"} else "standard"
        self.custom_directory = Path(custom_folder).expanduser() if custom_folder else None
        self.fallback_reason = ""
        if self.source == "custom":
            if self.custom_directory and self.custom_directory.is_dir():
                return self.custom_directory.resolve()
            self.fallback_reason = str(self.custom_directory or custom_folder)
        return self.standard_directory

    def repository(self, source: str, custom_folder: str = "") -> BadgeRepository:
        return BadgeRepository(self.configure(source, custom_folder))
