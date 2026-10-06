from pathlib import Path


ROOT = Path(__file__).parents[1] / "nenolink_ai_marker"


def test_image_badge_group_contains_badge_and_visual_controls_before_logo():
    source = (ROOT / "image_workspace.py").read_text(encoding="utf-8")
    assert "image_badge_group" in source
    assert "self.badge_control.frame.grid(row=0, column=0" in source
    assert "_slider(app.image_badge_group" in source
    assert "self.logo_control.frame.grid(row=12" in source


def test_video_badge_group_precedes_options_and_output():
    source = (ROOT / "video_workspace.py").read_text(encoding="utf-8")
    assert "video_badge_group" in source
    assert "_video_slider(app.video_badge_group" in source
    assert 'heading("VIDEO OPTIONS", 16)' in source
    assert 'heading("OUTPUT", 21)' in source
