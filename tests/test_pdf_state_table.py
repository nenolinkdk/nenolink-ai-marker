from pathlib import Path
import pytest

from nenolink_ai_marker.workspace_state import (
    PDF_TRANSITION_TABLE, PdfEvent, PdfWorkspaceState,
    apply_pdf_event, pdf_transition,
)


@pytest.mark.parametrize("spec", PDF_TRANSITION_TABLE)
def test_every_pdf_table_transition_executes(spec):
    assert pdf_transition(spec.event) is spec
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=6, current_page=2, active_scope=(2, 4))
    payloads = {
        PdfEvent.FILE_SELECTED: {"path": Path("new.pdf"), "page_count": 4},
        PdfEvent.SCOPE_MODE: {"mode": "selected"},
        PdfEvent.SCOPE_TEXT_CHANGED: {"text": "2,4"},
        PdfEvent.SCOPE_UPDATE: {"values": (2, 4), "text": "2,4"},
        PdfEvent.PREVIEW_PREVIOUS: {}, PdfEvent.PREVIEW_NEXT: {},
        PdfEvent.PREVIEW_PAGE_SELECTED: {"page": 3},
        PdfEvent.BADGE_CHANGED: {"badge_id": "AI Translation"},
        PdfEvent.LOGO_CHANGED: {"enabled": True, "path": Path("logo.png")},
        PdfEvent.VISUAL_CHANGED: {"size": 35, "logo_size": 25},
        PdfEvent.CLEAR_RUNTIME: {},
    }
    apply_pdf_event(state, spec.event, payloads[spec.event])
    assert state is not None


def test_pdf_draft_edit_does_not_change_effective_scope():
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=6, current_page=2, scope_mode="selected", scope_input="2", active_scope=(2,))
    apply_pdf_event(state, PdfEvent.SCOPE_TEXT_CHANGED, {"text": "3,5"})
    assert state.scope_input == "3,5" and state.active_scope == (2,) and state.current_page == 2


def test_pdf_invalid_update_preserves_scope_and_page():
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=6, current_page=2, scope_mode="selected", scope_input="2", active_scope=(2,))
    with pytest.raises(ValueError):
        apply_pdf_event(state, PdfEvent.SCOPE_UPDATE, {"values": (9,), "text": "9"})
    assert state.active_scope == (2,) and state.current_page == 2


def test_pdf_physical_navigation_preserves_scope():
    state = PdfWorkspaceState(path=Path("doc.pdf"), page_count=10, current_page=2, active_scope=(2, 7))
    apply_pdf_event(state, PdfEvent.PREVIEW_NEXT)
    assert state.current_page == 3 and state.active_scope == (2, 7)


def test_pdf_file_replacement_resets_document_scope_preserves_visuals():
    state = PdfWorkspaceState(path=Path("old.pdf"), page_count=8, current_page=5, active_scope=(2, 7))
    state.badge.badge_id = "AI Assisted"
    apply_pdf_event(state, PdfEvent.FILE_SELECTED, {"path": Path("new.pdf"), "page_count": 3})
    assert state.path == Path("new.pdf") and state.page_count == 3 and state.current_page == 1
    assert state.active_scope == (1, 2, 3) and state.badge.badge_id == "AI Assisted"
