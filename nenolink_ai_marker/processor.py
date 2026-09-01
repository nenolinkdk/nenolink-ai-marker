from pathlib import Path
from typing import Protocol

from PIL import Image

from .models import MarkerSettings

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class MediaProcessor(Protocol):
    """Extension point for image processing now and video processing in v0.2."""

    def supports(self, path: Path) -> bool: ...

    def process(self, source: Path, overlay: Path, settings: MarkerSettings) -> Image.Image: ...


class ImageProcessor:
    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in SUPPORTED_EXTENSIONS

    @staticmethod
    def _position(
        image_size: tuple[int, int], badge_size: tuple[int, int], position: str, margin: int
    ) -> tuple[int, int]:
        image_width, image_height = image_size
        badge_width, badge_height = badge_size
        left = margin
        right = max(0, image_width - badge_width - margin)
        top = margin
        bottom = max(0, image_height - badge_height - margin)
        positions = {
            "top-left": (left, top),
            "top-right": (right, top),
            "bottom-left": (left, bottom),
            "bottom-right": (right, bottom),
        }
        return positions[settings_position(position)]

    def process(self, source: Path, overlay: Path, settings: MarkerSettings) -> Image.Image:
        settings.validated()
        if not self.supports(source):
            raise ValueError(f"Unsupported image type: {source.suffix or 'no extension'}")
        try:
            with Image.open(source) as opened:
                base = opened.convert("RGBA")
            with Image.open(overlay) as opened_badge:
                badge = opened_badge.convert("RGBA")
        except (OSError, Image.UnidentifiedImageError) as error:
            raise ValueError(f"Could not open image: {error}") from error

        effective_margin = min(settings.margin, (base.width - 1) // 2, (base.height - 1) // 2)
        available_width = max(1, base.width - (2 * effective_margin))
        available_height = max(1, base.height - (2 * effective_margin))
        target_width = min(available_width, max(1, round(base.width * settings.size_percent / 100)))
        target_height = max(1, round(badge.height * target_width / badge.width))
        if target_height > available_height:
            scale = available_height / target_height
            target_width = max(1, round(target_width * scale))
            target_height = available_height
        badge = badge.resize((target_width, target_height), Image.Resampling.LANCZOS)

        if settings.opacity < 100:
            alpha = badge.getchannel("A").point(lambda value: round(value * settings.opacity / 100))
            badge.putalpha(alpha)

        result = base.copy()
        result.alpha_composite(
            badge, self._position(result.size, badge.size, settings.position, effective_margin)
        )
        return result

    def save(self, image: Image.Image, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        suffix = destination.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            image.convert("RGB").save(destination, format="JPEG", quality=95)
        elif suffix == ".png":
            image.save(destination, format="PNG")
        elif suffix == ".webp":
            image.save(destination, format="WEBP", quality=95)
        else:
            raise ValueError(f"Unsupported output type: {suffix}")


def settings_position(position: str) -> str:
    return position if position in {"top-left", "top-right", "bottom-left", "bottom-right"} else "bottom-right"


def output_path(source: Path, output_directory: Path | None = None) -> Path:
    directory = output_directory or source.parent
    candidate = directory / f"{source.stem}_ai{source.suffix}"
    counter = 2
    while candidate.exists() or candidate.resolve() == source.resolve():
        candidate = directory / f"{source.stem}_ai_{counter}{source.suffix}"
        counter += 1
    return candidate
