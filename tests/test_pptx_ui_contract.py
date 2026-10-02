from pathlib import Path


APP = Path(__file__).parents[1] / "nenolink_ai_marker" / "app.py"
SOURCE = APP.read_text(encoding="utf-8")


def test_pptx_workspace_has_common_sections_and_human_labels():
    mount = SOURCE[SOURCE.index("def _mount_pptx_workspace"):SOURCE.index("def pptx_visual_changed")]
    for label in ("PowerPoint", "SLIDES", "AI BADGE", "OWN LOGO", "Choose PowerPoint"):
        assert label in mount
    for label in ("Size", "Margin", "Opacity"):
        assert label in mount


def test_pptx_badge_uses_common_repository_and_projects_graphic():
    assert "self.refresh_image_badges()" in SOURCE
    assert "def _project_pptx_badge_visual" in SOURCE
    assert "self.pptx_badge_photo" in SOURCE
    assert "self.badges.find(badge_id)" in SOURCE


def test_pptx_preview_and_output_share_authoritative_projection():
    assert "def _pptx_visual_projection_settings" in SOURCE
    preview = SOURCE[SOURCE.index("def _update_pptx_preview"):SOURCE.index("def change_pptx_slide")]
    process = SOURCE[SOURCE.index("def process_pptx"):SOURCE.index("def _render_update_notification")]
    assert "_pptx_visual_projection_settings()" in preview
    assert "_pptx_visual_projection_settings()" in process
    assert "self.pptx_state.active_scope" in preview


def test_pptx_scope_and_physical_navigation_are_separate():
    assert "self.pptx_current_slide" in SOURCE
    assert "self.pptx_state.active_scope" in SOURCE
    assert "self.pptx_state.current_slide" in SOURCE
    assert "self.pptx_state.scope_mode" in SOURCE


def test_pptx_badge_selection_routes_through_projection_without_remount():
    selection = SOURCE[SOURCE.index("def select_badge"):SOURCE.index("def select_badge_display")]
    assert "_project_pptx_badge_visual()" in selection
    assert "_update_pptx_preview()" in selection
    assert "_mount_pptx_workspace" not in selection


def test_common_presentation_builders_are_stateless_callback_adapters():
    ui = (Path(__file__).parents[1] / "nenolink_ai_marker" / "workspace_ui.py").read_text(encoding="utf-8")
    assert "def build_badge_section" in ui
    assert "def build_logo_section" in ui
    assert "on_enabled" in ui and "on_selected" in ui
    assert "on_choose" in ui and "on_position" in ui
    assert "WORKSPACE_LAYOUT" in ui


def test_pptx_file_row_exposes_save_and_common_order():
    mount = SOURCE[SOURCE.index("def _mount_pptx_workspace"):SOURCE.index("def pptx_visual_changed")]
    assert 'text="Save Marked PowerPoint..."' in mount
    assert mount.index("Choose PowerPoint") < mount.index("SLIDES") < mount.index("AI BADGE") < mount.index("OWN LOGO")


def test_authoritative_shell_mounts_complete_pptx_workspace_not_placeholder():
    render = SOURCE[SOURCE.index("def _render_authoritative_state"):SOURCE.index("def _format_has_active_work")]
    assert "self._mount_pptx_workspace()" in render
    assert "PPTX TEST" not in render
