import inspect

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.image_workspace import ImageWorkspace


def test_image_translation_does_not_overwrite_badge_control_graphic():
    source = inspect.getsource(MarkerApp.apply_image_translations)
    assert "_update_badge_controls" not in source
    assert "single_badge_preview_label" not in source


def test_image_badge_projection_is_workspace_owned():
    source = inspect.getsource(ImageWorkspace.project)
    assert "BadgeProjection" in source
    assert "single_badge_photo" not in source


def test_image_position_label_is_inside_badge_section():
    source = inspect.getsource(ImageWorkspace._build_ui)
    assert "app.position_label = ctk.CTkLabel(app.image_badge_group)" in source
