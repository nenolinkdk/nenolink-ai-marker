from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageChops

from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.pptx_preview import PptxPreviewRenderer
from test_pptx_processor import _create_pptx, _write_overlay


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preview_renders_badge_logo_and_preserves_source(tmp_path):
    source=tmp_path/"slides.pptx"; _create_pptx(source,3); before=_hash(source)
    badge=tmp_path/"badge.png"; logo=tmp_path/"logo.png"
    _write_overlay(badge,(0,150,70,255),(160,50)); _write_overlay(logo,(210,30,30,180),(80,80))
    settings=MarkerSettings(position="bottom-right",size_percent=22,margin=20,opacity=70,logo_enabled=True,logo_path=str(logo),logo_position="top-left",logo_size_percent=14,logo_margin=12,logo_opacity=60)
    result=PptxPreviewRenderer().render(source,2,badge,settings,logo)
    assert (result.slide_number,result.slide_count)==(2,3)
    assert result.image.size[0]>result.image.size[1]
    assert result.image.getpixel((20,20)) != (255,255,255,255)
    assert result.image.getpixel((result.image.width-25,result.image.height-20)) != (255,255,255,255)
    assert _hash(source)==before


def test_preview_updates_for_position_size_and_slide_navigation(tmp_path):
    source=tmp_path/"slides.pptx"; _create_pptx(source,4)
    badge=tmp_path/"badge.png"; _write_overlay(badge,(0,150,70,255),(160,50))
    renderer=PptxPreviewRenderer()
    first=renderer.render(source,1,badge,MarkerSettings(position="top-left",size_percent=10)).image
    changed=renderer.render(source,4,badge,MarkerSettings(position="bottom-right",size_percent=30)).image
    assert ImageChops.difference(first.convert("RGB"),changed.convert("RGB")).getbbox() is not None
    assert renderer.render(source,99,badge,MarkerSettings()).slide_number==4


def test_preview_without_logo_has_no_logo_overlay(tmp_path):
    source=tmp_path/"slides.pptx"; _create_pptx(source,1)
    badge=tmp_path/"badge.png"; logo=tmp_path/"logo.png"
    _write_overlay(badge,(0,150,70,255),(160,50)); _write_overlay(logo,(210,30,30,255),(80,80))
    renderer=PptxPreviewRenderer(); settings=MarkerSettings(logo_enabled=False,logo_position="top-left")
    without=renderer.render(source,1,badge,settings,logo).image
    settings.logo_enabled=True
    with_logo=renderer.render(source,1,badge,settings,logo).image
    assert ImageChops.difference(without.convert("RGB"),with_logo.convert("RGB")).getbbox() is not None
