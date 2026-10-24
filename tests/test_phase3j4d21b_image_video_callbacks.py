from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from nenolink_ai_marker import video_workspace as video_module
from nenolink_ai_marker.batch import BatchProcessor, video_enable_expression, video_overlay_visible_at
from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.processor import ImageProcessor
from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.workspace_state import ImageWorkspaceState, VideoWorkspaceState


def _png(path: Path, color, size=(12, 12)) -> Path:
    Image.new("RGBA", size, color).save(path)
    return path


def test_image_checkbox_and_slider_callbacks_only_dispatch_their_own_values(tmp_path):
    logo = _png(tmp_path / "own-logo.png", (0, 0, 255, 255))
    state = ImageWorkspaceState()
    state.logo.enabled = True
    state.logo.path = logo
    state.badge.enabled = False
    workspace = ImageWorkspace.__new__(ImageWorkspace)
    workspace.app = SimpleNamespace()  # Deliberately has no legacy MarkerApp vars.
    workspace.state = state
    workspace.root = None
    workspace.refresh_preview = lambda: None

    workspace.visual_changed(42)  # A CTkSlider-style numeric callback is not a checkbox.
    assert state.badge.enabled is False
    assert state.logo.enabled is True and state.logo.path == logo

    workspace.visual_changed(True)
    assert state.badge.enabled is True
    assert state.logo.enabled is True and state.logo.path == logo

    workspace.badge_parameter_changed("size", 41.7)
    assert state.badge.size == 41
    assert state.badge.enabled is True
    assert state.logo.enabled is True and state.logo.path == logo


