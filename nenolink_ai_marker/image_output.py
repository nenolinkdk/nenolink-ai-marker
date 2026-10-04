"""Immutable Image output inputs owned by the Image workspace boundary."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True, slots=True)
class ImageProcessingRequest:
    sources: tuple[Path, ...]
    badge: Any
    logo: Path | None
    settings: Any

