import hashlib

from PIL import Image, ImageDraw

from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.preview import ImagePreviewRenderer
from nenolink_ai_marker.processor import ImageProcessor


def preview_media(tmp_path):
    tmp_path.mkdir(parents=True,exist_ok=True)
    source=tmp_path/"photograph.jpg"; badge=tmp_path/"ai-assisted.png"; logo=tmp_path/"company.png"
    Image.new("RGB",(1200,800),"white").save(source,quality=95)
    Image.new("RGBA",(240,100),(220,20,40,255)).save(badge)
    transparent=Image.new("RGBA",(180,180),(0,0,0,0)); ImageDraw.Draw(transparent).ellipse((20,20,160,160),fill=(20,80,220,180)); transparent.save(logo)
    return source,badge,logo


def render(tmp_path, **values):
    source,badge,logo=preview_media(tmp_path)
    settings=MarkerSettings(position="bottom-right",size_percent=20,margin=20,opacity=100,**values)
    image=ImagePreviewRenderer(ImageProcessor()).render(source,badge,settings,logo if settings.logo_enabled else None)
    return source,image


def test_preview_contains_standard_badge_and_optional_logo(tmp_path):
    _,badge_only=render(tmp_path/"badge-only",logo_enabled=False)
    _,both=render(tmp_path/"both",logo_enabled=True,logo_position="top-left",logo_size_percent=18,logo_margin=10)
    assert badge_only.getpixel((700,465))[:3]==(220,20,40)
    assert badge_only.getpixel((20,20))[:3]==(255,255,255)
    assert both.getpixel((45,45))[2]>both.getpixel((45,45))[0]
    assert both.getpixel((700,465))[:3]==(220,20,40)


def test_preview_changes_for_positions_sizes_margins_and_opacity(tmp_path):
    source,badge,logo=preview_media(tmp_path)
    renderer=ImagePreviewRenderer(ImageProcessor())
    baseline=renderer.render(source,badge,MarkerSettings(position="bottom-right",size_percent=20,margin=0,logo_enabled=True,logo_position="top-left",logo_size_percent=15,logo_margin=0),logo)
    changes=(
        MarkerSettings(position="top-right",size_percent=20,margin=0,logo_enabled=True,logo_position="top-left",logo_size_percent=15,logo_margin=0),
        MarkerSettings(position="bottom-right",size_percent=35,margin=0,logo_enabled=True,logo_position="top-left",logo_size_percent=15,logo_margin=0),
        MarkerSettings(position="bottom-right",size_percent=20,margin=80,logo_enabled=True,logo_position="top-left",logo_size_percent=15,logo_margin=0),
        MarkerSettings(position="bottom-right",size_percent=20,margin=0,opacity=35,logo_enabled=True,logo_position="top-left",logo_size_percent=15,logo_margin=0),
        MarkerSettings(position="bottom-right",size_percent=20,margin=0,logo_enabled=True,logo_position="bottom-left",logo_size_percent=15,logo_margin=0),
        MarkerSettings(position="bottom-right",size_percent=20,margin=0,logo_enabled=True,logo_position="top-left",logo_size_percent=35,logo_margin=0),
        MarkerSettings(position="bottom-right",size_percent=20,margin=0,logo_enabled=True,logo_position="top-left",logo_size_percent=15,logo_margin=80),
        MarkerSettings(position="bottom-right",size_percent=20,margin=0,logo_enabled=True,logo_position="top-left",logo_size_percent=15,logo_margin=0,logo_opacity=30),
    )
    assert all(renderer.render(source,badge,settings,logo).tobytes()!=baseline.tobytes() for settings in changes)


def test_same_corner_transparency_and_source_integrity(tmp_path):
    source,badge,logo=preview_media(tmp_path); before=hashlib.sha256(source.read_bytes()).hexdigest()
    image=ImagePreviewRenderer(ImageProcessor()).render(source,badge,MarkerSettings(position="top-left",margin=0,logo_enabled=True,logo_position="top-left",logo_margin=0,logo_opacity=50),logo)
    assert image.size==(720,480)
    assert image.getpixel((1,1))[:3]==(220,20,40)
    assert image.getpixel((45,45))[:3]!=(220,20,40)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    with Image.open(source) as checked:
        assert not any(key in checked.info for key in ("Software","AI Label","Marker Version","NenolinkAIMarker"))


def test_preview_cache_reuses_decoded_source_until_file_changes(tmp_path):
    source,badge,logo=preview_media(tmp_path); renderer=ImagePreviewRenderer(ImageProcessor())
    first=renderer.render(source,badge,MarkerSettings(),None)
    cached=renderer._source_image
    second=renderer.render(source,badge,MarkerSettings(position="top-left"),None)
    assert renderer._source_image is cached
    assert first.tobytes()!=second.tobytes()
