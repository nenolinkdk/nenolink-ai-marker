from pathlib import Path


APP = Path(__file__).parents[1] / "nenolink_ai_marker" / "app.py"


def _mount_source():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def _mount_pdf_workspace")
    return source[start:source.index("    def _mount_pptx_workspace", start)]


def test_pdf_mount_has_two_hosts_and_responsive_split():
    active = _mount_source()
    assert "self.pdf_controls_host = AutoHideScrollableFrame" in active
    assert "self.pdf_preview_host = ctk.CTkFrame" in active
    assert "grid_columnconfigure(0, weight=0, minsize=320)" in active
    assert "grid_columnconfigure(1, weight=1)" in active


def test_pdf_preview_is_in_preview_host_and_file_selection_does_not_remount():
    active = _mount_source()
    assert "ctk.CTkLabel(self.pdf_preview_host" in active
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def choose_pdf_phase2")
    end = source.index("    def _confirm_pdf_signature", start)
    assert "_mount_pdf_workspace" not in source[start:end]


def test_pdf_state_contract_and_mixed_scope_remain_explicit():
    state = (Path(__file__).parents[1] / "nenolink_ai_marker" / "workspace_state.py").read_text(encoding="utf-8")
    assert "class PdfWorkspaceState" in state
    source = APP.read_text(encoding="utf-8")
    assert "bounds = part.split(\"-\")" in source
    assert "self.pdf_active_scope" in source
