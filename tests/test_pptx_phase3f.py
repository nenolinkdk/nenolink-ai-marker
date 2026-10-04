from types import SimpleNamespace

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.pptx_workspace import PptxWorkspace


class _Widget:
    def __init__(self, width=0, height=0):
        self.width, self.height, self.values = width, height, {}

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def configure(self, **values):
        self.values.update(values)


def test_pptx_fit_rectangle_has_one_idempotent_owner():
    workspace = PptxWorkspace.__new__(PptxWorkspace)
    workspace.preview_viewport = _Widget(760, 470)
    first = workspace._preview_fit_rect()
    second = workspace._preview_fit_rect()
    assert first == second == (592, 360)


def test_tools_are_overlays_and_do_not_confirm_or_destroy_active_content(monkeypatch):
    app = SimpleNamespace(
        active_tool=None,
        active_content_type="pptx",
        shell_controller=SimpleNamespace(active_content_type="pptx", dispatch=lambda event: setattr(app, "active_tool", event)),
        _render_authoritative_state=lambda: None,
        render_shell_state=lambda: None,
    )
    MarkerApp.dispatch_shell_event(app, "badges")
    assert app.active_tool == "badges"


def test_pptx_language_projection_does_not_remount_or_clear_state():
    workspace = PptxWorkspace.__new__(PptxWorkspace)
    workspace.state = SimpleNamespace(loaded=True)
    workspace.choose_button = _Widget()
    workspace.save_button = _Widget()
    workspace.preview_label = _Widget()
    translator = SimpleNamespace(text=lambda key: {"pptx.choose": "Vælg PowerPoint", "pptx.preview_hint": "Forhåndsvisning"}[key])
    workspace.apply_language(translator)
    assert workspace.choose_button.values["text"] == "Vælg PowerPoint"
    assert workspace.save_button.values["text"] == "Save"
    assert workspace.preview_label.values["text"] == ""
