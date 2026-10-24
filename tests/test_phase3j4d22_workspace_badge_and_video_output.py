from pathlib import Path
from types import SimpleNamespace
import subprocess

from PIL import Image

from nenolink_ai_marker.badges import BadgeRepository
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.pdf_processor import PdfProcessor
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.pptx_state import PptxWorkspaceState
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.workspace_state import PdfWorkspaceState, VideoWorkspaceState


def _repository():
    return BadgeRepository(Path(__file__).parents[1] / "assets" / "badges", standard=True)


def test_badge_repository_resolves_display_names_without_tool_mapping():
    repository = _repository()

    assert repository.canonical_filename("Human Reviewed") == "human-reviewed.png"
    assert repository.canonical_filename("ai-assisted.png") == "ai-assisted.png"
    assert repository.canonical_filename("not a badge") is None


def test_video_badge_callback_canonicalizes_without_badges_tool(tmp_path):
    repository = _repository()
    app = SimpleNamespace(badges=repository, badge_display_to_file={},
                          _save_image_settings=lambda: None)
    workspace = VideoWorkspace(app, VideoWorkspaceState())
    workspace.project = lambda: None
    workspace.refresh_preview = lambda: None

    workspace.change_badge("Human Reviewed")

    assert workspace.state.badge.badge_id == "human-reviewed.png"
    assert workspace._badge_path() == repository.find("human-reviewed.png")


def test_pdf_badge_callback_and_request_use_canonical_repository_id(tmp_path):
    from pypdf import PdfWriter

    source = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with source.open("wb") as stream:
        writer.write(stream)
    repository = _repository()
    app = SimpleNamespace(
        badges=repository, badge_display_to_file={},
        translator=SimpleNamespace(language="en"),
        settings=lambda: MarkerSettings(),
    )
    workspace = PdfWorkspace(app, PdfWorkspaceState())
    workspace.project = lambda: None
    workspace.refresh_preview = lambda: None
    workspace.accept_file(source, PdfProcessor.inspect(source))

    workspace.select_badge("Human Reviewed")
    output = tmp_path / "output.pdf"
    request = workspace.build_processing_request(output)
    result = PdfProcessor().process(request.request, request.selection)

    assert workspace.state.badge.badge_id == "human-reviewed.png"
    assert request.request.badge_path == repository.find("human-reviewed.png")
    assert output.is_file() and result.badge_pages == 1


def test_pptx_default_display_badge_is_resolved_for_save_request(tmp_path, monkeypatch):
    from tkinter import filedialog
    from test_pptx_processor import _create_pptx

    source = tmp_path / "source.pptx"
    _create_pptx(source, 1)
    destination = tmp_path / "output.pptx"
    repository = _repository()
    processed = []

    class Processor:
        def process(self, request, selection, *, logo_selection=None):
            processed.append((request, selection, logo_selection))

    translator = SimpleNamespace(language="en", text=lambda key, **_values: key)
    app = SimpleNamespace(
        badges=repository, translator=translator,
        settings=lambda: MarkerSettings(), pptx_processor=Processor(),
        status_var=SimpleNamespace(set=lambda _value: None),
    )
    workspace = PptxWorkspace(app)
    workspace.state = PptxWorkspaceState(path=source, slide_count=1,
                                         active_scope=(1,))
    workspace.scope_status = SimpleNamespace(configure=lambda **_kwargs: None)
    monkeypatch.setattr(filedialog, "asksaveasfilename",
                        lambda **_kwargs: str(destination))

    workspace._save_as()

    assert workspace.state.badge.badge_id == "AI Assisted"  # workspace default is preserved
    assert len(processed) == 1
    request, _selection, logo_selection = processed[0]
    assert request.badge_path == repository.find("ai-assisted.png")
    assert request.disclosure.badge_name == "ai-assisted.png"
    assert logo_selection.items == (1,)


def test_pptx_badge_control_selection_stores_canonical_repository_id():
    repository = _repository()
    app = SimpleNamespace(
        badges=repository,
        translator=SimpleNamespace(language="en", text=lambda key, **_values: key),
    )
    workspace = PptxWorkspace(app)

    workspace._select_badge("Human Reviewed")

    assert workspace.state.badge.badge_id == "human-reviewed.png"


def test_video_filter_maps_final_output_and_uses_independent_logo_margin(
    tmp_path, monkeypatch,
):
    import nenolink_ai_marker.batch as batch

    badge = tmp_path / "badge.png"
    logo = tmp_path / "logo.png"
    badge.touch()
    logo.touch()
    captured = []
    monkeypatch.setattr(batch, "find_ffmpeg", lambda: "ffmpeg")

    def fake_run(command, **_kwargs):
        captured.append(command)
        return SimpleNamespace(returncode=0, stderr="")

    from types import SimpleNamespace
    monkeypatch.setattr(batch.subprocess, "run", fake_run)
    settings = MarkerSettings(margin=11, logo_margin=37, position="top-left",
                              video_mode="permanent", logo_mode="permanent")

    assert batch.BatchProcessor.process_video(
        tmp_path / "input.mp4", badge, tmp_path / "output.mp4", settings,
        logo=logo,
    )

    command = captured[0]
    graph = command[command.index("-filter_complex") + 1]
    map_index = command.index("-map")
    assert "overlay=11:11" in graph
    assert "overlay=37:37" in graph
    assert "[base1][ov1]overlay=11:11" in graph
    assert "[base2][ov2]overlay=37:37" in graph
    assert command[map_index + 1] == "[ov2out]"


def test_video_save_creates_real_output_with_bundled_ffmpeg_and_png_logo(
    tmp_path, monkeypatch,
):
    from tkinter import filedialog, messagebox
    from nenolink_ai_marker.batch import find_ffmpeg, extract_video_frame
    from nenolink_ai_marker.processor import ImageProcessor

    ffmpeg = find_ffmpeg()
    assert ffmpeg, "the packaged test contract requires the bundled FFmpeg"
    source = tmp_path / "input.mp4"
    logo = tmp_path / "logo.png"
    output = tmp_path / "output.mp4"
    Image.new("RGBA", (80, 40), (230, 20, 40, 255)).save(logo)
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        check=True, capture_output=True, text=True,
    )

    errors = []
    status = []
    translator = SimpleNamespace(
        text=lambda key, **values: key.format(**values) if values else key,
    )
    app = SimpleNamespace(
        translator=translator, processor=ImageProcessor(), badges=_repository(),
        status_var=SimpleNamespace(set=status.append),
        _save_image_settings=lambda: None,
    )
    state = VideoWorkspaceState(path=source)
    state.badge.enabled = False
    state.logo.enabled, state.logo.path = True, logo
    state.logo.margin = 29
    workspace = VideoWorkspace(app, state)
    monkeypatch.setattr(filedialog, "asksaveasfilename",
                        lambda **_kwargs: str(output))
    monkeypatch.setattr(messagebox, "showerror",
                        lambda *_args: errors.append(_args))
    monkeypatch.setattr(messagebox, "showwarning",
                        lambda *_args: errors.append(_args))

    workspace.save()

    assert not errors
    assert status and "video.saved_name" in status[-1]
    assert output.is_file() and output.stat().st_size > 0
    rendered = extract_video_frame(ffmpeg, output, timestamp=0.2)
    assert rendered.size == (320, 240)
    assert rendered.getpixel((32, 32))[0] > 150  # logo appears at its 29px margin
    assert max(rendered.getpixel((8, 8))[:3]) < 40  # outside the logo remains black
