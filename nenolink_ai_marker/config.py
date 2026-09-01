import json
from pathlib import Path

from .models import MarkerSettings

APP_DIR_NAME = "NenolinkAI Marker"


def default_config_path() -> Path:
    return Path.home() / "AppData" / "Local" / APP_DIR_NAME / "config.json"


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()

    def load(self) -> MarkerSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = MarkerSettings.__dataclass_fields__.keys()
            return MarkerSettings(**{key: data[key] for key in allowed if key in data}).validated()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return MarkerSettings()

    def save(self, settings: MarkerSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(settings.validated().to_dict(), indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)

