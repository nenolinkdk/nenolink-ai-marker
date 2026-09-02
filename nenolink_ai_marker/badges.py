from pathlib import Path


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

    def find(self, name: str) -> Path | None:
        return next((path for path in self.list_badges() if path.name == name), None)


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
