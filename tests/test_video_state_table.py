from pathlib import Path
from types import SimpleNamespace
import pytest

from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.workspace_state import (
    VIDEO_TRANSITION_TABLE, VideoEvent, VideoWorkspaceState,
    apply_video_event, video_transition,
)


def snap(state):
    return (state.path, state.mode, state.duration, state.badge.__dict__.copy(), state.logo.__dict__.copy())


@pytest.mark.parametrize("spec", VIDEO_TRANSITION_TABLE)
def test_every_video_table_transition_executes(spec):
    assert video_transition(spec.event) is spec
    state = VideoWorkspaceState(path=Path("clip.mp4"), mode="permanent", duration=5)
    before = snap(state)
    payload = {
        VideoEvent.FILE_SELECTED: {"path": Path("new.mp4")},
        VideoEvent.MODE_CHANGED: {"mode": "end"},
        VideoEvent.DURATION_CHANGED: {"duration": 8},
        VideoEvent.BADGE_CHANGED: {"badge_id": "AI Translation"},
        VideoEvent.VISUAL_CHANGED: {"size": 35, "margin": 22},
        VideoEvent.CLEAR_RUNTIME: {},
    }[spec.event]
    assert apply_video_event(state, spec.event, payload) is state
    if spec.event is VideoEvent.BADGE_CHANGED:
        assert state.path == before[0] and state.mode == before[1] and state.duration == before[2]
    if spec.event is VideoEvent.MODE_CHANGED:
        assert state.path == before[0] and state.badge.__dict__ == before[3]
    if spec.event is VideoEvent.DURATION_CHANGED:
        assert state.path == before[0] and state.badge.__dict__ == before[3]


def test_real_video_callback_seam_dispatches_reducer():
    state = VideoWorkspaceState(path=Path("clip.mp4"))
    app = SimpleNamespace(
        video_mode_display_to_value={"End": "end"},
        _update_video_duration_visibility=lambda: None,
        _save_image_settings=lambda: None,
    )
    workspace = VideoWorkspace.__new__(VideoWorkspace)
    workspace.app = app; workspace.state = state
    workspace.project = lambda: None
    workspace.change_mode("End")
    assert state.mode == "end" and state.path == Path("clip.mp4")


def test_video_clear_preserves_visual_preferences():
    state = VideoWorkspaceState(path=Path("clip.mp4"))
    state.badge.badge_id = "AI Assisted"
    apply_video_event(state, VideoEvent.CLEAR_RUNTIME)
    assert state.path is None and state.badge.badge_id == "AI Assisted"
