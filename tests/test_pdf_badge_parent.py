from pathlib import Path


PDF_WORKSPACE = Path(__file__).parents[1] / "nenolink_ai_marker" / "pdf_workspace.py"


def test_pdf_badge_control_is_constructed_from_controls_container():
    source = PDF_WORKSPACE.read_text(encoding="utf-8")
    assert "BadgeControl(host" not in source
    assert "controls = self.control_panel.frame" in source
    controls_index = source.index("controls = self.control_panel.frame")
    badge_index = source.index("self.badge_control = BadgeControl(badge_section")
    assert controls_index < badge_index
