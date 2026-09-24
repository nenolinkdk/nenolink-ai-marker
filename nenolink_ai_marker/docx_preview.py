"""Lightweight approximate DOCX placement preview; not a Word renderer."""

from dataclasses import dataclass, replace
from pathlib import Path
import textwrap
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from PIL import Image, ImageDraw, ImageFont

from .docx_processor import DocxProcessor, W, _q
from .models import MarkerSettings
from .processor import ImageProcessor


@dataclass(frozen=True, slots=True)
class DocxPreview:
    image: Image.Image


class DocxPreviewRenderer:
    """Draw one representative page and reuse the established overlay compositor."""

    def __init__(self, processor: ImageProcessor | None = None) -> None:
        self.processor = processor or ImageProcessor()
        self._cache_key = None
        self._cache_value = None

    def clear(self) -> None:
        self._cache_key = self._cache_value = None

    def render(
        self, source: Path, badge_path: Path | None, settings: MarkerSettings,
        logo_path: Path | None = None, max_size: tuple[int, int] = (680, 220),
    ) -> DocxPreview:
        source = Path(source)
        key = (source.resolve(), source.stat().st_mtime_ns, max_size)
        if key == self._cache_key and self._cache_value is not None:
            canvas, page_width_pixels = self._cache_value
            canvas = canvas.copy()
        else:
            with ZipFile(source, "r") as archive:
                document = ET.fromstring(archive.read("word/document.xml"))
            section = document.find(f".//{_q(W, 'sectPr')}")
            width_emu, height_emu = DocxProcessor._page_size(section if section is not None else document)
            width = max_size[0]; height = round(width * height_emu / width_emu)
            if height > max_size[1]:
                height = max_size[1]; width = round(height * width_emu / height_emu)
            canvas = Image.new("RGBA", (max(1, width), max(1, height)), "white")
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((0, 0, width - 1, height - 1), outline="#b8b8b8", width=2)
            text = " ".join(node.text.strip() for node in document.findall(f".//{_q(W, 't')}") if node.text and node.text.strip())
            font = ImageFont.load_default(); y = max(14, round(height * .12))
            for line in textwrap.wrap(text, max(25, width // 8))[:9]:
                draw.text((round(width * .10), y), line, fill="#444444", font=font)
                y += 16
                if y > height * .78:
                    break
            page_width_pixels = max(1, round(width_emu / 9525))
            self._cache_key = key; self._cache_value = (canvas.copy(), page_width_pixels)
        scale = canvas.width / page_width_pixels
        preview_settings = replace(
            settings,
            margin=max(0, round(settings.margin * scale)),
            logo_margin=max(0, round(settings.logo_margin * scale)),
        )
        badge = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        if badge_path:
            with Image.open(badge_path) as opened:
                badge = opened.convert("RGBA")
        logo = None
        if preview_settings.logo_enabled and logo_path:
            with Image.open(logo_path) as opened:
                logo = opened.convert("RGBA")
        return DocxPreview(self.processor.compose(canvas, badge, preview_settings, logo))
