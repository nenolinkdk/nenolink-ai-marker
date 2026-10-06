import inspect
from pathlib import Path

from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.workspace_state import PdfEvent, PdfWorkspaceState, apply_pdf_event


def test_pdf_scope_and_physical_page_are_independent():
    state = PdfWorkspaceState()
    apply_pdf_event(state, PdfEvent.FILE_SELECTED, {"path": Path("sample.pdf"), "page_count": 8})
    apply_pdf_event(state, PdfEvent.SCOPE_MODE, {"mode": "first"})
    scope = state.active_scope
    apply_pdf_event(state, PdfEvent.PREVIEW_PAGE_SELECTED, {"page": 4})
    assert state.current_page == 4
    assert state.active_scope == scope == (1,)


def test_pdf_processing_request_reads_workspace_state_not_tk_mirrors():
    source = inspect.getsource(PdfWorkspace.build_processing_request)
    assert "state.badge" in source
    assert "state.logo" in source
    assert "state.active_scope" in source
    assert "badge_var.get()" not in source
    assert "pdf_badge_enabled_var.get()" not in source


def test_pdf_badge_callbacks_do_not_fallback_to_tk_authority():
    visual = inspect.getsource(PdfWorkspace.visual_changed)
    select = inspect.getsource(PdfWorkspace.select_badge)
    assert "pdf_badge_enabled_var.get()" not in visual + select
    assert "self.state.badge.enabled" in visual + select
