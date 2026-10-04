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


def test_image_workspace_owns_mount_and_lifecycle_contract():
    assert "def mount(self, host)" in WORKSPACE
    assert "self._build_ui(self.root)" in WORKSPACE
    assert "def unmount(self)" in WORKSPACE
    assert "def project(self)" in WORKSPACE
    assert "def has_active_work(self)" in WORKSPACE
    assert "def clear_runtime_state(self)" in WORKSPACE
    mount_start = APP.index("    def _mount_image_workspace")
    mount_end = APP.index("    def _mount_video_workspace", mount_start)
    mount = APP[mount_start:mount_end]
    assert "image_workspace_owner.mount(self.content_host)" in mount
    assert "CTkFrame" not in mount


def test_image_save_is_workspace_owned():
    assert "def save(self):" in WORKSPACE
    assert "ImageProcessingRequest" in WORKSPACE
    assert "filedialog.asksaveasfilename" in WORKSPACE
    builder_start = WORKSPACE.index("def _build_ui")
    assert "command=self.save" in WORKSPACE[builder_start:]


def test_image_registry_uses_workspace_lifecycle_object():
    assert '"image": self.image_workspace_owner' in APP
    assert "workspace.mount(self.content_host)" in APP
    assert '"image": self._mount_image_workspace' not in APP
