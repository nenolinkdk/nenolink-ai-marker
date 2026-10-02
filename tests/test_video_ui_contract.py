from pathlib import Path


APP = Path(__file__).parents[1] / "nenolink_ai_marker" / "app.py"


def test_active_video_workspace_has_state_order_and_no_widget_class_labels():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def _mount_video_workspace(self)")
    end = source.index("    def _video_slider", start)
    active = source[start:end]
    assert active.index("self.video_open_button") < active.index("self.video_badge_enable")
    assert "self.video_badge_enable.grid(row=2" in active
    assert "self.video_mode_label.grid_configure(row=14" in active
    assert "self.video_process_button.grid_configure(row=17" in active
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
