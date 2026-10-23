"""Impact-based pre-build gate for the active PPTX route."""
import inspect

from nenolink_ai_marker.app import MarkerApp


def test_pptx_navigation_route_mounts_canonical_workspace():
    source = inspect.getsource(MarkerApp.render_shell_state)
    assert 'destination = self.shell_controller.active_content_type' in source
    assert 'text="PPTX TEST"' not in source
    assert 'workspace = self._workspace_registry[destination]' in source
    assert 'workspace.mount(self.content_host)' in source
    init_source = inspect.getsource(MarkerApp.__init__)
    assert '"pptx": self.pptx_workspace_state' in init_source


def test_pptx_empty_workspace_contract_is_complete():
    source = inspect.getsource(__import__('nenolink_ai_marker.pptx_workspace', fromlist=['PptxWorkspace']))
    assert 'class PptxWorkspace' in source
    assert 'section.slides' in source
    assert 'pptx.choose' in source
    assert 'self.mounted = True' in source


def test_pptx_minimal_workspace_has_no_legacy_builder_dependency():
    source = inspect.getsource(MarkerApp.render_shell_state)
    assert "_mount_pptx_workspace_canonical" not in source
    assert "build_workspace_control_template" not in source
