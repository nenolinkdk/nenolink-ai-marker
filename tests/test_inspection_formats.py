from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import BadZipFile

import pytest
from PIL import Image
from pypdf import PdfWriter

from nenolink_ai_marker.document_processing import (
    DisclosureSettings, ItemSelection, ProcessingRequest,
)
from nenolink_ai_marker.inspection import InspectionError, INSPECT_EXTENSIONS, inspect_file
from nenolink_ai_marker.metadata import marker_metadata
from nenolink_ai_marker.pdf_processor import PdfProcessor
from nenolink_ai_marker.pptx_processor import PptxProcessor


def _make_pdf(path: Path, *, password: str | None = None) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    if password:
        writer.encrypt(password)
    with path.open("wb") as stream:
        writer.write(stream)


def _document_request(source: Path, destination: Path, badge: Path) -> ProcessingRequest:
    return ProcessingRequest(
        source, destination,
        DisclosureSettings("ai-assisted.png", "AI Assisted", language="da"),
        badge_path=badge,
        metadata=marker_metadata("ai-assisted.png", "AI Assisted"),
    )


def test_pdf_metadata_round_trip_and_unmarked_pdf(tmp_path):
    source = tmp_path / "source.pdf"
    marked = tmp_path / "marked.pdf"
    unmarked = tmp_path / "unmarked.pdf"
    badge = tmp_path / "badge.png"
    Image.new("RGBA", (64, 24), "green").save(badge)
    _make_pdf(source)
    _make_pdf(unmarked)

    PdfProcessor().process(_document_request(source, marked, badge), ItemSelection())

    before = marked.read_bytes()
    inspected = inspect_file(marked)
    assert inspected.found
    assert (inspected.software, inspected.ai_label, inspected.marker_version) == (
        "Nenolink AI Marker", "AI Assisted", "1.0.3",
    )
    assert inspected.disclosure_language == "da"
    assert marked.read_bytes() == before
    assert not inspect_file(unmarked).found


def test_encrypted_pdf_inspect_preserves_pdf_security_contract(tmp_path):
    encrypted = tmp_path / "encrypted.pdf"
    _make_pdf(encrypted, password="secret")
    with pytest.raises(InspectionError) as error:
        inspect_file(encrypted)
    assert error.value.code == "protected_pdf"


def test_pdf_inspection_keeps_existing_hard_limit(tmp_path, monkeypatch):
    from nenolink_ai_marker.document_limits import DocumentMetrics
    from nenolink_ai_marker import inspection

    source = tmp_path / "oversized.pdf"
    _make_pdf(source)
    monkeypatch.setattr(
        inspection.PdfProcessor, "inspect",
        lambda _path: SimpleNamespace(metrics=DocumentMetrics(301 * 1024 * 1024, 1)),
    )
    with pytest.raises(InspectionError) as error:
        inspect_file(source)
    assert error.value.code == "pdf_limit"


def test_pptx_metadata_round_trip_and_unmarked_deck(tmp_path):
    from test_pptx_processor import _create_pptx

    source = tmp_path / "source.pptx"
    marked = tmp_path / "marked.pptx"
    unmarked = tmp_path / "unmarked.pptx"
    badge = tmp_path / "badge.png"
    Image.new("RGBA", (64, 24), "green").save(badge)
    _create_pptx(source, 1)
    _create_pptx(unmarked, 1)

    PptxProcessor().process(_document_request(source, marked, badge), ItemSelection())

    before = marked.read_bytes()
    inspected = inspect_file(marked)
    assert inspected.found
    assert (inspected.software, inspected.ai_label, inspected.marker_version) == (
        "Nenolink AI Marker", "AI Assisted", "1.0.3",
    )
    assert inspected.disclosure_language == "da"
    assert marked.read_bytes() == before
    assert not inspect_file(unmarked).found


