"""Impact-based pre-build gate for the active PPTX route."""
import inspect

from nenolink_ai_marker.app import MarkerApp


def test_pptx_navigation_route_mounts_canonical_workspace():
    source = inspect.getsource(MarkerApp.render_shell_state)
    assert 'self._mount_pptx_workspace()' in source
    assert 'text="PPTX TEST"' not in source


def test_pptx_empty_workspace_contract_is_complete():
    source = inspect.getsource(MarkerApp._mount_pptx_workspace_canonical)
    template = inspect.getsource(__import__('nenolink_ai_marker.workspace_ui', fromlist=['build_workspace_control_template']))
    for text in ("PowerPoint", "Choose PowerPoint", "Save Marked PowerPoint",
                 "SLIDES", "AI BADGE", "OWN LOGO"):
        assert text in source
    assert "Choose Logo" in template
    for text in ("Badge Position", "Badge Size", "Margin", "Opacity",
                 "Logo Size", "Logo Margin", "Logo Opacity"):
        assert text in source or text in template


def test_pptx_state_is_shared_by_preview_and_output_projection():
    source = inspect.getsource(MarkerApp)
    assert "def _pptx_visual_projection_settings" in source
    assert "self._pptx_visual_projection_settings()" in source
    assert "self.pptx_state.active_scope" in inspect.getsource(MarkerApp._update_pptx_preview)
