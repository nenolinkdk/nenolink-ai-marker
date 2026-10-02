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


def test_pdf_control_order_and_human_labels_are_explicit():
    active = _mount_source()
    for label in ("FILE", "AI BADGE", "OWN LOGO", "PDF PAGES", "OUTPUT", "Badge Position", "Badge Size", "Badge Margin", "Badge Opacity"):
        assert label in active
    assert active.index('text="FILE"') < active.index('text="AI BADGE"') < active.index('text="OWN LOGO"') < active.index('text="PDF PAGES"') < active.index('text="OUTPUT"')


def test_pdf_badge_selection_uses_shared_repository_and_rerenders_without_remount():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def select_pdf_badge_display")
    end = source.index("    def _sync_pdf_state", start)
    handler = source[start:end]
    assert "self.badge_display_to_file.get(display_name)" in handler
    assert "self.badges.find(filename)" in handler
    assert "self.pdf_state.badge.badge_id = filename" in handler
    assert "self.render_pdf_preview()" in handler
    assert "_mount_pdf_workspace" not in handler


def test_pdf_badge_position_projects_state_and_preview_without_remount():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def change_pdf_badge_position")
    end = source.index("    def _sync_pdf_state", start)
    handler = source[start:end]
    assert "self.position_display_to_value.get(display_name)" in handler
    assert "self.pdf_state.badge.position = value" in handler
    assert "self.render_pdf_preview()" in handler
    assert "_mount_pdf_workspace" not in handler
    mount = _mount_source()
    assert "command=self.change_pdf_badge_position" in mount


def test_pdf_badge_size_projects_normalized_state_and_preview():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def change_pdf_badge_size")
    end = source.index("    def _sync_pdf_state", start)
    handler = source[start:end]
    assert "max(1, min(100" in handler
    assert "self.pdf_state.badge.size = normalized" in handler
    assert "Badge Size: {normalized}%" in handler
    assert "self.render_pdf_preview()" in handler
    assert "command=self.change_pdf_badge_size" in _mount_source()