def test_video_metadata_round_trip_with_real_ffmpeg(tmp_path):
    from nenolink_ai_marker.batch import BatchProcessor, find_ffmpeg
    from nenolink_ai_marker.models import MarkerSettings

    ffmpeg = find_ffmpeg()
    assert ffmpeg
    source_frame = tmp_path / "frame.png"
    source = tmp_path / "source.mp4"
    output = tmp_path / "marked.mp4"
    badge = tmp_path / "ai-assisted.png"
    Image.new("RGB", (160, 120), "black").save(source_frame)
    Image.new("RGBA", (64, 24), "green").save(badge)
    import subprocess
    subprocess.run(
        [ffmpeg, "-y", "-loop", "1", "-i", str(source_frame), "-t", "0.6",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        check=True, capture_output=True, text=True,
    )
    assert not inspect_file(source).found
    assert BatchProcessor.process_video(
        source, badge, output, MarkerSettings(video_mode="permanent"),
        marker_metadata("ai-assisted.png", "AI Assisted"),
    )
    before = output.read_bytes()
    inspected = inspect_file(output)
    assert inspected.found and inspected.software == "Nenolink AI Marker"
    assert inspected.ai_label == "AI Assisted" and inspected.marker_version == "1.0.3"
    assert output.read_bytes() == before


@pytest.mark.parametrize("suffix", [".png", ".mp4", ".pdf", ".pptx"])
def test_invalid_supported_files_return_clear_inspection_error(tmp_path, suffix):
    invalid = tmp_path / f"invalid{suffix}"
    invalid.write_bytes(b"not a valid media/document file")
    with pytest.raises(InspectionError) as error:
        inspect_file(invalid)
    assert error.value.code == "invalid_file"


def test_unsupported_and_missing_files_have_distinct_errors(tmp_path):
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("plain text", encoding="utf-8")
    missing = tmp_path / "missing.pdf"
    with pytest.raises(InspectionError) as error:
        inspect_file(unsupported)
    assert error.value.code == "unsupported_type"
    with pytest.raises(InspectionError) as error:
        inspect_file(missing)
    assert error.value.code == "missing_file"


@pytest.mark.parametrize("locale", ["cs", "da", "de", "en", "es", "fr", "it", "nl", "no", "pl", "pt", "sv"])
def test_inspect_localization_keys_exist_for_all_supported_locales(locale):
    data = json.loads((Path(__file__).parents[1] / "locales" / f"{locale}.json").read_text(encoding="utf-8"))
    required = {"inspect.intro", "inspect.supported", "inspect.unsupported_type", "inspect.invalid_file"}
    assert required <= data.keys()
    assert all(data[key].strip() for key in required)


def test_inspect_file_filter_and_results_cover_target_formats():
    assert {".jpg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".avi", ".webm", ".pdf", ".pptx"} <= INSPECT_EXTENSIONS


def test_inspect_overlay_callback_does_not_mutate_workspace_state(tmp_path, monkeypatch):
    import nenolink_ai_marker.app as app_module
    from nenolink_ai_marker.app import MarkerApp
    from nenolink_ai_marker.inspection import InspectionResult

    source = tmp_path / "marked.pdf"
    source.write_bytes(b"fixture")
    state = {"path": Path("current-image.png"), "badge": "human-reviewed.png", "scope": "all"}
    configured = []
    app = SimpleNamespace(
        translator=SimpleNamespace(text=lambda key, **values: key.format(**values)),
        tool_inspect_result=SimpleNamespace(configure=lambda **values: configured.append(values)),
        _tool_inspection_projection=None,
        _workspace_registry={"image": SimpleNamespace(state=state)},
    )
    app._project_inspection_result = lambda: MarkerApp._project_inspection_result(app)
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **_kwargs: str(source))
    monkeypatch.setattr(app_module, "inspect_file", lambda path: InspectionResult(path, "PDF", 7, True, "Nenolink AI Marker", "AI Assisted", "1.0.3", "en"))

    MarkerApp._tool_choose_inspection(app)

    assert app._workspace_registry["image"].state is state
    assert state == {"path": Path("current-image.png"), "badge": "human-reviewed.png", "scope": "all"}
    assert configured and "AI Assisted" in configured[-1]["text"]
