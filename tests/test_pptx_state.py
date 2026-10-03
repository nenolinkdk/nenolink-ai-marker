from pathlib import Path

import pytest
from nenolink_ai_marker.pptx_state import (PptxWorkspaceState, PptxEvent, PPTX_TRANSITION_TABLE,
    apply_pptx_visual_event, apply_pptx_scope_event, normalize_scope)


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


def test_scope_defaults_and_immediate_modes():
    state = PptxWorkspaceState(Path("deck.pptx"), 10)
    apply_pptx_scope_event(state, PptxEvent.SCOPE_MODE, "all")
    assert state.active_scope == tuple(range(1, 11))
    apply_pptx_scope_event(state, PptxEvent.SCOPE_MODE, "first")
    assert state.active_scope == (1,) and state.current_slide == 1


@pytest.mark.parametrize("mode,text,expected", [
    ("selected", "2,4-6,9", (2, 4, 5, 6, 9)),
    ("range", "5-7,10-12", (5, 6, 7, 10, 11, 12)),
])
def test_scope_update_normalizes_without_mutating_file_or_badge(mode, text, expected):
    state = PptxWorkspaceState(Path("deck.pptx"), 12, 8, "all", tuple(range(1, 13)))
    badge = state.badge.__dict__.copy()
    apply_pptx_scope_event(state, PptxEvent.SCOPE_MODE, mode)
    apply_pptx_scope_event(state, PptxEvent.SCOPE_TEXT_CHANGED, text)
    assert state.active_scope == tuple(range(1, 13))
    apply_pptx_scope_event(state, PptxEvent.SCOPE_UPDATE, text)
    assert state.active_scope == expected and state.current_slide == expected[0]
    assert state.path == Path("deck.pptx") and state.badge.__dict__ == badge


@pytest.mark.parametrize("mode,text", [("selected", ""), ("selected", "0"), ("selected", "8-4"), ("selected", "13"), ("range", "4")])
def test_invalid_scope_preserves_last_valid_scope(mode, text):
    state = PptxWorkspaceState(Path("deck.pptx"), 12, 6, "selected", (2, 4), "2,4")
    before = (state.active_scope, state.current_slide)
    with pytest.raises(ValueError):
        normalize_scope(mode, text, state.slide_count)
    assert (state.active_scope, state.current_slide) == before
