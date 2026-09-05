from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image

from .models import MarkerSettings
from .processor import ImageProcessor


class ImagePreviewRenderer:
    """Create live, scaled image previews while caching the decoded source image."""

    def __init__(self, processor: ImageProcessor, maximum_size: tuple[int, int] = (720, 600)) -> None:
        self.processor = processor
        self.maximum_size = maximum_size
        self._source_key: tuple[Path, int, int] | None = None
        self._source_image: Image.Image | None = None
        self._original_size: tuple[int, int] | None = None

    def clear(self) -> None:
        self._source_key = None
        self._source_image = None
        self._original_size = None

    def _source(self, path: Path) -> Image.Image:
        stat = path.stat()
        key = (path.resolve(), stat.st_mtime_ns, stat.st_size)
        if key != self._source_key or self._source_image is None:
            with Image.open(path) as opened:
                source = opened.convert("RGBA")
            self._original_size = source.size
            source.thumbnail(self.maximum_size, Image.Resampling.LANCZOS)
            self._source_key = key
            self._source_image = source.copy()
        return self._source_image.copy()

    @staticmethod
    def _open_overlay(path: Path) -> Image.Image:
        with Image.open(path) as opened:
            return opened.convert("RGBA")

    def render(self, source: Path, badge: Path, settings: MarkerSettings, logo: Path | None = None) -> Image.Image:
        preview_source = self._source(source)
        original_size = self._original_size or preview_source.size
        scale = min(preview_source.width / max(1, original_size[0]), preview_source.height / max(1, original_size[1]))
        preview_settings = replace(
            settings,
            margin=round(settings.margin * scale),
            logo_margin=round(settings.logo_margin * scale),
        ).validated()
        badge_image = self._open_overlay(badge)
        logo_image = self._open_overlay(logo) if preview_settings.logo_enabled and logo else None
        return self.processor.compose(preview_source, badge_image, preview_settings, logo_image)
