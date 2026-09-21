"""Lazy single-page PDF placement preview."""

from dataclasses import dataclass, replace
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont

from .models import MarkerSettings
from .pdf_processor import PdfProcessor
from .processor import ImageProcessor


@dataclass(frozen=True,slots=True)
class PdfPreview:
    image: Image.Image
    page_number: int
    page_count: int


class PdfPreviewRenderer:
    def __init__(self,processor=None):self.processor=processor or ImageProcessor()

    def render(self,source: Path,page_number: int,badge_path: Path | None,settings: MarkerSettings,logo_path: Path | None=None,max_size=(680,220)) -> PdfPreview:
        reader=PdfProcessor._reader(source); count=len(reader.pages); ordinal=min(max(1,page_number),count); page=reader.pages[ordinal-1]
        width_points=float(page.mediabox.width); height_points=float(page.mediabox.height); width=max_size[0]; height=round(width*height_points/width_points)
        if height>max_size[1]:height=max_size[1]; width=round(height*width_points/height_points)
        canvas=Image.new("RGBA",(max(1,width),max(1,height)),"white"); draw=ImageDraw.Draw(canvas); draw.rectangle((0,0,width-1,height-1),outline="#b8b8b8",width=2)
        try:text=page.extract_text() or ""
        except Exception:text=""
        font=ImageFont.load_default(); y=12
        for line in textwrap.wrap(" ".join(text.split()),max(20,width//8))[:10]:draw.text((14,y),line,fill="#444444",font=font); y+=16
        scale=width/max(1,width_points/.75); preview_settings=replace(settings,margin=round(settings.margin*scale),logo_margin=round(settings.logo_margin*scale))
        if badge_path:
            with Image.open(badge_path) as opened:badge=opened.convert("RGBA")
        else:badge=Image.new("RGBA",(1,1),(0,0,0,0))
        logo=None
        if preview_settings.logo_enabled and logo_path:
            with Image.open(logo_path) as opened:logo=opened.convert("RGBA")
        return PdfPreview(self.processor.compose(canvas,badge,preview_settings,logo),ordinal,count)
