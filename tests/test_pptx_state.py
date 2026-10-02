from pathlib import Path

import pytest
from nenolink_ai_marker.pptx_state import PptxWorkspaceState, PptxEvent, PPTX_TRANSITION_TABLE, apply_pptx_visual_event


def test_pptx_state_keeps_physical_preview_and_scope_independent():
    state = PptxWorkspaceState(Path("deck.pptx"), 10, 7, "selected", (3, 7), "3,7")
    state.badge.size = 42
    state.logo.opacity = 55
    assert state.current_slide == 7 and state.active_scope == (3, 7)
    assert state.badge.size == 42 and state.logo.opacity == 55


def test_pptx_state_clear_is_unconditional():
    state = PptxWorkspaceState(Path("deck.pptx"), 4, 2, "first", (1,), "")
    state.clear()
    assert not state.loaded and state.current_slide == 1
    assert state.scope_mode == "all" and state.active_scope == ()


@pytest.mark.parametrize("spec", PPTX_TRANSITION_TABLE)
def test_transition_table_declares_effects(spec):
    assert spec.event in PptxEvent
    assert spec.remount is False
    if spec.event.name.startswith("BADGE_"):
        assert all("logo" not in field for field in spec.mutates)
    if spec.event.name.startswith("LOGO_"):
        assert all("badge" not in field for field in spec.mutates)


@pytest.mark.parametrize("event,value,field", [
    (PptxEvent.BADGE_SIZE, 44, "size"), (PptxEvent.BADGE_MARGIN, 33, "margin"),
    (PptxEvent.BADGE_OPACITY, 77, "opacity"), (PptxEvent.LOGO_SIZE, 22, "size"),
    (PptxEvent.LOGO_MARGIN, 18, "margin"), (PptxEvent.LOGO_OPACITY, 66, "opacity"),
])
def test_visual_reducer_mutates_only_its_target(event, value, field):
    state = PptxWorkspaceState(Path("deck.pptx"), 10, 7, "selected", (3, 7), "3,7")
    before_path, before_slide, before_scope = state.path, state.current_slide, state.active_scope
    before_other = state.logo.__dict__.copy() if event.name.startswith("BADGE") else state.badge.__dict__.copy()
    apply_pptx_visual_event(state, event, value)
    target = state.badge if event.name.startswith("BADGE") else state.logo
    assert getattr(target, field) == value
    assert (state.path, state.current_slide, state.active_scope) == (before_path, before_slide, before_scope)
    other = state.logo if event.name.startswith("BADGE") else state.badge
    assert other.__dict__ == before_other
