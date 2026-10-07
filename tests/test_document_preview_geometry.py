from pathlib import Path

import pytest

from nenolink_ai_marker.document_preview_layout import fit_preview_geometry


def test_geometry_receipt_portrait_uses_height_limit():
    receipt = fit_preview_geometry(1000, 800, 595, 842)
    assert receipt.limiting_dimension == "height"
    assert abs(receipt.measured_fraction - 0.8) <= 0.01
    assert receipt.rendered_height / receipt.rendered_width == pytest.approx(842 / 595, rel=0.01)


def test_geometry_receipt_landscape_uses_width_limit():
    receipt = fit_preview_geometry(1000, 800, 16, 9)
    assert receipt.limiting_dimension == "width"
    assert abs(receipt.measured_fraction - 0.8) <= 0.01


def test_active_pdf_pptx_paths_use_measured_viewport_geometry():
    root = Path(__file__).parents[1] / "nenolink_ai_marker"
    pdf = (root / "pdf_workspace.py").read_text(encoding="utf-8")
    pptx = (root / "pptx_workspace.py").read_text(encoding="utf-8")
    assert "host.winfo_width()" in pdf
    assert "host.winfo_height()" in pdf
    assert "fit_preview_geometry(width, height" in pdf
    assert "self.preview_viewport.winfo_width()" in pptx
    assert "self.preview_viewport.winfo_height()" in pptx
    assert "fit_preview_geometry(viewport_width, viewport_height" in pptx
    assert "target_fraction=0.8" in pdf and "target_fraction=0.8" in pptx
