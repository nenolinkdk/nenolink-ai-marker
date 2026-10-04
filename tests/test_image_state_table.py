from pathlib import Path
from types import SimpleNamespace

import pytest

from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.workspace_state import (
    IMAGE_TRANSITION_TABLE,
    ImageEvent,
    ImageWorkspaceState,
    apply_image_event,
    image_transition,
)


def snapshot(state):
    return (state.path, state.selected_files, state.badge.__dict__.copy(), state.logo.__dict__.copy(), state.output_status)


@pytest.mark.parametrize("spec", IMAGE_TRANSITION_TABLE)
def test_every_image_table_transition_executes(spec):
    assert image_transition(spec.event) is spec
    state = ImageWorkspaceState(path=Path("one.png"), selected_files=(Path("one.png"),))
    before = snapshot(state)
    payload = {
        ImageEvent.FILE_SELECTED: {"files": (Path("two.png"),)},
        ImageEvent.BADGE_CHANGED: {"badge_id": "AI Translation"},
        ImageEvent.LOGO_CHANGED: {"enabled": True, "path": Path("logo.png")},
        ImageEvent.VISUAL_CHANGED: {"size": 35, "logo_size": 25},
        ImageEvent.CLEAR_RUNTIME: {},
    }[spec.event]
    result = apply_image_event(state, spec.event, payload)
    assert result is state
    if spec.event is ImageEvent.BADGE_CHANGED:
        assert state.selected_files == before[1] and state.logo.__dict__ == before[3]
    if spec.event is ImageEvent.LOGO_CHANGED:
        assert state.selected_files == before[1] and state.badge.__dict__ == before[2]


def test_file_event_preserves_visual_state():
    state = ImageWorkspaceState()
    state.badge.badge_id = "AI Assisted"
    state.logo.path = Path("logo.png")
    apply_image_event(state, ImageEvent.FILE_SELECTED, {"files": (Path("new.png"),)})
    assert state.path == Path("new.png")
    assert state.badge.badge_id == "AI Assisted"
    assert state.logo.path == Path("logo.png")


def test_real_image_callback_seam_dispatches_reducer(monkeypatch):
    state = ImageWorkspaceState(path=Path("one.png"), selected_files=(Path("one.png"),))
    app = SimpleNamespace(
        badge_var=SimpleNamespace(get=lambda: "AI Translation"),
        _project_image_visual_state=lambda: None,
    )
    workspace = ImageWorkspace.__new__(ImageWorkspace)
    workspace.app = app
    workspace.state = state
    workspace.refresh_preview = lambda: None
    workspace.badge_changed()
    assert state.badge.badge_id == "AI Translation"
    assert state.path == Path("one.png")


def test_clear_is_table_driven_and_preserves_visual_preferences():
    state = ImageWorkspaceState(path=Path("one.png"), selected_files=(Path("one.png"),))
    state.badge.badge_id = "AI Assisted"
    apply_image_event(state, ImageEvent.CLEAR_RUNTIME)
    assert state.path is None and state.selected_files == ()
    assert state.badge.badge_id == "AI Assisted"
