import json
import os
from pathlib import Path

from .models import MarkerSettings

APP_VENDOR = "Nenolink"
APP_NAME = "AI Marker"


def default_config_path() -> Path:
    roaming = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return roaming / APP_VENDOR / APP_NAME / "settings.json"


def legacy_config_path() -> Path:
    return Path.home() / "AppData" / "Local" / "NenolinkAI Marker" / "config.json"


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()
        self.legacy_path = legacy_config_path() if path is None else None

    def load(self) -> MarkerSettings:
        source = self.path
        if not source.is_file() and self.legacy_path and self.legacy_path.is_file():
            source = self.legacy_path
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
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
