from pathlib import Path


PDF_WORKSPACE = Path(__file__).parents[1] / "nenolink_ai_marker" / "pdf_workspace.py"


def test_pdf_badge_control_is_constructed_from_controls_container():
    source = PDF_WORKSPACE.read_text(encoding="utf-8")
    assert "BadgeControl(host" not in source
    assert "controls = ctk.CTkScrollableFrame" in source
    controls_index = source.index("controls = ctk.CTkScrollableFrame")
    badge_index = source.index("self.badge_control = BadgeControl(controls")
    assert controls_index < badge_index
