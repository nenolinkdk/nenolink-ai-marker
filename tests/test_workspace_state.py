from pathlib import Path

from nenolink_ai_marker.workspace_state import (
    BadgeVisualState, LogoVisualState, WorkspaceEvent, WorkspaceRuntimeState,
    visual_projection,
)


def test_badge_and_logo_state_are_independent():
    state = WorkspaceRuntimeState(Path("source.png"), BadgeVisualState(badge_id="a"), LogoVisualState(path=Path("logo.png")))
    before_logo = state.logo
    state.badge.size = 42; state.badge.opacity = 35
    assert state.logo == before_logo and state.path == Path("source.png")


def test_logo_changes_do_not_mutate_badge_or_file():
    state = WorkspaceRuntimeState(Path("source.png"), BadgeVisualState(badge_id="a"), LogoVisualState())
    before_badge = state.badge
    state.logo.enabled = True; state.logo.margin = 77
    assert state.badge == before_badge and state.path == Path("source.png")


def test_runtime_clear_only_clears_runtime_file_and_output():
    state = WorkspaceRuntimeState(Path("source.png"), output_status="saved")
    state.clear_runtime_state()
    assert not state.has_active_work() and state.output_status == ""
    assert state.badge is not None and state.logo is not None


def test_visual_projection_is_shared_preview_output_input():
    state = WorkspaceRuntimeState(Path("source.png"), BadgeVisualState(size=42), LogoVisualState(opacity=55))
    preview, output = visual_projection(state)
    assert preview == state.badge and output == state.logo
    assert preview is not state.badge and output is not state.logo


def test_common_contract_has_no_document_scope():
    assert not hasattr(WorkspaceRuntimeState, "active_scope")
    assert WorkspaceEvent.BADGE_SIZE_CHANGED.value == "badge_size_changed"
