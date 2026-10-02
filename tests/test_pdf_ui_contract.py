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
    for label in ("FILE", "AI BADGE", "OWN LOGO", "PDF PAGES", "OUTPUT", "Badge Position", "Badge Size", "Margin:", "Opacity:", "Logo Size:", "Logo Margin:", "Logo Opacity:"):
        assert label in active
    assert active.index('text="FILE"') < active.index('text="PDF PAGES"') < active.index('text="AI BADGE"') < active.index('text="OWN LOGO"') < active.index('text="OUTPUT"')


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


def test_pdf_badge_margin_and_opacity_project_state_and_preview():
    source = APP.read_text(encoding="utf-8")
    for name, state_field, label, bounds in (
        ("change_pdf_badge_margin", "self.pdf_state.badge.margin = normalized", "Margin: {normalized} px", "max(0, min(250"),
        ("change_pdf_badge_opacity", "self.pdf_state.badge.opacity = normalized", "Opacity: {normalized}%", "max(0, min(100"),
    ):
        start = source.index(f"    def {name}")
        end = source.index("    def ", start + 5)
        handler = source[start:end]
        assert bounds in handler
        assert state_field in handler
        assert label in handler
        assert "self.render_pdf_preview()" in handler
    mount = _mount_source()
    assert "command=self.change_pdf_badge_margin" in mount
    assert "command=self.change_pdf_badge_opacity" in mount


def test_pdf_logo_enable_projection_preserves_selected_path():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def change_pdf_logo_enabled")
    end = source.index("    def ", start + 5)
    handler = source[start:end]
    assert "self.pdf_state.logo.enabled = bool(self.logo_enabled_var.get())" in handler
    assert "self.render_pdf_preview()" in handler
    assert "logo.path =" not in handler
    assert "command=self.change_pdf_logo_enabled" in _mount_source()


def test_pdf_preview_projection_event_contract_is_explicit():
    source = APP.read_text(encoding="utf-8")
    for event in (
        "choose_pdf_phase2", "change_pdf_preview_page", "change_pdf_page",
        "select_pdf_badge_display", "change_pdf_badge_position",
        "change_pdf_badge_size", "change_pdf_badge_margin",
        "change_pdf_badge_opacity", "change_pdf_logo_enabled",
    ):
        start = source.index(f"    def {event}")
        end = source.find("    def ", start + 5)
        handler = source[start:] if end == -1 else source[start:end]
        assert ("render_pdf_preview" in handler or "update_pdf_preview" in handler), event


def test_pdf_logo_properties_have_independent_state_handlers_and_labels():
    source = APP.read_text(encoding="utf-8")
    for name, field, label in (("change_pdf_logo_position", "logo.position", "Logo Position"), ("change_pdf_logo_size", "logo.size", "Logo Size"), ("change_pdf_logo_margin", "logo.margin", "Logo Margin"), ("change_pdf_logo_opacity", "logo.opacity", "Logo Opacity")):
        start = source.index(f"    def {name}")
        end = source.find("    def ", start + 5)
        handler = source[start:] if end == -1 else source[start:end]
        assert field in handler and "render_pdf_preview" in handler
        assert label in source
    assert "self.pdf_state.logo.path =" in source


def test_pdf_save_projects_authoritative_state_and_uses_ai_filename():
    source = APP.read_text(encoding="utf-8")
    start = source.index("    def process_pdf_phase6")
    end = source.index("    def _update_pdf_scope_controls", start)
    handler = source[start:end]
    assert "asksaveasfilename" in handler
    assert "initialfile=f\"{self.pdf_path.stem}_ai.pdf\"" in handler
    assert "self.pdf_state.badge.position" in handler
    assert "self.pdf_state.logo.position" in handler
    assert "ItemSelection(\"selected\", tuple(self.pdf_active_scope))" in handler
    assert "_mount_pdf_workspace" not in handler
