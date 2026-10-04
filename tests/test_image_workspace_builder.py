from pathlib import Path


ROOT = Path(__file__).parents[1]
APP = (ROOT / "nenolink_ai_marker" / "app.py").read_text(encoding="utf-8")
WORKSPACE = (ROOT / "nenolink_ai_marker" / "image_workspace.py").read_text(encoding="utf-8")


def test_image_workspace_owns_the_widget_builder():
    assert "class ImageWorkspace" in WORKSPACE
    assert "def _build_ui(self, workspace)" in WORKSPACE
    assert "CTkFrame" in WORKSPACE and "CTkButton" in WORKSPACE


def test_markerapp_builder_is_only_a_delegate():
    start = APP.index("    def _build_image_workspace(self)")
    end = APP.index("    def _image_slider", start)
    method = APP[start:end]
    assert "image_workspace_owner._build_ui" in method
    assert "CTkFrame" not in method
    assert "CTkButton" not in method


def test_builder_receives_existing_image_state():
    assert "self.image_workspace_owner = ImageWorkspace(" in APP
    assert "self, self.image_state" in APP
    assert "self.state = state" in WORKSPACE
