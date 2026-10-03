from __future__ import annotations

from types import SimpleNamespace

from nenolink_ai_marker.pptx_state import PptxWorkspaceState, choose_file_success
from nenolink_ai_marker.pptx_preview import PptxPreviewRenderer
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from test_pptx_processor import _create_pptx, _write_overlay


class _Widget:
    def __init__(self, **values):
        self.values = values
        self.mapped = True

    def configure(self, **values):
        self.values.update(values)

    def winfo_width(self):
        return self.values.get("width", 760)

    def winfo_height(self):
        return self.values.get("height", 470)

    def winfo_ismapped(self):
        return self.mapped


class _Repository:
    def __init__(self, asset):
        self.asset = asset

    def display_badges(self):
        return [self.asset]

    def display_name(self, name):
        return "AI Assisted"


def test_pptx_real_user_navigation_keeps_geometry_and_reset_session(tmp_path, monkeypatch):
    """Exercise the production workspace arrow callback, not the reducer directly."""
    source = tmp_path / "varied-slides.pptx"
    _create_pptx(source, 10)
    badge = tmp_path / "badge.png"
    _write_overlay(badge, (0, 150, 70, 255), (160, 50))

    import nenolink_ai_marker.pptx_workspace as module
    monkeypatch.setattr(module.ctk, "CTkImage", lambda *args, **kwargs: object())
    workspace = PptxWorkspace(SimpleNamespace(badges=_Repository(badge), pptx_preview_renderer=PptxPreviewRenderer()))
    workspace.state = PptxWorkspaceState()
    choose_file_success(workspace.state, source, 10)
    workspace.preview_host = _Widget(width=780, height=520)
    workspace.preview_viewport = _Widget(width=760, height=470)
    workspace.preview_label = _Widget(width=740, height=430)
    workspace.navigation = _Widget(width=120, height=30)
    workspace.previous_button = _Widget()
    workspace.next_button = _Widget()
    workspace.slide_status = _Widget()
    workspace.receipts = SimpleNamespace(record=lambda _entry: None)
    workspace.preview_photo = None
    workspace._render_preview()

    def geometry():
        return (
            workspace.preview_viewport.winfo_width(),
            workspace.preview_viewport.winfo_height(),
            workspace.navigation.winfo_width(),
            workspace.navigation.winfo_height(),
        )

    baseline = geometry()
    baseline_scope = workspace.state.active_scope
    baseline_badge = workspace.state.badge.__dict__.copy()
    sequence = (1, 2, 3, 4, 3, 4)
    for expected in sequence:
        workspace._change_slide(1 if expected > workspace.state.current_slide else -1)
        assert workspace.state.current_slide == expected
        assert geometry() == baseline
        assert workspace.state.active_scope == baseline_scope
        assert workspace.state.badge.__dict__ == baseline_badge
        assert workspace.navigation.winfo_ismapped()
        assert workspace.preview_label.values.get("image") is not None

    # The same callback path is used for the reverse/forward rerender.
    workspace._change_slide(-1)
    workspace._change_slide(1)
    assert workspace.state.current_slide == 4
    assert geometry() == baseline

    workspace.clear_runtime_state()
    assert not workspace.has_active_work()
    assert workspace.state.path is None
    assert workspace.state.slide_count == 0
    assert workspace.state.current_slide == 1
    assert workspace.state.active_scope == ()

