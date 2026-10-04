"""Regression reproductions for packaged-runtime callback divergences.

These tests intentionally describe the expected callback contract and remain
red until the production callback/projection defects are repaired.
"""
from pathlib import Path
from types import SimpleNamespace

from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.workspace_state import ImageWorkspaceState


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _image_app():
    return SimpleNamespace(
        badge_enabled_var=_Var(True), badge_var=_Var("ai-assisted.png"),
        badge_display_var=_Var("AI Assisted"), position_var=_Var("bottom-right"),
        badge_display_to_file={"AI Assisted": "ai-assisted.png", "AI Translation": "ai-translation.png"},
        size_var=_Var(20), margin_var=_Var(20), opacity_var=_Var(100),
        logo_enabled_var=_Var(False), logo_position_var=_Var("bottom-right"),
        logo_size_var=_Var(20), logo_margin_var=_Var(20), logo_opacity_var=_Var(100),
        _logo_path=lambda: None,
        _project_image_visual_state=lambda: None,
    )


def test_image_badge_checkbox_callback_updates_authoritative_enabled_state():
    app = _image_app(); state = ImageWorkspaceState(); workspace = ImageWorkspace.__new__(ImageWorkspace)
    workspace.app = app; workspace.state = state
    workspace.refresh_preview = lambda: None
    app.badge_enabled_var.set(False)
    workspace.visual_changed()
    assert state.badge.enabled is False


def test_image_badge_selector_callback_uses_projected_selection():
    app = _image_app(); state = ImageWorkspaceState(); workspace = ImageWorkspace.__new__(ImageWorkspace)
    workspace.app = app; workspace.state = state
    workspace.refresh_preview = lambda: None
    app.badge_display_var.set("AI Translation")
    workspace.badge_changed()
    assert state.badge.badge_id == "ai-translation.png"


def test_image_badge_change_reaches_preview_from_authoritative_state():
    app = _image_app(); state = ImageWorkspaceState(selected_files=(Path("photo.jpg"),))
    workspace = ImageWorkspace.__new__(ImageWorkspace); workspace.app = app; workspace.state = state
    workspace.refresh_preview = lambda: None
    app.badge_display_var.set("AI Translation")
    workspace.badge_changed()
    assert state.badge.badge_id == "ai-translation.png"