def test_image_badge_selection_keeps_logo_authority_and_save_uses_state(tmp_path, monkeypatch):
    source = _png(tmp_path / "source.png", (40, 40, 40, 255))
    badge = _png(tmp_path / "human-reviewed.png", (255, 0, 0, 255))
    logo = _png(tmp_path / "logo.png", (0, 0, 255, 255))

    class Badges:
        def display_badges(self):
            return [badge]

        def display_name(self, badge_id):
            return "Human Reviewed" if badge_id == badge.name else badge_id

        def find(self, badge_id):
            return badge if badge_id == badge.name else None

    captured = {}

    class Processor:
        def process(self, path, selected_badge, settings, selected_logo):
            captured.update(source=path, badge=selected_badge, settings=settings, logo=selected_logo)
            return Image.new("RGBA", (16, 16), "white")

        def save(self, image, destination, metadata):
            captured["destination"] = destination
            return True

    state = ImageWorkspaceState(selected_files=(source,), path=source)
    state.badge.badge_id = badge.name
    state.logo.enabled = True
    state.logo.path = logo
    workspace = ImageWorkspace.__new__(ImageWorkspace)
    workspace.app = SimpleNamespace(
        badges=Badges(), settings=lambda: MarkerSettings(), processor=Processor(),
        translator=SimpleNamespace(text=lambda key, **kwargs: key.format(**kwargs)),
        status_var=SimpleNamespace(set=lambda _value: None),
    )
    workspace.state = state
    workspace.root = None
    workspace.badge_control = SimpleNamespace(selector_var=SimpleNamespace(get=lambda: "Human Reviewed"))
    workspace.project = lambda: None
    workspace.refresh_preview = lambda: None

    workspace.badge_changed()
    assert state.badge.badge_id == badge.name
    assert state.logo.path == logo and state.logo.enabled

    import tkinter.filedialog as filedialog
    import tkinter.messagebox as messagebox
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_kwargs: str(tmp_path / "output.png"))
    monkeypatch.setattr(messagebox, "showinfo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *_args, **_kwargs: None)
    workspace.save()

    assert captured["source"] == source
    assert captured["badge"] == badge
    assert captured["logo"] == logo
    assert captured["settings"].logo_enabled is True
    assert captured["settings"].logo_path == str(logo)
    assert captured["destination"] == tmp_path / "output.png"


def test_image_event_state_drives_concrete_preview_and_saved_pixels(tmp_path, monkeypatch):
    source = _png(tmp_path / "source.png", (20, 20, 20, 255), size=(100, 80))
    badge = _png(tmp_path / "ai-assisted.png", (255, 0, 0, 255))
    logo = _png(tmp_path / "logo.png", (0, 0, 255, 255))

    class Badges:
        def display_badges(self):
            return [badge]

        def display_name(self, _badge_id):
            return "AI Assisted"

        def find(self, badge_id):
            return badge if badge_id == badge.name else None

    class PreviewLabel:
        def configure(self, **kwargs):
            self.options = kwargs

    class FakeCTkImage:
        def __init__(self, *, light_image, dark_image, size):
            self.image = light_image
            self.size = size

    monkeypatch.setattr("nenolink_ai_marker.image_workspace.ctk.CTkImage", FakeCTkImage)
    state = ImageWorkspaceState(path=source, selected_files=(source,))
    state.badge.badge_id = badge.name
    state.badge.enabled = True
    state.badge.position = "top-right"
    state.badge.size = 20
    state.badge.margin = 0
    state.logo.enabled = True
    state.logo.path = logo
    state.logo.position = "top-left"
    state.logo.size = 20
    state.logo.margin = 0
    captured = {}
    app = SimpleNamespace(
        badges=Badges(), processor=ImageProcessor(), settings=lambda: MarkerSettings(),
        preview_renderer=SimpleNamespace(render=lambda image, selected_badge, settings, selected_logo: (
            captured.update(preview=(image, selected_badge, settings, selected_logo))
            or ImageProcessor().process(image, selected_badge, settings, selected_logo)
        )),
        translator=SimpleNamespace(text=lambda key, **kwargs: key.format(**kwargs)),
        preview_photo=None, preview_image=None, status_var=SimpleNamespace(set=lambda _value: None),
    )
    workspace = ImageWorkspace.__new__(ImageWorkspace)
    workspace.app = app
    workspace.state = state
    workspace.root = None
    workspace.preview_label = PreviewLabel()
    workspace._show_preview = lambda: None

    workspace.badge_parameter_changed("opacity", 60)
    assert state.badge.opacity == 60 and state.logo.path == logo
    workspace.refresh_preview()
    preview_source, preview_badge, preview_settings, preview_logo = captured["preview"]
    assert preview_source == source and preview_badge == badge and preview_logo == logo
    assert preview_settings.opacity == 60 and preview_settings.logo_enabled
    assert app.preview_photo.image.getpixel((0, 0))[:3] == (0, 0, 255)

    import tkinter.filedialog as filedialog
    import tkinter.messagebox as messagebox
    target = tmp_path / "marked.png"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_kwargs: str(target))
    monkeypatch.setattr(messagebox, "showinfo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *_args, **_kwargs: None)
    workspace.save()
    assert target.is_file()
    with Image.open(target) as output:
        assert output.convert("RGBA").getpixel((0, 0))[:3] == (0, 0, 255)


@pytest.mark.parametrize(
    ("badge_enabled", "logo_enabled", "logo_mode", "expected_badge", "expected_logo"),
    [
        (True, False, "entire", True, False),
        (False, True, "entire", False, True),
        (True, True, "entire", True, True),
        (True, True, "back", True, False),  # representative frame is t=1s
    ],
)
def test_video_preview_composites_badge_and_logo_independently_at_sample_time(
    tmp_path, monkeypatch, badge_enabled, logo_enabled, logo_mode, expected_badge, expected_logo,
):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"test video placeholder")
    badge = _png(tmp_path / "ai-assisted.png", (255, 0, 0, 255))
    logo = _png(tmp_path / "logo.png", (0, 0, 255, 255))

    class Badges:
        def display_badges(self):
            return [badge]

    class PreviewLabel:
        def configure(self, **kwargs):
            self.options = kwargs

    class FakeCTkImage:
        def __init__(self, *, light_image, dark_image, size):
            self.image = light_image
            self.size = size

    monkeypatch.setattr(video_module, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(video_module, "extract_video_frame", lambda _ffmpeg, _path, *, timestamp: Image.new("RGBA", (80, 60), (0, 0, 0, 255)))
    monkeypatch.setattr(video_module, "video_duration_seconds", lambda *_args: 20.0)
    monkeypatch.setattr(video_module.ctk, "CTkImage", FakeCTkImage)

    state = VideoWorkspaceState(path=source)
    state.badge.enabled = badge_enabled
    state.logo.enabled = logo_enabled
    state.logo.path = logo
    state.logo.mode = logo_mode
    state.badge.margin = 0
    state.logo.margin = 0
    state.mode = "beginning"
    state.duration = 5
    workspace = VideoWorkspace.__new__(VideoWorkspace)
    workspace.app = SimpleNamespace(
        badges=Badges(), processor=ImageProcessor(),
        video_preview_label=PreviewLabel(),
        translator=SimpleNamespace(text=lambda key, **kwargs: key.format(**kwargs)),
    )
    workspace.state = state
    workspace.preview_photo = None
    workspace.refresh_preview()

    assert workspace.PREVIEW_TIMESTAMP_SECONDS == 1.0
    rendered = workspace.preview_photo.image
    assert (rendered.getpixel((79, 59))[:3] == (255, 0, 0)) is expected_badge
    assert (rendered.getpixel((0, 0))[:3] == (0, 0, 255)) is expected_logo


@pytest.mark.parametrize(
    ("mode", "timestamp", "visible"),
    [("front", 1, True), ("beginning", 1, True), ("entire", 19, True),
     ("permanent", 19, True), ("back", 1, False), ("back", 16, True),
     ("end", 16, True), ("end", 1, False)],
)
def test_video_preview_timing_aliases_match_saved_overlay_timing(mode, timestamp, visible):
    assert video_overlay_visible_at(mode, 5, 20, timestamp) is visible


def test_video_save_request_uses_independent_authoritative_badge_logo_state(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"test video placeholder")
    badge = _png(tmp_path / "ai-assisted.png", (255, 0, 0, 255))
    logo = _png(tmp_path / "logo.png", (0, 0, 255, 255))

    class Badges:
        def display_badges(self):
            return [badge]

        def display_name(self, _badge_id):
            return "AI Assisted"

    state = VideoWorkspaceState(path=source)
    state.badge.enabled = True
    state.badge.badge_id = badge.name
    state.badge.size = 37
    state.badge.position = "bottom-left"
    state.logo.enabled = True
    state.logo.path = logo
    state.logo.mode = "back"
    state.logo.size = 26
    state.logo.margin = 9
    state.logo.opacity = 73
    state.duration = 7
    state.mode = "beginning"
    workspace = VideoWorkspace.__new__(VideoWorkspace)
    workspace.app = SimpleNamespace(
        badges=Badges(), processor=object(),
        translator=SimpleNamespace(text=lambda key, **kwargs: key.format(**kwargs)),
        status_var=SimpleNamespace(set=lambda _value: None),
    )
    workspace.state = state

    import tkinter.filedialog as filedialog
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_kwargs: str(tmp_path / "output.mp4"))
    monkeypatch.setattr(video_module, "find_ffmpeg", lambda: "ffmpeg")
    recorded = {}
    monkeypatch.setattr(BatchProcessor, "process_video", lambda *args, **kwargs: recorded.update(args=args, kwargs=kwargs))
    workspace.save()
    args = recorded["args"]
    # The monkeypatched instance method receives BatchProcessor as self.
    settings = args[4]
    assert args[2] == badge and recorded["kwargs"]["logo"] == logo
    assert settings.video_mode == "beginning" and settings.video_duration == 7
    assert settings.logo_mode == "back" and settings.logo_enabled
    assert settings.logo_size_percent == 26 and settings.logo_margin == 9 and settings.logo_opacity == 73
    assert settings.size_percent == 37 and settings.position == "bottom-left"


