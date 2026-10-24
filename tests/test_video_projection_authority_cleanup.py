import inspect
from pathlib import Path
from types import SimpleNamespace

from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.workspace_state import VideoWorkspaceState


def test_video_projection_uses_authoritative_mode_duration_and_badge():
    source = inspect.getsource(VideoWorkspace._project_controls)
    assert "self.state.mode" in source
    assert "self.state.duration" in source
    assert "self.state.badge.badge_id" in source


def test_video_save_request_uses_workspace_state_not_tk_mirrors():
    source = inspect.getsource(VideoWorkspace.save)
    assert "self.state.mode" in source
    assert "self.state.duration" in source
    assert "self.app.video_mode_var.get()" not in source
    assert "self.app.video_duration_var.get()" not in source


def test_video_badge_callback_does_not_fallback_to_global_badge_authority():
    state = VideoWorkspaceState(path=Path("clip.mp4"))
    state.badge.enabled = False
    workspace = VideoWorkspace.__new__(VideoWorkspace)
    workspace.app = SimpleNamespace()
    workspace.state = state
    workspace.project = lambda: None
    workspace.refresh_preview = lambda: None

    workspace.change_visual(35)
    assert state.badge.enabled is False
    workspace.change_visual(True)
    assert state.badge.enabled is True
