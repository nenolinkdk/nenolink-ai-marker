from pathlib import Path

from nenolink_ai_marker.workspace_state import VideoEvent, VideoWorkspaceState, apply_video_event, video_transition
from nenolink_ai_marker.logo_control import LogoControl, LogoProjection
import inspect


def test_video_logo_events_are_table_backed_and_independent_from_badge():
    state = VideoWorkspaceState(path=Path("clip.mp4"))
    apply_video_event(state, VideoEvent.BADGE_CHANGED, {"badge_id": "ai-assisted.png", "enabled": True})
    apply_video_event(state, VideoEvent.LOGO_FILE_CHANGED, {"path": Path("logo.png"), "enabled": True})
    apply_video_event(state, VideoEvent.LOGO_MODE_CHANGED, {"mode": "front"})
    apply_video_event(state, VideoEvent.LOGO_SIZE_CHANGED, {"size": 30})
    apply_video_event(state, VideoEvent.LOGO_MARGIN_CHANGED, {"margin": 12})
    apply_video_event(state, VideoEvent.LOGO_OPACITY_CHANGED, {"opacity": 80})
    assert state.badge.badge_id == "ai-assisted.png"
    assert state.logo.path == Path("logo.png")
    assert state.logo.enabled and state.logo.mode == "front"
    assert state.logo.position == "top-left"
    assert state.logo.size == 30 and state.logo.margin == 12 and state.logo.opacity == 80
    assert video_transition(VideoEvent.LOGO_MODE_CHANGED).event is VideoEvent.LOGO_MODE_CHANGED


def test_video_logo_can_be_disabled_without_changing_badge():
    state = VideoWorkspaceState()
    state.badge.badge_id = "ai-assisted.png"
    apply_video_event(state, VideoEvent.LOGO_ENABLED_CHANGED, {"enabled": True})
    apply_video_event(state, VideoEvent.LOGO_ENABLED_CHANGED, {"enabled": False})
    assert state.logo.enabled is False
    assert state.badge.badge_id == "ai-assisted.png"


def test_logo_control_is_stateless_and_projects_video_capabilities():
    source = inspect.getsource(LogoControl)
    assert "WorkspaceState" not in source and "process_video" not in source
    assert "def project" in source
    projection = LogoProjection(enabled=True, filename="logo.png", mode="front", modes=("Front", "Entire", "Back"), position="top-left")
    assert projection.fixed_position is True and projection.modes == ("Front", "Entire", "Back")