def test_video_slider_and_checkbox_callbacks_do_not_read_legacy_app_values(tmp_path):
    logo = _png(tmp_path / "logo.png", (0, 0, 255, 255))
    state = VideoWorkspaceState(path=tmp_path / "clip.mp4")
    state.badge.enabled = False
    state.logo.enabled = True
    state.logo.path = logo
    workspace = VideoWorkspace.__new__(VideoWorkspace)
    workspace.app = SimpleNamespace(_save_image_settings=lambda: None)
    workspace.state = state
    workspace.project = lambda: None
    workspace.refresh_preview = lambda: None
    workspace.video_position_display_to_value = {"Top left": "top-left"}

    workspace.change_visual(64)  # Slider-style numeric callback, not checkbox status.
    assert state.badge.enabled is False
    workspace.change_badge_parameter("opacity", 64)
    assert state.badge.opacity == 64 and state.badge.enabled is False
    assert state.logo.enabled and state.logo.path == logo
    workspace.change_badge_position("Top left")
    assert state.badge.position == "top-left"
    assert state.logo.enabled and state.logo.path == logo
    workspace.change_visual(True)
    assert state.badge.enabled is True
    assert state.logo.enabled and state.logo.path == logo


def test_video_front_back_saved_filter_uses_shared_beginning_end_semantics(monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"input")
    logo = _png(tmp_path / "logo.png", (0, 0, 255, 255))
    commands = []

    class Completed:
        returncode = 0
        stderr = ""

    monkeypatch.setattr("nenolink_ai_marker.batch.find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr("nenolink_ai_marker.batch.video_duration_seconds", lambda *_args: 20.0)
    monkeypatch.setattr("nenolink_ai_marker.batch.subprocess.run", lambda command, **_kwargs: commands.append(command) or Completed())
    settings = MarkerSettings(logo_enabled=True, logo_path=str(logo), logo_mode="front", video_duration=5)
    BatchProcessor.process_video(source, None, tmp_path / "front.mp4", settings, logo=logo)
    assert "between(t\\,0\\,5)" in commands[-1][commands[-1].index("-filter_complex") + 1]
    settings.logo_mode = "back"
    BatchProcessor.process_video(source, None, tmp_path / "back.mp4", settings, logo=logo)
    assert "gte(t\\,15)" in commands[-1][commands[-1].index("-filter_complex") + 1]


def test_video_timing_helper_preserves_existing_badge_expressions():
    assert video_enable_expression("beginning", 5, 20) == ":enable='between(t\\,0\\,5)'"
    assert video_enable_expression("front", 5, 20) == ":enable='between(t\\,0\\,5)'"
    assert video_enable_expression("end", 5, 20) == ":enable='gte(t\\,15)'"
    assert video_enable_expression("back", 5, 20) == ":enable='gte(t\\,15)'"
