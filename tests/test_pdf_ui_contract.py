from pathlib import Path
ROOT = Path(__file__).parents[1]
APP = ROOT / "nenolink_ai_marker" / "app.py"
WORKSPACE = ROOT / "nenolink_ai_marker" / "pdf_workspace.py"
def _app(): return APP.read_text(encoding="utf-8")
def _workspace(): return WORKSPACE.read_text(encoding="utf-8")
def test_pdf_production_route_targets_workspace():
    assert "self.pdf_workspace_owner.mount(self.content_host)" in _app()
    assert "def mount(self" in _workspace() and "_build_pdf_workspace_compat" not in _app()
    assert "process_pdf_phase6" not in _app()
def test_pdf_workspace_mount_owns_single_ui_tree_and_preview():
    s = _workspace(); assert s.count("def mount(self") == 1
    assert "pdf_workspace_root" in s and "pdf_controls_host" in s and "pdf_preview_host" in s
    assert "ctk.CTkLabel(preview_host" in s
def test_pdf_file_control_does_not_remount_workspace():
    s = _workspace(); assert "command=self.choose_file" in s and "def choose_file" in s
    assert "_mount_pdf_workspace" not in s
def test_pdf_controls_use_workspace_event_boundary():
    s = _workspace()
    for m in ("set_badge", "set_scope", "set_logo", "save"): assert f"def {m}(" in s
    assert "apply_pdf_event" in s and "PdfWorkspaceState" in s
def test_pdf_save_control_targets_workspace_save():
    s = _workspace(); assert "command=self.save" in s and "def save(self)" in s
    assert "build_processing_request" in s and "asksaveasfilename" in s
def test_pdf_authoritative_state_drives_badge_projection():
    s = _workspace(); assert "self.state.badge" in s and "self._ensure_badge_selection()" in s
    assert "badge_display_var" in s and "pdf_badge_visual" in s
def test_pdf_clean_state_projects_default_badge_before_file_load():
    s = _workspace(); assert "def enter_clean(self)" in s and "CLEAR_RUNTIME" in s
    assert "_ensure_badge_selection" in s and "badge_id" in s
def test_pdf_active_work_uses_workspace_state():
    s = _workspace(); start = s.index("def has_active_work"); end = s.find("def ", start + 5)
    assert 'getattr(self.state, "path"' in (s[start:] if end == -1 else s[start:end])
def test_pdf_services_remain_processing_boundaries():
    s = _workspace(); assert "PdfProcessor" in s and "pdf_preview_renderer" in s and "build_processing_request" in s
def test_pdf_legacy_routes_absent_structural_guard():
    from nenolink_ai_marker.app import MarkerApp
    assert not hasattr(MarkerApp, "_build_pdf_workspace_compat") and not hasattr(MarkerApp, "process_pdf_phase6")
def test_pdf_state_contract_and_mixed_scope_remain_explicit():
    state = (ROOT / "nenolink_ai_marker" / "workspace_state.py").read_text(encoding="utf-8"); app = _app()
    assert "class PdfWorkspaceState" in state and "active_scope" in state
def test_pdf_visual_preference_snapshot_is_deterministic_and_one_way():
    from nenolink_ai_marker.models import MarkerSettings
    from nenolink_ai_marker.preference_snapshot import VisualPreferenceSnapshot, project_snapshot_to_tk
    class Var:
        def __init__(self): self.value = None
        def set(self, value): self.value = value
    settings = MarkerSettings(badge_name="no-ai.png", size_percent=31); first = VisualPreferenceSnapshot.from_settings(settings)
    assert first == VisualPreferenceSnapshot.from_settings(settings); badge = Var(); project_snapshot_to_tk(first, {"badge_var": badge})
    assert badge.value == "no-ai.png" and not hasattr(first, "set")

# State-table authority gate: the table is the normative PDF behavior specification.
def test_pdf_table_is_normative_and_complete():
    from nenolink_ai_marker.workspace_state import PDF_TRANSITION_TABLE, PdfEvent, pdf_transition
    events = {spec.event for spec in PDF_TRANSITION_TABLE}
    assert events == set(PdfEvent)
    for event in PdfEvent:
        assert pdf_transition(event).event is event

def test_pdf_workspace_actions_use_table_reducer():
    source = _workspace()
    for action in ("accept_file", "set_current_page", "set_badge", "set_logo", "set_scope", "set_scope_mode", "clear_runtime_state"):
        start = source.index(f"def {action}")
        end = source.find("def ", start + 5)
        body = source[start:] if end == -1 else source[start:end]
        assert "apply_pdf_event" in body, action
    assert "PdfEvent" in source

def test_pdf_projection_and_save_are_state_derived():
    source = _workspace()
    project = source[source.index("def project"):source.index("def _ensure_badge_selection")]
    save = source[source.index("def build_processing_request"):source.index("def save")]
    assert "state = self.state" in project
    assert "state.badge" in project and "state.logo" in project
    assert "state = self.state" in save and "state.badge" in save and "state.logo" in save
    assert "badge_var.get" not in save and "position_var.get" not in save

def test_pdf_ui_callbacks_have_table_contracts():
    source = _workspace()
    assert "command=self.choose_file" in source
    assert "command=self.save" in source
    assert "apply_pdf_event(self.state, PdfEvent.BADGE_CHANGED" in source
    assert "apply_pdf_event(self.state, PdfEvent.LOGO_CHANGED" in source
    assert "apply_pdf_event(self.state, PdfEvent.SCOPE_MODE" in source
