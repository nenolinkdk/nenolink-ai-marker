"""Impact-based pre-build gate for the active PPTX route."""
import inspect

from nenolink_ai_marker.app import MarkerApp


def test_pptx_navigation_route_mounts_canonical_workspace():
    source = inspect.getsource(MarkerApp.render_shell_state)
    assert 'self._workspace_registry[destination]()' in source
    assert 'text="PPTX TEST"' not in source
    mount = inspect.getsource(MarkerApp._mount_pptx_workspace)
    assert 'self.pptx_workspace_state.mount(self.content_host)' in mount
    assert 'raise RuntimeError("PPTX workspace failed to mount")' in mount


def test_pptx_empty_workspace_contract_is_complete():
    source = inspect.getsource(__import__('nenolink_ai_marker.pptx_workspace', fromlist=['PptxWorkspace']))
    assert 'class PptxWorkspace' in source
    assert 'text="PowerPoint"' in source
    assert 'self.mounted = True' in source


def test_pptx_minimal_workspace_has_no_legacy_builder_dependency():
    source = inspect.getsource(MarkerApp._mount_pptx_workspace)
    assert "_mount_pptx_workspace_canonical" not in source
    assert "build_workspace_control_template" not in source
