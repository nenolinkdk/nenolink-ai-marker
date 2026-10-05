from pathlib import Path
ROOT=Path(__file__).parents[1]
APP=(ROOT/"nenolink_ai_marker"/"app.py").read_text(encoding="utf-8")
WS=(ROOT/"nenolink_ai_marker"/"video_workspace.py").read_text(encoding="utf-8")
def test_video_workspace_owns_ui_and_lifecycle():
    for token in ("class VideoWorkspace","def mount(self","def unmount(self)","def project(self)","def has_active_work(self)","def clear_runtime_state(self)","def _build_ui"):
        assert token in WS
def test_video_registry_uses_workspace_lifecycle_object():
    assert '"video": self.video_workspace_owner' in APP
    assert "workspace.mount(self.content_host)" in APP
    assert '"video": self._mount_video_workspace' not in APP
def test_video_callbacks_use_typed_events():
    for event in ("FILE_SELECTED","MODE_CHANGED","DURATION_CHANGED","BADGE_CHANGED","VISUAL_CHANGED"):
        assert f"VideoEvent.{event}" in WS
    assert "apply_video_event" in WS
def test_video_preview_uses_authoritative_state_and_ffmpeg():
    assert "self.state.path" in WS and "self.state.badge" in WS
    assert "extract_video_frame" in WS and "find_ffmpeg" in WS and "CTkImage" in WS
def test_video_save_uses_processing_request_from_state():
    assert "VideoProcessingRequest" in WS and "def save(self)" in WS
    for token in ("self.state.mode","self.state.duration","self.state.badge"):
        assert token in WS
def test_video_table_is_normative_for_all_events():
    from nenolink_ai_marker.workspace_state import VIDEO_TRANSITION_TABLE,VideoEvent,video_transition
    assert {x.event for x in VIDEO_TRANSITION_TABLE}==set(VideoEvent)
    for event in VideoEvent: assert video_transition(event).event is event
def test_video_legacy_mount_not_called_by_registry():
    assert "def _mount_video_workspace" in APP
    start=APP.index('"video": self.video_workspace_owner')
    assert 'self._mount_video_workspace' not in APP[start:start+120]
