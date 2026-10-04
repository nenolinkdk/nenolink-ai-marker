from types import SimpleNamespace

import pytest

from nenolink_ai_marker.app import _ShellRuntimeAdapter
from nenolink_ai_marker.shell_controller import (
    DESTINATIONS,
    ShellAction,
    ShellController,
    ShellTransitionExecutor,
    shell_transition_spec,
)


class Workspace:
    def __init__(self, active=True, fail=False):
        self.active = active
        self.fail = fail
        self.clear_calls = 0
        self.mount_calls = 0
        self.project_calls = 0
        self.unmount_calls = 0

    def has_active_work(self):
        return self.active

    def clear_runtime_state(self):
        self.clear_calls += 1
        if self.fail:
            raise RuntimeError("injected clear failure")
        self.active = False

    def unmount(self):
        self.unmount_calls += 1

    def mount(self, _host):
        self.mount_calls += 1

    def project(self):
        self.project_calls += 1


def make_app(workspaces):
    controller = ShellController()
    controller.active_content_type = "pptx"
    controller.active_tool = "badges"
    return SimpleNamespace(
        _workspace_registry=workspaces,
        content_host=object(),
        shell_controller=controller,
        _mount_tool=lambda _tool: None,
        _unmount_tool=lambda: None,
    )


def test_confirmed_reset_clears_every_workspace_through_registry_and_receipt():
    workspaces = {name: Workspace() for name in DESTINATIONS}
    app = make_app(workspaces)
    runtime = _ShellRuntimeAdapter(app)
    spec = shell_transition_spec("pptx", "badges", "reset", True, "continue")

    ShellTransitionExecutor().execute(spec, runtime)

    assert all(not workspace.active for workspace in workspaces.values())
    assert runtime.cleared_workspaces == list(DESTINATIONS)
    assert runtime.clear_failures == []
    assert runtime.app.shell_controller.active_tool is None
    assert runtime.app.shell_controller.active_content_type == "image"
    receipt = app.last_shell_receipt
    assert receipt.outcome == "success"
    assert receipt.cleared_workspaces == DESTINATIONS
    assert receipt.final_state == "image"
    assert receipt.final_tool == "none"
    assert ShellAction.CLEAR_ALL_WORKSPACES.value in receipt.executed_actions


def test_cancelled_reset_preserves_all_workspaces_and_tool():
    workspaces = {name: Workspace() for name in DESTINATIONS}
    app = make_app(workspaces)
    runtime = _ShellRuntimeAdapter(app)
    spec = shell_transition_spec("pptx", "inspect", "reset", True, "cancel")

    ShellTransitionExecutor().execute(spec, runtime)

    assert all(workspace.active for workspace in workspaces.values())
    assert all(workspace.clear_calls == 0 for workspace in workspaces.values())
    assert app.shell_controller.active_content_type == "pptx"
    assert app.shell_controller.active_tool == "badges"  # executor preserves source; tool UI remains untouched


def test_reset_receipt_reports_partial_clear_on_failure():
    workspaces = {name: Workspace() for name in DESTINATIONS}
    workspaces["pdf"].fail = True
    app = make_app(workspaces)
    runtime = _ShellRuntimeAdapter(app)
    spec = shell_transition_spec("image", None, "reset", True, "continue")

    with pytest.raises(RuntimeError, match="injected clear failure"):
        ShellTransitionExecutor().execute(spec, runtime)

    receipt = app.last_shell_receipt
    assert receipt.outcome == "failure"
    assert receipt.cleared_workspaces == ("image", "video")
    assert receipt.clear_failures and receipt.clear_failures[0].startswith("pdf: RuntimeError")
