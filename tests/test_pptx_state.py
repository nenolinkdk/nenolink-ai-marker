from pathlib import Path

from nenolink_ai_marker.pptx_state import PptxWorkspaceState


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
