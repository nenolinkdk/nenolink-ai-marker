"""Common, policy-free workspace contract checks."""

import inspect

import pytest

from nenolink_ai_marker.image_workspace import ImageWorkspace
from nenolink_ai_marker.video_workspace import VideoWorkspace
from nenolink_ai_marker.pdf_workspace import PdfWorkspace
from nenolink_ai_marker.pptx_workspace import PptxWorkspace
from nenolink_ai_marker.workspace_protocol import WorkspaceProtocol


WORKSPACES = (
    ("ImageWorkspace", ImageWorkspace),
    ("VideoWorkspace", VideoWorkspace),
    ("PdfWorkspace", PdfWorkspace),
    ("PptxWorkspace", PptxWorkspace),
)
METHODS = ("mount", "unmount", "dispatch", "project", "has_active_work", "clear_runtime_state", "enter_clean")


def run_workspace_contract_tests(workspace_cls):
    """Return common structural failures for one workspace class.

    This deliberately tests only the shell-facing lifecycle shape.  It does
    not prescribe format-specific transitions, rendering, scope or output.
    """
    failures = []
    for name in METHODS:
        method = getattr(workspace_cls, name, None)
        if not callable(method):
            failures.append(f"missing lifecycle method {name}")
    if not issubclass(workspace_cls, object):  # documents that no inheritance is required
        failures.append("workspace is not a normal object")
    return failures


@pytest.mark.parametrize("name,workspace_cls", WORKSPACES)
def test_workspace_structural_lifecycle_contract(name, workspace_cls):
    failures = run_workspace_contract_tests(workspace_cls)
    assert not failures, f"{name}: {', '.join(failures)}"


@pytest.mark.parametrize("name,workspace_cls", WORKSPACES)
def test_workspace_is_structurally_conformant_without_inheritance(name, workspace_cls):
    assert isinstance(workspace_cls.__new__(workspace_cls), WorkspaceProtocol), name
    assert WorkspaceProtocol not in workspace_cls.__bases__, "protocol must not become a base class"


def test_protocol_contains_only_local_lifecycle_surface():
    assert set(WorkspaceProtocol.__annotations__) == set()
    protocol_methods = {
        name for name, value in WorkspaceProtocol.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert protocol_methods == set(METHODS)
    assert "save" not in protocol_methods
    assert "reset" not in protocol_methods


def test_contract_does_not_define_format_policy():
    source = inspect.getsource(WorkspaceProtocol)
    for forbidden in ("ImageEvent", "VideoEvent", "PdfEvent", "PptxEvent", "TRANSITION_TABLE", "processor", "preview"):
        assert forbidden not in source
