from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, PngImagePlugin

from nenolink_ai_marker.inspection import human_file_size, inspect_file
from nenolink_ai_marker.metadata import marker_metadata
from nenolink_ai_marker.processor import ImageProcessor


@pytest.mark.parametrize("suffix", [".jpg", ".png", ".webp"])
def test_image_write_read_round_trip(suffix, tmp_path):
    target = tmp_path / f"marked{suffix}"
    metadata = marker_metadata("ai-localization.png")
    assert ImageProcessor().save(Image.new("RGBA", (20, 20), "red"), target, metadata)
    before = target.read_bytes()
    result = inspect_file(target)
    assert result.found
    assert result.software == "Nenolink AI Marker"
    assert result.ai_label == "AI Localization"
    assert result.marker_version == "0.5.0"
    assert target.read_bytes() == before


def test_custom_badge_display_name_round_trip(tmp_path):
    target = tmp_path / "custom.png"
    metadata = marker_metadata("my-company-ai-assisted.png")
    ImageProcessor().save(Image.new("RGBA", (10, 10), "blue"), target, metadata)
    assert inspect_file(target).ai_label == "My Company AI Assisted"


def test_ordinary_image_is_not_found(tmp_path):
    target = tmp_path / "ordinary.jpg"
    Image.new("RGB", (10, 10), "white").save(target)
    result = inspect_file(target)
    assert not result.found
    assert result.ai_label is None


def test_generic_software_field_alone_is_not_found(tmp_path):
    target = tmp_path / "generic.png"
    info = PngImagePlugin.PngInfo(); info.add_text("Software", "Nenolink AI Marker")
    Image.new("RGB", (10, 10)).save(target, pnginfo=info)
    assert not inspect_file(target).found


def test_partial_identifier_metadata_is_found_without_inventing_values(tmp_path):
    target = tmp_path / "partial.png"
    info = PngImagePlugin.PngInfo(); info.add_text("NenolinkAIMarker", "1"); info.add_text("Software", "Nenolink AI Marker"); info.add_text("Marker Version", "0.5.0")
    Image.new("RGB", (10, 10)).save(target, pnginfo=info)
    result = inspect_file(target)
    assert result.found
    assert result.ai_label is None
    assert result.marker_version == "0.5.0"


def test_malformed_metadata_is_handled(tmp_path):
    target = tmp_path / "malformed.jpg"
    Image.new("RGB", (10, 10)).save(target, xmp=b"not xml")
    assert not inspect_file(target).found


@pytest.mark.parametrize("suffix", [".mp4", ".mov"])
def test_video_metadata_round_trip_values_and_read_only(suffix, tmp_path):
    target = tmp_path / f"marked{suffix}"; target.write_bytes(b"video")
    output = ";FFMETADATA1\nsoftware=Nenolink AI Marker\nai_label=AI Generated\nmarker_version=0.5.0\nnenolink_ai_marker=1\n"
    completed = type("Completed", (), {"returncode": 0, "stdout": output, "stderr": ""})()
    with patch("nenolink_ai_marker.inspection.find_ffmpeg", return_value="C:/ffmpeg.exe"), patch("nenolink_ai_marker.inspection.subprocess.run", return_value=completed) as run:
        before = target.read_bytes(); result = inspect_file(target)
    assert result.found and result.ai_label == "AI Generated" and result.marker_version == "0.5.0"
    assert target.read_bytes() == before
    assert run.call_args.args[0][-3:] == ["-f", "ffmetadata", "-"]


def test_ordinary_video_is_not_found(tmp_path):
    target = tmp_path / "ordinary.mp4"; target.write_bytes(b"video")
    completed = type("Completed", (), {"returncode": 0, "stdout": ";FFMETADATA1\nencoder=other\n", "stderr": ""})()
    with patch("nenolink_ai_marker.inspection.find_ffmpeg", return_value="C:/ffmpeg.exe"), patch("nenolink_ai_marker.inspection.subprocess.run", return_value=completed):
        assert not inspect_file(target).found


def test_corrupt_video_and_unsupported_format_are_graceful(tmp_path):
    video = tmp_path / "bad.mp4"; video.write_bytes(b"bad")
    failed = type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "Invalid data"})()
    with patch("nenolink_ai_marker.inspection.find_ffmpeg", return_value="C:/ffmpeg.exe"), patch("nenolink_ai_marker.inspection.subprocess.run", return_value=failed):
        with pytest.raises(ValueError, match="Could not read video metadata"): inspect_file(video)
    unsupported = tmp_path / "file.txt"; unsupported.write_text("x")
    with pytest.raises(ValueError, match="Unsupported file type"): inspect_file(unsupported)


def test_human_file_sizes():
    assert human_file_size(725 * 1024) == "725 KB"
    assert human_file_size(5 * 1024 * 1024) == "5 MB"
