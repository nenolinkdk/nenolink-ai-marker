import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from PIL import Image

from nenolink_ai_marker.batch import BatchProcessor, scan_folder
from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.config import ConfigStore
from nenolink_ai_marker.inspection import inspect_file
from nenolink_ai_marker.metadata import marker_metadata
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.processor import ImageProcessor


def media(tmp_path):
    source=tmp_path/"photo.png"; badge=tmp_path/"ai-assisted.png"; logo=tmp_path/"company.png"
    Image.new("RGB",(200,120),"white").save(source)
    Image.new("RGBA",(60,30),(255,0,0,255)).save(badge)
    transparent=Image.new("RGBA",(40,40),(0,0,0,0)); transparent.paste((0,0,255,180),(5,5,35,35)); transparent.save(logo)
    return source,badge,logo


def test_logo_disabled_preserves_existing_processing(tmp_path):
    source,badge,logo=media(tmp_path); processor=ImageProcessor(); settings=MarkerSettings(logo_enabled=False)
    assert processor.process(source,badge,settings).tobytes()==processor.process(source,badge,settings,logo).tobytes()


def test_transparent_logo_and_badge_are_visible_in_different_corners(tmp_path):
    source,badge,logo=media(tmp_path)
    result=ImageProcessor().process(source,badge,MarkerSettings(position="bottom-right",size_percent=20,margin=0,logo_enabled=True,logo_position="top-left",logo_size_percent=20,logo_margin=0),logo)
    assert result.getpixel((198,118))[:3]==(255,0,0)
    assert result.getpixel((10,10))[2]>result.getpixel((10,10))[0]
    assert result.getpixel((1,1))[:3]==(255,255,255)


def test_logo_same_corner_large_logo_and_settings_do_not_crash(tmp_path):
    source,badge,logo=media(tmp_path)
    settings=MarkerSettings(position="top-left",logo_enabled=True,logo_position="top-left",logo_size_percent=100,logo_margin=2000,logo_opacity=50)
    result=ImageProcessor().process(source,badge,settings,logo)
    assert result.size==(200,120)


def test_logo_size_margin_and_opacity_change_output(tmp_path):
    source,badge,logo=media(tmp_path); processor=ImageProcessor()
    compact=processor.process(source,badge,MarkerSettings(logo_enabled=True,logo_position="top-left",logo_size_percent=10,logo_margin=0,logo_opacity=100),logo)
    adjusted=processor.process(source,badge,MarkerSettings(logo_enabled=True,logo_position="top-left",logo_size_percent=40,logo_margin=20,logo_opacity=30),logo)
    assert compact.tobytes()!=adjusted.tobytes()


def test_logo_output_keeps_ai_metadata_without_logo_path_and_source_sha(tmp_path):
    source,badge,logo=media(tmp_path); before=hashlib.sha256(source.read_bytes()).hexdigest(); target=tmp_path/"photo_ai.png"
    image=ImageProcessor().process(source,badge,MarkerSettings(logo_enabled=True,logo_path=str(logo)),logo)
    assert ImageProcessor().save(image,target,marker_metadata(badge.name,"AI Assisted"))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    raw=target.read_bytes(); assert str(logo).encode() not in raw
    inspected=inspect_file(target); assert inspected.found and inspected.ai_label=="AI Assisted"


def test_batch_two_images_with_logo_and_disabled_regression(tmp_path):
    root=tmp_path/"input"; root.mkdir(); badge=tmp_path/"ai-assisted.png"; logo=tmp_path/"logo.webp"
    Image.new("RGBA",(50,25),"red").save(badge); Image.new("RGBA",(30,20),(0,0,255,180)).save(logo,"WEBP",lossless=True)
    for name in ("one.png","two.jpg"):Image.new("RGB",(100,80),"white").save(root/name)
    enabled=MarkerSettings(logo_enabled=True,logo_path=str(logo),logo_position="top-left",logo_margin=0)
    result=BatchProcessor().process(scan_folder(root),badge,enabled); assert result.successful==2
    disabled_root=tmp_path/"plain"; disabled_root.mkdir(); Image.new("RGB",(100,80),"white").save(disabled_root/"one.png")
    assert BatchProcessor().process(scan_folder(disabled_root),badge,MarkerSettings(logo_enabled=False,logo_path=str(logo))).successful==1


def test_logo_preferences_round_trip_and_safe_defaults(tmp_path):
    store=ConfigStore(tmp_path/"settings.json"); logo=tmp_path/"logo.jpg"
    settings=MarkerSettings(logo_enabled=True,logo_path=str(logo),logo_position="bottom-left",logo_size_percent=32,logo_margin=17,logo_opacity=61)
    store.save(settings); restored=store.load()
    assert (restored.logo_enabled,restored.logo_path,restored.logo_position,restored.logo_size_percent,restored.logo_margin,restored.logo_opacity)==(True,str(logo),"bottom-left",32,17,61)
    defaults=MarkerSettings(); assert not defaults.logo_enabled and defaults.logo_position=="top-left" and defaults.logo_size_percent==15 and defaults.logo_margin==20 and defaults.logo_opacity==100


def test_missing_persisted_logo_is_disabled_without_losing_path(tmp_path):
    missing=tmp_path/"deleted-logo.png"
    app=SimpleNamespace(logo_enabled_var=Mock(),logo_path_var=Mock(),status_var=Mock(),translator=Mock(),_save=Mock(),_update_logo_controls=Mock(),_update_batch_logo_value=Mock())
    app.logo_enabled_var.get.return_value=True; app.logo_path_var.get.return_value=str(missing); app.translator.text.return_value="Logo missing"
    app._logo_path=MarkerApp._logo_path.__get__(app)
    MarkerApp._validate_saved_logo(app)
    app.logo_enabled_var.set.assert_called_once_with(False)
    assert app.logo_path_var.get()==str(missing)
    app.status_var.set.assert_called_once_with("Logo missing")


def test_video_command_never_uses_configured_logo(tmp_path):
    completed=type("Completed",(),{"returncode":0,"stderr":""})(); logo=tmp_path/"private-logo.png"
    with patch("nenolink_ai_marker.batch.find_ffmpeg",return_value="ffmpeg.exe"),patch("nenolink_ai_marker.batch.subprocess.run",return_value=completed) as run:
        BatchProcessor.process_video(Path("source.mp4"),Path("badge.png"),Path("target.mp4"),MarkerSettings(logo_enabled=True,logo_path=str(logo)))
    assert str(logo) not in " ".join(map(str,run.call_args.args[0]))
