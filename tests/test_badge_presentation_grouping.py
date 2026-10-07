from pathlib import Path


ROOT = Path(__file__).parents[1] / "nenolink_ai_marker"


def test_image_badge_group_contains_badge_and_visual_controls_before_logo():
    source = (ROOT / "image_workspace.py").read_text(encoding="utf-8")
    assert "image_badge_group" in source
    assert "self.badge_control.frame.grid(row=0, column=0" in source
    assert "_slider(app.image_badge_group" in source
    assert "self.logo_control.frame.grid(row=0, column=0" in source


def test_image_control_panel_is_the_only_outer_left_geometry_owner():
    source = (ROOT / "image_workspace.py").read_text(encoding="utf-8")
    assert source.count("WorkspaceControlPanel(") == 1
    assert 'add_section("FILE", file_section)' in source
    assert 'add_section("AI_BADGE", app.image_badge_group)' in source
    assert 'add_section("OWN_LOGO", logo_section)' in source
    assert source.index('add_section("FILE", file_section)') < source.index('add_section("AI_BADGE", app.image_badge_group)') < source.index('add_section("OWN_LOGO", logo_section)')
    assert "process_button.grid(row=4" not in source
    assert "image_badge_group.grid(row=2" not in source
    assert "logo_control.frame.grid(row=3" not in source


def test_video_badge_group_precedes_options_and_output():
    source = (ROOT / "video_workspace.py").read_text(encoding="utf-8")
    assert "video_badge_group" in source
    assert "_video_slider(app.video_badge_group" in source
    assert 'add_section("AI_BADGE", app.video_badge_group)' in source
    assert 'add_section("OWN_LOGO", logo_section)' in source
    assert 'add_section("VIDEO_OPTIONS", options_section)' in source
    assert 'SaveControl(file_section' in source


def test_all_workspace_panels_use_canonical_section_order():
    expected = {
        "image_workspace.py": ['"FILE", "AI_BADGE", "OWN_LOGO"'],
        "video_workspace.py": ['"FILE", "AI_BADGE", "OWN_LOGO", "VIDEO_OPTIONS"'],
        "pdf_workspace.py": ['"FILE", "PAGES", "AI_BADGE", "OWN_LOGO"'],
        "pptx_workspace.py": ['"FILE", "SLIDES", "AI_BADGE", "OWN_LOGO"'],
    }
    for filename, tokens in expected.items():
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "WorkspaceControlPanel" in source
        assert any(token in source for token in tokens)
