import inspect

from nenolink_ai_marker.video_workspace import VideoWorkspace


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
    source = inspect.getsource(VideoWorkspace.change_visual)
    assert "self.app.badge_enabled_var.get()" not in source
    assert "self.state.badge.enabled" in source
