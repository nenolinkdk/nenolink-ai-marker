from pathlib import Path


ROOT = Path(__file__).parents[1] / "nenolink_ai_marker"


def test_current_workspace_presentation_attributes_have_local_owners():
    image = (ROOT / "image_workspace.py").read_text(encoding="utf-8")
    assert "self.preview_label = ctk.CTkLabel" in image
    assert "app.preview_label" not in image
    assert "PreviewShell(workspace)" in image

