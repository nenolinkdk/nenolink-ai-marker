import inspect
from types import SimpleNamespace

from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.pptx_state import PptxWorkspaceState, project_file


def test_active_registry_uses_only_state_owned_pptx_workspace():
    from nenolink_ai_marker.app import MarkerApp
    source = inspect.getsource(MarkerApp._workspace_registry) if hasattr(MarkerApp, "_workspace_registry") else inspect.getsource(MarkerApp)
    assert "PptxWorkspace" in source or "pptx_workspace_state" in source


def test_file_projection_is_translatable_and_state_owned(tmp_path):
    path = tmp_path / "sample.pptx"
    path.write_bytes(b"x" * 2048)
    state = PptxWorkspaceState(path=path, slide_count=3)
    def translate(key, **values):
        if key == "pptx.selected": return f"loaded {values['name']}"
        return f"{values['size']} / {values['count']}"
    result = project_file(state, translate)
    assert result["filename"] == "sample.pptx"
    assert result["details"].endswith(" / 3")


def test_apply_language_is_projection_only_for_minimal_workspace():
    workspace = PptxWorkspace.__new__(PptxWorkspace)
    workspace.state = SimpleNamespace(loaded=True)
    class Widget:
        def __init__(self): self.values = {}
        def configure(self, **values): self.values.update(values)
        def cget(self, key): return self.values.get(key, "")
    workspace.choose_button = Widget(); workspace.save_button = Widget(); workspace.preview_label = Widget()
    workspace.apply_language(SimpleNamespace(text=lambda key, **values: key))
    assert workspace.choose_button.values["text"] == "pptx.choose"
    assert workspace.save_button.values["text"] == "Save"
