from pathlib import Path


APP = Path(__file__).parents[1] / "nenolink_ai_marker" / "app.py"


def test_active_video_workspace_has_state_order_and_no_widget_class_labels():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def _mount_video_workspace(self)")
    end = source.index("    def _video_slider", start)
    active = source[start:end]
    assert active.index('heading("FILE"') < active.index('heading("AI BADGE"') < active.index('heading("VIDEO OPTIONS"') < active.index('heading("OUTPUT"')
    assert 'text="Add AI badge"' in active
    assert 'text="Video preview"' in active
    assert 'text="Save Marked Video..."' in active
    for forbidden in ("CTkButton", "CTkCheckBox", "CTkLabel", "CTkSlider"):
        assert f'text="{forbidden}"' not in active


def test_active_video_preview_uses_ffmpeg_and_retains_ctk_image():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def _render_video_preview")
    end = source.index("    def open_video", start)
    active = source[start:end]
    assert "find_ffmpeg()" in active
    assert "extract_video_frame" in active
    assert "self.video_preview_photo=ctk.CTkImage" in active
    assert "self.video_preview_label.image=self.video_preview_photo" in active


def test_video_mount_owns_two_fresh_hosts_and_clears_common_host():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def _mount_video_workspace(self)")
    end = source.index("    def _video_slider", start)
    active = source[start:end]
    assert "self._clear_content_host()" in active
    assert "self.video_controls_host = left" in active
    assert "self.video_preview_host = right" in active
    assert "grid_columnconfigure(0, weight=0, minsize=320)" in active
    assert "grid_columnconfigure(1, weight=1)" in active


def test_video_file_selection_does_not_rebuild_workspace():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def open_video(self)")
    end = source.index("    def save_video", start)
    handler = source[start:end]
    assert "self.video_state.path = path" in handler
    assert "self.video_sources = [path]" in handler
    assert "_mount_video_workspace" not in handler
    assert "video_controls_host" not in handler
    assert "video_preview_host" not in handler


def test_video_selection_renders_existing_preview_without_remounting():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def open_video(self)")
    end = source.index("    def save_video", start)
    handler = source[start:end]
    assert "self.video_workspace_owner.refresh_preview()" in handler
    assert "_mount_video_workspace" not in handler


def test_video_visual_events_rerender_projection():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def change_video_position")
    end = source.index("    def _sync_video_state", start)
    handlers = source[start:end]
    assert handlers.count("self.video_workspace_owner.refresh_preview()") >= 3
    assert "def _project_video_state" in source
    assert "self.video_state.badge.size = int(self.video_size_var.get())" in source


def test_video_preview_uses_authoritative_badge_state():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def _render_video_preview")
    end = source.index("    def open_video", start)
    renderer = source[start:end]
    assert "state=self.video_state" in renderer
    assert "state.badge.enabled" in renderer
    assert "self.video_preview_photo=ctk.CTkImage" in renderer


def test_video_save_is_bound_to_save_as_and_protects_source():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def save_video(self)")
    end = source.index("    def _build_badges_tool", start)
    handler = source[start:end]
    assert "filedialog.asksaveasfilename" in handler
    assert 'initialfile=suggested.name' in handler
    assert 'target_path.resolve() == source.resolve()' in handler
    assert "process_video(source, badge, Path(target)" in handler
    assert "_mount_video_workspace" not in handler


def test_video_save_uses_authoritative_state_values():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def save_video(self)")
    end = source.index("    def _build_badges_tool", start)
    handler = source[start:end]
    for value in ("self.video_state.badge.position", "self.video_state.badge.size", "self.video_state.badge.margin", "self.video_state.badge.opacity", "self.video_state.mode", "self.video_state.duration"):
        assert value in handler
