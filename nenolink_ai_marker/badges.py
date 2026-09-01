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

