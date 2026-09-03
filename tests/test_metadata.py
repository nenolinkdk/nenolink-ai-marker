from pathlib import Path
from unittest.mock import patch

from PIL import Image, PngImagePlugin

from nenolink_ai_marker import __version__
from nenolink_ai_marker.batch import BatchProcessor, scan_folder
from nenolink_ai_marker.metadata import marker_metadata
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.processor import ImageProcessor


def _marked_image():
    return Image.new("RGBA", (32, 24), (20, 40, 60, 255))


def test_jpeg_writes_standard_and_structured_metadata(tmp_path):
    target = tmp_path / "marked.jpg"
    metadata = marker_metadata("ai-localization.png")
    assert ImageProcessor().save(_marked_image(), target, metadata)
    with Image.open(target) as result:
        exif = result.getexif()
        assert exif[305] == "Nenolink AI Marker"
        assert "AI Label=AI Localization" in exif[270]
        assert f"Version={__version__}" in exif[270]
        assert b'nenolink:AILabel="AI Localization"' in result.info["xmp"]
        assert f'nenolink:MarkerVersion="{__version__}"'.encode() in result.info["xmp"]


def test_png_writes_explicit_metadata_keys(tmp_path):
    target = tmp_path / "marked.png"
    metadata = marker_metadata("ai-generated.png")
    assert ImageProcessor().save(_marked_image(), target, metadata)
    with Image.open(target) as result:
        assert result.info["Software"] == "Nenolink AI Marker"
        assert result.info["AI Label"] == "AI Generated"
        assert result.info["Marker Version"] == __version__
        assert result.info["NenolinkAIMarker"] == "1"


def test_webp_writes_exif_metadata_with_existing_pillow(tmp_path):
    target = tmp_path / "marked.webp"
    metadata = marker_metadata("ai-assisted.png")
    assert ImageProcessor().save(_marked_image(), target, metadata)
    with Image.open(target) as result:
        exif = result.getexif()
        assert exif[305] == "Nenolink AI Marker"
        assert "AI Label=AI Assisted" in exif[270]
        assert b'nenolink:AILabel="AI Assisted"' in result.info["xmp"]


def test_batch_custom_badge_name_and_original_unchanged(tmp_path):
    source_root = tmp_path / "input"
    source_root.mkdir()
    source = source_root / "photo.png"
    badge = tmp_path / "my-company-ai-assisted.png"
    Image.new("RGB", (40, 30), "white").save(source)
    Image.new("RGBA", (20, 10), "red").save(badge)
    original = source.read_bytes()
    result = BatchProcessor().process(scan_folder(source_root), badge, MarkerSettings())
    assert result.successful == 1
    assert not result.metadata_warnings
    assert source.read_bytes() == original
    with Image.open(source_root / "AI-marked" / "photo_ai.png") as output:
        assert output.info["AI Label"] == "My Company AI Assisted"


def test_metadata_encoder_failure_retries_visible_output(tmp_path):
    target = tmp_path / "marked.png"
    with patch.object(PngImagePlugin.PngInfo, "add_text", side_effect=ValueError("metadata rejected")):
        assert not ImageProcessor().save(_marked_image(), target, marker_metadata("ai-assisted.png"))
    assert target.is_file()
    with Image.open(target) as output:
        assert output.size == (32, 24)


def test_video_command_contains_selected_badge_and_version():
    completed = type("Completed", (), {"returncode": 0, "stderr": ""})()
    metadata = marker_metadata("ai-generated.png")
    with patch("nenolink_ai_marker.batch.find_ffmpeg", return_value="C:/ffmpeg.exe"), patch(
        "nenolink_ai_marker.batch.subprocess.run", return_value=completed
    ) as run:
        assert BatchProcessor.process_video(
            Path("input.mp4"), Path("ai-generated.png"), Path("output.mp4"),
            MarkerSettings(), metadata,
        )
    command = run.call_args.args[0]
    assert "software=Nenolink AI Marker" in command
    assert "ai_label=AI Generated" in command
    assert f"marker_version={__version__}" in command
    assert "use_metadata_tags" in command


def test_video_metadata_failure_retries_without_metadata():
    failed = type("Completed", (), {"returncode": 1, "stderr": "metadata rejected"})()
    succeeded = type("Completed", (), {"returncode": 0, "stderr": ""})()
    with patch("nenolink_ai_marker.batch.find_ffmpeg", return_value="C:/ffmpeg.exe"), patch(
        "nenolink_ai_marker.batch.subprocess.run", side_effect=[failed, succeeded]
    ) as run:
        assert not BatchProcessor.process_video(
            Path("input.mp4"), Path("ai-generated.png"), Path("output.mp4"), MarkerSettings()
        )
    assert len(run.call_args_list) == 2
    assert "-metadata" in run.call_args_list[0].args[0]
    assert "-metadata" not in run.call_args_list[1].args[0]
