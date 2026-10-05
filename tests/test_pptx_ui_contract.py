from pathlib import Path
ROOT=Path(__file__).parents[1]
APP=(ROOT/"nenolink_ai_marker"/"app.py").read_text(encoding="utf-8")
WS=(ROOT/"nenolink_ai_marker"/"pptx_workspace.py").read_text(encoding="utf-8")
STATE=(ROOT/"nenolink_ai_marker"/"pptx_state.py").read_text(encoding="utf-8")
def test_pptx_workspace_has_common_sections_and_human_labels():
    assert "class PptxWorkspace" in WS and "def mount(self" in WS
    for token in ("file_heading","slides_heading","badge_enable","logo_choose_button","preview_label"): assert token in WS
def test_pptx_badge_uses_common_repository_and_projects_graphic():
    assert "project_badge" in WS and "build_badge_visual" in WS and "_project_badge" in WS
def test_pptx_preview_and_output_share_authoritative_projection():
    assert "def _render_preview" in WS and "def _save_as" in WS
    assert "self.state.badge" in WS and "self.state.logo" in WS
def test_pptx_scope_and_physical_navigation_are_separate():
    assert "PptxEvent.SCOPE_MODE" in WS and "PptxEvent.PREVIEW_NEXT" in WS
    assert "active_scope" in WS and "current_slide" in WS
def test_pptx_file_row_exposes_save_and_common_order():
    assert "command=self._choose_file" in WS and "command=self._save_as" in WS
    assert WS.index("file_heading") < WS.index("slides_heading") < WS.index("badge_enable")
def test_pptx_table_is_normative_for_all_events():
    from nenolink_ai_marker.pptx_state import PPTX_TRANSITION_TABLE,PptxEvent,pptx_transition
    assert {x.event for x in PPTX_TRANSITION_TABLE}==set(PptxEvent)
    for event in PptxEvent: assert pptx_transition(event).event is event

def test_pptx_callbacks_dispatch_table_events():
    for event in ("BADGE_ENABLE","BADGE_SELECT","BADGE_POSITION","SCOPE_MODE","SCOPE_UPDATE","PREVIEW_NEXT"): assert f"PptxEvent.{event}" in WS
    assert "apply_pptx_event" in WS
def test_pptx_legacy_routes_are_absent_from_markerapp():
    assert "def _mount_pptx_workspace_canonical" not in APP
    assert "def process_pptx(self)" not in APP
    assert "self.pptx_workspace_state.mount" in APP
