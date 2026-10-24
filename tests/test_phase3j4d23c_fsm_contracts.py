from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.workspace_state import ImageEvent, ImageWorkspaceState, apply_image_event
from nenolink_ai_marker.workspace_state import PdfWorkspaceState, VideoEvent, VideoWorkspaceState, apply_video_event
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.video_workspace import VideoWorkspace


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def test_global_persistence_preserves_workspace_visual_settings():
    original = MarkerSettings(
        language="en", badge_source="standard", custom_badge_folder="",
        badge_name="legacy-badge.png", position="top-left", size_percent=37,
        margin=41, opacity=62, logo_enabled=True, logo_path="legacy-logo.png",
        logo_size_percent=29, logo_margin=31, logo_opacity=73,
        output_folder="batch-output",
    )
    saved = []
    app = SimpleNamespace(
        _saved_settings=original,
        translator=SimpleNamespace(language="da"),
        badge_source_var=_Var("custom"),
        custom_badge_var=_Var("C:/user/badges"),
        config_store=SimpleNamespace(save=saved.append),
        # Persistence must not sample old workspace Tk variables or settings().
        settings=lambda: (_ for _ in ()).throw(AssertionError("stale UI settings read")),
        badge_var=_Var("wrong-video-badge.png"),
        position_var=_Var("center"), size_var=_Var(99), margin_var=_Var(0),
        opacity_var=_Var(1), logo_enabled_var=_Var(False),
        logo_path_var=_Var("wrong-video-logo.png"), logo_position_var=_Var("center"),
        logo_size_var=_Var(99), logo_margin_var=_Var(0), logo_opacity_var=_Var(1),
    )

    MarkerApp._save(app)

    assert len(saved) == 1
    persisted = saved[0]
    assert (persisted.language, persisted.badge_source, persisted.custom_badge_folder) == (
        "da", "custom", "C:/user/badges",
    )
    assert (persisted.badge_name, persisted.position, persisted.size_percent,
            persisted.margin, persisted.opacity) == (
        "legacy-badge.png", "top-left", 37, 41, 62,
    )
    assert (persisted.logo_enabled, persisted.logo_path, persisted.logo_size_percent,
            persisted.logo_margin, persisted.logo_opacity, persisted.output_folder) == (
        True, "legacy-logo.png", 29, 31, 73, "batch-output",
    )


def test_image_preview_cache_belongs_to_workspace_presentation(monkeypatch, tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGBA", (18, 12), (20, 30, 40, 255)).save(source)
    state = ImageWorkspaceState(path=source, selected_files=(source,))
    rendered = Image.new("RGBA", (18, 12), (80, 90, 100, 255))
    configured = []
    workspace = ImageWorkspace.__new__(ImageWorkspace)
    workspace.state = state
    workspace.app = SimpleNamespace(
        badges=SimpleNamespace(find=lambda _badge_id: None),
        settings=lambda: MarkerSettings(),
        preview_renderer=SimpleNamespace(render=lambda *_args: rendered),
        translator=SimpleNamespace(text=lambda key, **_values: key),
    )
    workspace.preview_label = SimpleNamespace(configure=lambda **kwargs: configured.append(kwargs))
    workspace._show_preview = lambda: None
    workspace._show_welcome = lambda: None
    monkeypatch.setattr("nenolink_ai_marker.image_workspace.ctk.CTkImage",
                        lambda **kwargs: SimpleNamespace(**kwargs))

    workspace.refresh_preview()

    assert not hasattr(state, "preview_image")
    assert not hasattr(workspace, "preview_image")
    assert workspace.preview_photo is not None
    assert configured and configured[-1]["image"] is workspace.preview_photo

    apply_image_event(state, ImageEvent.FILE_SELECTED, {"files": ()})
    workspace.refresh_preview()
    assert workspace.preview_photo is None


def test_clean_image_state_has_no_derived_preview_cache_field():
    state = ImageWorkspaceState()
    assert not hasattr(state, "preview_image")


def test_pdf_projection_does_not_repair_badge_or_mutate_workspace_state(monkeypatch):
    import nenolink_ai_marker.pdf_workspace as module

    state = PdfWorkspaceState()
    state.badge.badge_id = ""
    before = (state.path, state.page_count, state.current_page,
              state.scope_mode, state.scope_input, tuple(state.active_scope),
              state.badge.__dict__.copy(), state.logo.__dict__.copy())
    info = object()
    app = SimpleNamespace(
        translator=SimpleNamespace(text=lambda key, **_values: key),
        pdf_info=info,
    )
    workspace = PdfWorkspace.__new__(PdfWorkspace)
    workspace.app = app
    workspace.state = state
    workspace.apply_translations = lambda: None
    workspace._project_badge_controls = lambda: None
    workspace.preview_photo = None
    monkeypatch.setattr(module, "apply_pdf_event",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("project dispatched an event")))

    workspace.project()

    after = (state.path, state.page_count, state.current_page,
             state.scope_mode, state.scope_input, tuple(state.active_scope),
             state.badge.__dict__.copy(), state.logo.__dict__.copy())
    assert after == before
    assert app.pdf_info is info


