import pytest

from nenolink_ai_marker.shell_controller import (
    ContentState, ContentEvent, ShellAction, shell_transition_spec,
    SHELL_TRANSITION_TABLE,
)
from types import SimpleNamespace
from nenolink_ai_marker.app import MarkerApp


@pytest.mark.parametrize("source,event", list(SHELL_TRANSITION_TABLE))
def test_every_content_table_row_has_executable_plan(source, event):
    spec = shell_transition_spec(source.value, None, event.value, False)
    assert spec.destination_content.value == SHELL_TRANSITION_TABLE[(source, event)].value
    assert ShellAction.PROJECT_DESTINATION in spec.actions
    if source.value != event.value:
        assert ShellAction.MOUNT_DESTINATION in spec.actions


@pytest.mark.parametrize("event", ("badges", "inspect"))
def test_tool_plan_preserves_underlying_content(event):
    spec = shell_transition_spec("pdf", None, event, False)
    assert spec.preserve_source
    assert spec.destination_content is ContentState.PDF
    assert ShellAction.MOUNT_TOOL in spec.actions


def test_reset_plans_cover_cancel_and_confirm():
    cancelled = shell_transition_spec("pdf", None, "reset", True, "cancel")
    confirmed = shell_transition_spec("pdf", None, "reset", True, "continue")
    assert cancelled.preserve_source
    assert cancelled.actions == (ShellAction.PRESERVE_SOURCE,)
    assert confirmed.destination_content is ContentState.IMAGE
    assert ShellAction.CLEAR_ALL_WORKSPACES in confirmed.actions
    assert ShellAction.CLEAR_SOURCE not in confirmed.actions


def test_executor_receipt_stops_at_destination_mount_failure():
    spec = shell_transition_spec("pdf", None, "pptx", False)
    seen = []
    runtime = SimpleNamespace(
        preserve_source=lambda: None,
        clear_source=lambda _source: seen.append("clear"),
        unmount_source=lambda _source: seen.append("unmount"),
        clean_destination=lambda _destination: seen.append("clean"),
        mount_destination=lambda _destination: (_ for _ in ()).throw(OSError("mount failed")),
        project_destination=lambda _destination: seen.append("project"),
        mount_tool=lambda _tool: None, unmount_tool=lambda: None,
        clear_tool=lambda: None, record_receipt=lambda receipt: seen.append(receipt),
    )
    with pytest.raises(RuntimeError):
        __import__("nenolink_ai_marker.shell_controller", fromlist=["ShellTransitionExecutor"]).ShellTransitionExecutor().execute(spec, runtime)
    receipt = seen[-1]
    assert receipt.outcome == "failure"
    assert receipt.failure and "mount failed" in receipt.failure
    assert receipt.last_successful_action == "clean_destination"
    assert "project_destination" not in receipt.executed_actions


@pytest.mark.parametrize("decision", [None, "cancel", "continue"])
def test_receipt_propagates_confirmation_decision(decision):
    spec = shell_transition_spec("pdf", None, "pptx", decision == "cancel", decision)
    seen = []
    runtime = SimpleNamespace(
        preserve_source=lambda: None,
        clear_source=lambda _source: None,
        unmount_source=lambda _source: None,
        clean_destination=lambda _destination: None,
        mount_destination=lambda _destination: None,
        project_destination=lambda _destination: None,
        mount_tool=lambda _tool: None, unmount_tool=lambda: None,
        clear_tool=lambda: None, record_receipt=seen.append,
    )
    if decision == "cancel":
        __import__("nenolink_ai_marker.shell_controller", fromlist=["ShellTransitionExecutor"]).ShellTransitionExecutor().execute(spec, runtime)
    else:
        __import__("nenolink_ai_marker.shell_controller", fromlist=["ShellTransitionExecutor"]).ShellTransitionExecutor().execute(spec, runtime)
    assert seen[-1].decision == decision
    assert seen[-1].guard is (decision == "cancel")


def test_executor_receipt_captures_tool_mount_failure():
    spec = shell_transition_spec("pdf", None, "badges", False)
    seen = []
    runtime = SimpleNamespace(
        preserve_source=lambda: None,
        clear_source=lambda _source: None,
        unmount_source=lambda _source: None,
        clean_destination=lambda _destination: None,
        mount_destination=lambda _destination: None,
        project_destination=lambda _destination: None,
        mount_tool=lambda _tool: (_ for _ in ()).throw(OSError("tool mount failed")),
        unmount_tool=lambda: None, clear_tool=lambda: None,
        record_receipt=seen.append,
    )
    with pytest.raises(RuntimeError):
        __import__("nenolink_ai_marker.shell_controller", fromlist=["ShellTransitionExecutor"]).ShellTransitionExecutor().execute(spec, runtime)
    receipt = seen[-1]
    assert receipt.outcome == "failure"
    assert receipt.tool_result == "not_attempted"
    assert "tool mount failed" in receipt.failure


@pytest.mark.parametrize("destination", ("image", "video", "pdf", "pptx", "badges", "inspect"))
def test_constructed_shell_button_command_enters_production_dispatch(destination):
    calls = []
    app = MarkerApp.__new__(MarkerApp)
    app.dispatch_shell_event = calls.append
    command = app._shell_button_command(destination)
    command()
    assert calls == [destination]


def test_constructed_reset_button_command_enters_production_reset():
    calls = []
    app = MarkerApp.__new__(MarkerApp)
    app.reset_shell = lambda: calls.append("reset")
    app._reset_button_command()
    assert calls == ["reset"]
