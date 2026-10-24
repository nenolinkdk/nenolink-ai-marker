from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest

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
    app = SimpleNamespace(badges=repository, badge_display_to_file={})
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

    assert workspace.state.badge.badge_id == "ai-assisted.png"  # canonical workspace default is preserved
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
    from nenolink_ai_marker.batch import VideoProcessReceipt

    badge = tmp_path / "badge.png"
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (80, 40), (255, 0, 0, 255)).save(badge)
    Image.new("RGBA", (80, 40), (0, 0, 255, 255)).save(logo)
    captured = []
    monkeypatch.setattr(batch, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(batch, "extract_video_frame", lambda *_args, **_kwargs: Image.new("RGBA", (640, 360)))

    def fake_run(command):
        captured.append(command)
        return VideoProcessReceipt(tuple(command), 4242, 0, "", 0.25)

    from types import SimpleNamespace
    monkeypatch.setattr(batch, "run_ffmpeg_with_receipt", fake_run)
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
    assert "[0:v][ov1]overlay=11:11" in graph
    assert "[ov1out][ov2]overlay=37:37" in graph
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
    status_threads = []
    main_thread = __import__("threading").get_ident()
    translator = SimpleNamespace(
        text=lambda key, **values: key.format(**values) if values else key,
    )
    scheduled = []
    app = SimpleNamespace(
        translator=translator, processor=ImageProcessor(), badges=_repository(),
        status_var=SimpleNamespace(set=lambda value: (status.append(value), status_threads.append(__import__("threading").get_ident()))),
        after=lambda _delay, callback: scheduled.append(callback),
    )
    state = VideoWorkspaceState(path=source)
    state.badge.enabled = False
    state.logo.enabled, state.logo.path = True, logo
    state.logo.margin = 29
    workspace = VideoWorkspace(app, state)
    dialog_calls = []
    monkeypatch.setattr(filedialog, "asksaveasfilename",
                        lambda **_kwargs: (dialog_calls.append(True), str(output))[1])
    monkeypatch.setattr(messagebox, "showerror",
                        lambda *_args: errors.append(_args))
    monkeypatch.setattr(messagebox, "showwarning",
                        lambda *_args: errors.append(_args))

    workspace.save()
    workspace.save()  # A second click while processing must not open another dialog/job.
    assert len(dialog_calls) == 1
    assert status[-1] == "video.saving"
    workspace._save_thread.join(timeout=20)
    assert not workspace._save_thread.is_alive()
    assert scheduled
    scheduled.pop(0)()

    assert not errors
    assert status and "video.saved_name" in status[-1]
    assert output.is_file() and output.stat().st_size > 0
    rendered = extract_video_frame(ffmpeg, output, timestamp=0.2)
    assert rendered.size == (320, 240)
    assert rendered.getpixel((32, 32))[0] > 150  # logo appears at its 29px margin
    assert max(rendered.getpixel((8, 8))[:3]) < 40  # outside the logo remains black
    assert workspace.last_save_result is not None
    assert workspace.last_save_result.error is None
    assert len(workspace.last_save_result.receipts) == 1
    receipt = workspace.last_save_result.receipts[0]
    assert receipt.pid > 0 and receipt.returncode == 0
    assert receipt.elapsed_seconds > 0 and "-filter_complex" in receipt.command
    assert isinstance(receipt.stderr, str)
    assert status_threads and set(status_threads) == {main_thread}


@pytest.mark.parametrize(("position", "expected_y"), [("top-right", 13), ("bottom-right", 195)])
def test_real_video_output_preserves_source_graphic_and_projects_independent_overlay_margins(
    tmp_path, position, expected_y,
):
    from nenolink_ai_marker.batch import BatchProcessor, extract_video_frame, find_ffmpeg
    from nenolink_ai_marker.processor import ImageProcessor

    ffmpeg = find_ffmpeg()
    assert ffmpeg, "integration test needs the bundled FFmpeg"
    source_png = tmp_path / "source.png"
    source = tmp_path / "source.mp4"
    badge = tmp_path / "badge.png"
    logo = tmp_path / "logo.png"
    output = tmp_path / f"{position}.mp4"
    base = Image.new("RGBA", (320, 240), (20, 20, 20, 255))
    # This magenta rectangle is baked into the input and is not a new overlay.
    for x in range(4, 20):
        for y in range(4, 20):
            base.putpixel((x, y), (220, 20, 180, 255))
    base.save(source_png)
    Image.new("RGBA", (64, 32), (20, 220, 40, 255)).save(badge)
    Image.new("RGBA", (80, 40), (240, 130, 20, 255)).save(logo)
    subprocess.run(
        [ffmpeg, "-y", "-loop", "1", "-i", str(source_png), "-t", "1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        check=True, capture_output=True, text=True,
    )
    settings = MarkerSettings(
        size_percent=20, margin=13, position=position, opacity=100,
        video_mode="permanent", logo_size_percent=25, logo_margin=31,
        logo_opacity=100, logo_position="top-left", logo_mode="entire",
        logo_enabled=True,
    )
    source_frame = extract_video_frame(ffmpeg, source, timestamp=0.1)
    with Image.open(badge) as opened_badge, Image.open(logo) as opened_logo:
        expected = ImageProcessor().compose(
            source_frame, opened_badge.convert("RGBA"), settings,
            opened_logo.convert("RGBA"),
        )
    receipts = []
    assert BatchProcessor.process_video(
        source, badge, output, settings, logo=logo, on_process=receipts.append,
    )
    actual = extract_video_frame(ffmpeg, output, timestamp=0.1)
    assert output.is_file() and output.stat().st_size > 1000
    assert len(receipts) == 1 and receipts[0].returncode == 0
    assert receipts[0].pid > 0 and receipts[0].elapsed_seconds > 0

    # The source's baked mark remains at (10, 10), separate from both overlays.
    source_mark = actual.getpixel((10, 10))
    assert source_mark[0] > 120 and source_mark[2] > 80
    badge_x = 320 - 64 - 13
    badge_center = actual.getpixel((badge_x + 32, expected_y + 16))
    assert badge_center[1] > badge_center[0] * 1.4
    logo_center = actual.getpixel((31 + 40, 31 + 20))
    assert logo_center[0] > 150 and logo_center[1] > 60 and logo_center[2] < 80

    # Compare representative overlay centers to the same ImageProcessor
    # composition used for the workspace preview, allowing H.264 rounding.
    for point in ((badge_x + 32, expected_y + 16), (71, 51)):
        expected_pixel = expected.getpixel(point)
        actual_pixel = actual.getpixel(point)
        assert max(abs(expected_pixel[channel] - actual_pixel[channel]) for channel in range(3)) < 100


def test_video_preview_scales_independent_margins_with_thumbnail_geometry(monkeypatch, tmp_path):
    import nenolink_ai_marker.video_workspace as video_module

    badge = tmp_path / "badge.png"
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (80, 40), (20, 200, 30, 255)).save(badge)
    Image.new("RGBA", (80, 40), (220, 20, 30, 255)).save(logo)
    state = VideoWorkspaceState(path=tmp_path / "source.mp4")
    state.badge.enabled = True
    state.badge.badge_id = badge.name
    state.badge.margin = 20
    state.mode = "permanent"
    state.logo.enabled = True
    state.logo.path = logo
    state.logo.margin = 32
    state.logo.mode = "entire"
    captured = {}

    class PreviewProcessor:
        def compose(self, frame, _badge, settings, _logo):
            captured["settings"] = settings
            return frame

    class Label:
        def configure(self, **_kwargs):
            pass

    class Badges:
        def display_badges(self):
            return [badge]

    app = SimpleNamespace(
        video_preview_label=Label(), processor=PreviewProcessor(), badges=Badges(),
        translator=SimpleNamespace(text=lambda key, **values: key.format(**values)),
    )
    workspace = VideoWorkspace(app, state)
    monkeypatch.setattr(video_module, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(video_module, "extract_video_frame", lambda *_args, **_kwargs: Image.new("RGBA", (1920, 1080)))
    monkeypatch.setattr(video_module.ctk, "CTkImage", lambda **_kwargs: object())

    workspace.refresh_preview()

    assert captured["settings"].margin == 8
    assert captured["settings"].logo_margin == 12


def test_video_save_returns_to_tk_loop_and_ignores_duplicate_click(tmp_path, monkeypatch):
    import threading
    import time
    from tkinter import filedialog, messagebox
    import nenolink_ai_marker.video_workspace as video_module
    from nenolink_ai_marker.batch import BatchProcessor

    source = tmp_path / "input.mp4"
    source.write_bytes(b"test fixture")
    badge = tmp_path / "ai-assisted.png"
    Image.new("RGBA", (80, 40), (20, 200, 30, 255)).save(badge)
    destination = tmp_path / "output.mp4"
    entered = threading.Event()
    release = threading.Event()
    scheduled = []
    dialogs = []
    status_threads = []
    main_thread = threading.get_ident()

    class Badges:
        def display_badges(self):
            return [badge]
        def display_name(self, _badge_id):
            return "AI Assisted"

    app = SimpleNamespace(
        badges=Badges(), processor=object(),
        translator=SimpleNamespace(text=lambda key, **values: key.format(**values)),
        status_var=SimpleNamespace(set=lambda _value: status_threads.append(threading.get_ident())),
        after=lambda _delay, callback: scheduled.append(callback),
    )
    state = VideoWorkspaceState(path=source)
    state.badge.enabled = True
    state.badge.badge_id = badge.name
    workspace = VideoWorkspace(app, state)

    def hold_processing(*_args, **_kwargs):
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(BatchProcessor, "process_video", hold_processing)
    monkeypatch.setattr(video_module, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_kwargs: (dialogs.append(1), str(destination))[1])
    monkeypatch.setattr(messagebox, "showerror", lambda *_args: None)

    started = time.perf_counter()
    workspace.save()
    returned_in = time.perf_counter() - started
    assert returned_in < 0.5
    assert entered.wait(1) and workspace._save_in_progress
    workspace.save()
    assert len(dialogs) == 1
    assert status_threads == [main_thread]

    release.set()
    workspace._save_thread.join(timeout=5)
    assert not workspace._save_thread.is_alive()
    scheduled.pop(0)()
    assert not workspace._save_in_progress
    assert status_threads == [main_thread, main_thread]