def test_video_clear_runtime_uses_table_event_and_preserves_local_settings(monkeypatch):
    import nenolink_ai_marker.video_workspace as module

    state = VideoWorkspaceState(path=Path("clip.mp4"))
    state.mode, state.duration = "end", 8
    state.badge.badge_id, state.badge.size = "human-reviewed.png", 42
    state.logo.enabled, state.logo.path = True, Path("logo.png")
    workspace = VideoWorkspace.__new__(VideoWorkspace)
    workspace.app = SimpleNamespace()
    workspace.state = state
    workspace.preview_photo = object()
    events = []
    real_apply = module.apply_video_event

    def record(state_arg, event, payload=None):
        events.append(VideoEvent(event))
        return real_apply(state_arg, event, payload)

    monkeypatch.setattr(module, "apply_video_event", record)
    workspace.clear_runtime_state()

    assert events == [VideoEvent.CLEAR_RUNTIME]
    assert state.path is None
    assert (state.mode, state.duration, state.badge.badge_id,
            state.badge.size, state.logo.enabled, state.logo.path) == (
        "end", 8, "human-reviewed.png", 42, True, Path("logo.png"),
    )
    assert workspace.preview_photo is None


def test_video_duration_visibility_uses_workspace_mode_not_tk_variable():
    from nenolink_ai_marker.video_workspace import VideoWorkspace

    class Widget:
        def __init__(self):
            self.calls = []

        def grid(self): self.calls.append("grid")
        def grid_remove(self): self.calls.append("grid_remove")

    app = SimpleNamespace(
        video_duration_entry=Widget(), video_duration_label=Widget(),
        video_mode_var=SimpleNamespace(get=lambda: "permanent"),
    )
    workspace = VideoWorkspace.__new__(VideoWorkspace)
    workspace.app = app
    workspace.state = VideoWorkspaceState(mode="beginning")

    workspace.project_duration_visibility()
    assert app.video_duration_entry.calls == ["grid"]
    assert app.video_duration_label.calls == ["grid"]

    workspace.state.mode = "permanent"
    workspace.project_duration_visibility()
    assert app.video_duration_entry.calls[-1] == "grid_remove"
    assert app.video_duration_label.calls[-1] == "grid_remove"


def test_workspace_callbacks_do_not_render_preview_twice():
    from nenolink_ai_marker.video_workspace import VideoWorkspace

    class BadgeRepo:
        def canonical_filename(self, value):
            return "ai-assisted.png" if value == "AI Assisted" else None

    renders = {"video": 0, "pdf": 0}
    video = VideoWorkspace.__new__(VideoWorkspace)
    video.app = SimpleNamespace(badges=BadgeRepo())
    video.state = VideoWorkspaceState(path=Path("clip.mp4"))
    video.root = object()
    video.project = lambda: (renders.__setitem__("video", renders["video"] + 1), video.refresh_preview())
    video.refresh_preview = lambda: None
    video.video_position_display_to_value = {}
    video.change_badge("AI Assisted")
    video.change_visual(True)
    video.change_badge_parameter("size", 30)

    pdf = PdfWorkspace.__new__(PdfWorkspace)
    pdf.state = PdfWorkspaceState(path=Path("file.pdf"))
    pdf.project = lambda: (renders.__setitem__("pdf", renders["pdf"] + 1), pdf.refresh_preview())
    pdf.refresh_preview = lambda: None
    pdf.set_badge(size=31)
    pdf.set_logo(enabled=True)

    assert renders == {"video": 3, "pdf": 2}
