"""Lightweight approximate DOCX placement preview; not a Word renderer."""

from dataclasses import dataclass
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
            canvas = self._cache_value.copy()
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
            self._cache_key = key; self._cache_value = canvas.copy()
        badge = None
        if badge_path:
            with Image.open(badge_path) as opened:
                badge = opened.convert("RGBA")
        logo = None
        if settings.logo_enabled and logo_path:
            with Image.open(logo_path) as opened:
                logo = opened.convert("RGBA")
        result = canvas.convert("RGBA")
        if badge is not None:
            self._footer_picture(result, badge, settings.position, settings.size_percent, settings.opacity)
        if logo is not None:
            self._footer_picture(result, logo, settings.logo_position, settings.logo_size_percent, settings.logo_opacity)
        return DocxPreview(result)

    @staticmethod
    def _footer_picture(
        page: Image.Image, picture: Image.Image, position: str,
        size_percent: int, opacity: int,
    ) -> None:
        width = max(1, round(page.width * size_percent / 100))
        height = max(1, round(picture.height * width / max(1, picture.width)))
        picture = picture.resize((width, height), Image.Resampling.LANCZOS)
        if opacity < 100:
            alpha = picture.getchannel("A").point(lambda value: round(value * opacity / 100))
            picture.putalpha(alpha)
        inset = max(4, round(page.width * .04)); y = max(0, page.height - height - inset)
        if position == "center":
            x = max(0, (page.width - width) // 2)
        elif position.endswith("left"):
            x = inset
        else:
            x = max(0, page.width - width - inset)
        page.alpha_composite(picture, (x, y))
