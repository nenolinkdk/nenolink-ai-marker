from copy import deepcopy
from pathlib import Path

import pytest

from nenolink_ai_marker.pptx_state import (
    PptxEvent, PptxWorkspaceState, apply_pptx_scope_event,
    apply_pptx_visual_event, choose_file_success, project_file,
)


def snapshot(state):
    return {"path": state.path, "slide_count": state.slide_count,
            "current_slide": state.current_slide, "scope_mode": state.scope_mode,
            "active_scope": state.active_scope, "scope_input": state.scope_input,
            "badge": deepcopy(state.badge.__dict__), "logo": deepcopy(state.logo.__dict__),
            "output_status": state.output_status}


@pytest.fixture
def loaded():
    state = PptxWorkspaceState()
    choose_file_success(state, Path("deck.pptx"), 10)
    state.current_slide = 4
    state.scope_mode, state.scope_input, state.active_scope = "selected", "2,4-6", (2, 4, 5, 6)
    return state


@pytest.mark.parametrize("event,value,owned,group", [
    (PptxEvent.BADGE_ENABLE, False, "enabled", "badge"),
    (PptxEvent.BADGE_SELECT, "AI Translation", "badge_id", "badge"),
    (PptxEvent.BADGE_POSITION, "top-left", "position", "badge"),
    (PptxEvent.BADGE_SIZE, 33, "size", "badge"),
    (PptxEvent.BADGE_MARGIN, 44, "margin", "badge"),
    (PptxEvent.BADGE_OPACITY, 55, "opacity", "badge"),
    (PptxEvent.LOGO_ENABLE, True, "enabled", "logo"),
    (PptxEvent.LOGO_CHOOSE, "logo.png", "path", "logo"),
    (PptxEvent.LOGO_POSITION, "bottom-right", "position", "logo"),
    (PptxEvent.LOGO_SIZE, 33, "size", "logo"),
    (PptxEvent.LOGO_MARGIN, 44, "margin", "logo"),
    (PptxEvent.LOGO_OPACITY, 55, "opacity", "logo"),
])
def test_visual_event_ownership_matrix(loaded, event, value, owned, group):
    before = snapshot(loaded)
    apply_pptx_visual_event(loaded, event, value)
    after = snapshot(loaded)
    assert after[group][owned] != before[group][owned]
    for key in before:
        if key != group:
            assert after[key] == before[key]
    for key in before[group]:
        if key != owned:
            assert after[group][key] == before[group][key]


def test_scope_and_preview_ownership(loaded):
    before = snapshot(loaded)
    apply_pptx_scope_event(loaded, PptxEvent.SCOPE_TEXT_CHANGED, "7,9")
    assert loaded.scope_input == "7,9" and loaded.active_scope == before["active_scope"]
    apply_pptx_scope_event(loaded, PptxEvent.SCOPE_UPDATE, "7,9")
    assert loaded.active_scope == (7, 9) and loaded.current_slide == 7
    apply_pptx_scope_event(loaded, PptxEvent.PREVIEW_NEXT)
    assert loaded.current_slide == 8 and loaded.active_scope == (7, 9)
    assert loaded.path == before["path"] and loaded.badge.__dict__ == before["badge"]


def test_file_projection_and_hard_reset(loaded):
    loaded.path = Path("other.pptx")
    assert project_file(loaded)["filename"] == "other.pptx"
    loaded.clear()
    assert loaded.path is None and loaded.slide_count == 0 and loaded.current_slide == 1
    assert loaded.active_scope == () and loaded.scope_input == "" and loaded.output_status == ""


def test_visual_projection_is_authoritative(loaded):
    projection = loaded.visual_projection()
    assert projection["path"] == loaded.path
    assert projection["scope"] == loaded.active_scope
    assert projection["badge"]["size"] == loaded.badge.size
    assert projection["logo"]["opacity"] == loaded.logo.opacity
