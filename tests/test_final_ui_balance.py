from pathlib import Path

ROOT = Path(__file__).parents[1] / "nenolink_ai_marker"

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")

def test_workspaces_use_stable_left_columns_and_preview_shells():
    for name in ("image_workspace.py", "video_workspace.py", "pdf_workspace.py", "pptx_workspace.py"):
        source = read(name)
        assert "PreviewShell" in source
        assert "minsize=320" in source or "minsize=360" in source or "width=320" in source or "width=360" in source

def test_common_section_order_is_present():
    image, video, pdf, pptx = (read(n) for n in ("image_workspace.py", "video_workspace.py", "pdf_workspace.py", "pptx_workspace.py"))
    assert image.index("SourceControl") < image.index("LogoControl")
    assert video.index("SourceControl") < video.index("LogoControl")
    assert "self.source_control = SourceControl" in pdf and "self.scope_control = DocumentScopeControl" in pdf
    assert "self.logo_control = LogoControl" in pdf
    assert "self.source_control = SourceControl" in pptx and "self.scope_control = DocumentScopeControl" in pptx
    assert "self.logo_control = LogoControl" in pptx

def test_pdf_pptx_scope_and_physical_navigation_are_separate_components():
    for name in ("pdf_workspace.py", "pptx_workspace.py"):
        source = read(name)
        assert "DocumentScopeControl" in source
        assert "PhysicalNavigationControl" in source
        assert "PreviewShell" in source

def test_video_temporal_logo_contract_remains_explicit():
    source = read("video_workspace.py")
    # Presentation labels are localized; the semantic Video logo modes remain
    # explicit at the workspace boundary.
    assert '"front"' in source and '"logo.mode.front"' in source
    assert '"entire"' in source and '"logo.mode.entire"' in source
    assert '"back"' in source and '"logo.mode.back"' in source
    assert "top-left" in source
