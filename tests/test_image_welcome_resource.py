from pathlib import Path

from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.paths import welcome_image_path


def test_image_workspace_uses_current_welcome_resource_resolver():
    source = Path("nenolink_ai_marker/image_workspace.py")
    assert welcome_image_path().name == "welcome-europe.png"
    assert "welcome_image_path" in source.read_text(encoding="utf-8")
