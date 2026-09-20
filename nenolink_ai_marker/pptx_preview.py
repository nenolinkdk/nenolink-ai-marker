"""Lightweight placement preview for PPTX slides (not a PowerPoint renderer)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import textwrap
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from PIL import Image, ImageDraw, ImageFont

from .models import MarkerSettings
from .pptx_processor import A, PptxProcessor
from .processor import ImageProcessor


@dataclass(frozen=True, slots=True)
class PptxPreview:
    image: Image.Image
    slide_number: int
    slide_count: int


class PptxPreviewRenderer:
    """Draw a simple slide canvas/text outline, then reuse normal overlay logic."""

    def __init__(self, processor: ImageProcessor | None = None) -> None:
        self.processor = processor or ImageProcessor()
        self._cache_key: tuple[Path, int, int, tuple[int, int]] | None = None
        self._cache_value: tuple[Image.Image, int, int] | None = None

    def clear(self) -> None:
        self._cache_key = self._cache_value = None

    def render(
        self,
        source: Path,
        slide_number: int,
        badge_path: Path,
        settings: MarkerSettings,
        logo_path: Path | None = None,
        max_size: tuple[int, int] = (680, 220),
    ) -> PptxPreview:
        base, count, slide_width_pixels = self._base(source, slide_number, max_size)
        ordinal = min(max(1, slide_number), count)
        scale = base.width / max(1, slide_width_pixels)
        preview_settings = replace(
            settings,
            margin=max(0, round(settings.margin * scale)),
            logo_margin=max(0, round(settings.logo_margin * scale)),
        )
        with Image.open(badge_path) as opened:
            badge = opened.convert("RGBA")
        logo = None
        if preview_settings.logo_enabled and logo_path:
            with Image.open(logo_path) as opened:
                logo = opened.convert("RGBA")
        return PptxPreview(self.processor.compose(base, badge, preview_settings, logo), ordinal, count)

    def _base(self, source: Path, slide_number: int, max_size: tuple[int, int]) -> tuple[Image.Image, int, int]:
        key = (source.resolve(), source.stat().st_mtime_ns, slide_number, max_size)
        if key == self._cache_key and self._cache_value:
            image, count, width = self._cache_value
            return image.copy(), count, width
        with ZipFile(source, "r") as archive:
            presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
            relationships = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
            slides = PptxProcessor._ordered_slides(presentation, relationships)
            if not slides:
                raise ValueError("The presentation has no slides.")
            ordinal = min(max(1, slide_number), len(slides))
            width_emu, height_emu = PptxProcessor._slide_size(presentation)
            width = max_size[0]
            height = max(1, round(width * height_emu / width_emu))
            if height > max_size[1]:
                height = max_size[1]
                width = max(1, round(height * width_emu / height_emu))
            canvas = Image.new("RGBA", (width, height), "white")
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((0, 0, width - 1, height - 1), outline="#b8b8b8", width=2)
            slide = ET.fromstring(archive.read(slides[ordinal - 1]))
            texts = [node.text.strip() for node in slide.findall(f".//{{{A}}}t") if node.text and node.text.strip()]
            font = self._font(max(12, round(height / 18)))
            y = max(12, round(height * .10))
            for text in texts[:8]:
                lines = textwrap.wrap(text, width=max(18, round(width / 13))) or [text]
                draw.multiline_text((round(width * .07), y), "\n".join(lines), fill="#333333", font=font, spacing=4)
                y += max(22, round(height * .10)) * len(lines)
                if y > height * .78:
                    break
        slide_width_pixels = max(1, round(width_emu / 9525))
        self._cache_key = key
        self._cache_value = (canvas.copy(), len(slides), slide_width_pixels)
        return canvas, len(slides), slide_width_pixels

    @staticmethod
    def _font(size: int):
        try:
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            return ImageFont.load_default()
