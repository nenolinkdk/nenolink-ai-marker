import inspect
from pathlib import Path

from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.pptx_state import PptxEvent, PptxWorkspaceState, apply_pptx_event


def test_pptx_scope_and_physical_slide_are_independent():
    state = PptxWorkspaceState()
    apply_pptx_event(state, PptxEvent.CHOOSE_FILE, (Path("sample.pptx"), 8))
    apply_pptx_event(state, PptxEvent.SCOPE_MODE, "first")
    scope = state.active_scope
    apply_pptx_event(state, PptxEvent.PREVIEW_NEXT)
    assert state.current_slide == 2
    assert state.active_scope == scope == (1,)


def test_pptx_save_route_is_workspace_owned():
    source = inspect.getsource(PptxWorkspace._save_as)
    assert "self.state.path" in source
    assert "asksaveasfilename" in source
    assert "pptx_processor.process" in source
    assert "process_pptx_from_workspace" not in source
    assert "pptx_selection_mode_var.get()" not in source
    assert "pptx_selected_var.get()" not in source
    assert "pptx_range_var.get()" not in source


def test_pptx_projection_and_preview_use_workspace_state():
    project = inspect.getsource(PptxWorkspace._project_badge)
    preview = inspect.getsource(PptxWorkspace._render_preview)
    assert "self.state.badge" in project
    assert "self.state.current_slide" in preview
    assert "self.state.active_scope" in preview
