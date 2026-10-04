import pytest

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.shell_controller import (
    ContentState,
    SHELL_TRANSITION_TABLE,
    ShellAction,
    ShellTransitionExecutor,
    shell_transition_spec,
)

from test_common_workspace_routing_gate import CONTENT, _app


PAIRS = [(source, destination) for source in CONTENT for destination in CONTENT]
CROSS_PAIRS = [(source, destination) for source, destination in PAIRS if source != destination]


@pytest.mark.parametrize("source,destination", PAIRS)
def test_empty_content_matrix_uses_production_adapter(source, destination):
    app = _app()
    app._format_has_active_work = lambda _kind: False
    assert MarkerApp.request_content_transition(app, source)
    before = {kind: workspace.cleared for kind, workspace in app._workspace_registry.items()}
    assert MarkerApp.request_content_transition(app, destination)
    assert app.shell_controller.active_content_type == destination
    assert app._workspace_registry[destination].cleaned >= (0 if source == destination else 1)
    assert all(workspace.cleared == before[kind] for kind, workspace in app._workspace_registry.items())
    if source == destination:
        assert app.last_shell_spec.preserve_source
    else:
        assert app.last_shell_receipt.final_state == destination


@pytest.mark.parametrize("source", CONTENT)
def test_active_same_content_preserves_session_without_destructive_actions(source):
    destination = source
    app = _app()
    assert MarkerApp.request_content_transition(app, source)
    workspace = app._workspace_registry[source]
    app._format_has_active_work = lambda _kind: True
    app._confirm_format_switch.return_value = True
    assert MarkerApp.request_content_transition(app, destination)
    assert workspace.cleared == 0
    assert workspace.unmounted == 0
    assert app.shell_controller.active_content_type == source


@pytest.mark.parametrize("source,destination", CROSS_PAIRS)
def test_active_cross_content_cancel_preserves_source_and_receipt_policy(source, destination):
    app = _app()
    assert MarkerApp.request_content_transition(app, source)
    destination_workspace = app._workspace_registry[destination]
    destination_unmounted_before = destination_workspace.unmounted
    app._format_has_active_work = lambda _kind: True
    app._confirm_format_switch.return_value = False
    assert not MarkerApp.request_content_transition(app, destination)
    workspace = app._workspace_registry[source]
    assert workspace.cleared == 0
    assert workspace.unmounted == 0
    assert destination_workspace.cleaned == 0
    assert destination_workspace.unmounted == destination_unmounted_before
    assert app.shell_controller.active_content_type == source
    assert app.last_shell_spec.decision == "cancel"
    assert app.last_shell_spec.preserve_source


@pytest.mark.parametrize("source,destination", CROSS_PAIRS)
def test_active_cross_content_continue_clears_only_source_and_matches_spec(source, destination):
    app = _app()
    assert MarkerApp.request_content_transition(app, source)
    app._format_has_active_work = lambda kind: kind == source
    app._confirm_format_switch.return_value = True
    assert MarkerApp.request_content_transition(app, destination)
    source_workspace = app._workspace_registry[source]
    assert source_workspace.cleared == 1
    assert app._workspace_registry[destination].cleaned == 1
    assert all(workspace.cleared == 0 for kind, workspace in app._workspace_registry.items() if kind != source)
    receipt = app.last_shell_receipt
    expected = shell_transition_spec(source, None, destination, True, "continue")
    assert receipt.source == source
    assert receipt.expected_destination == destination
    assert receipt.decision == "continue"
    assert receipt.planned_actions == tuple(action.value for action in expected.actions)
    assert receipt.executed_actions == receipt.planned_actions
    assert receipt.final_state == destination
    assert ShellAction.CLEAR_ALL_WORKSPACES.value not in receipt.executed_actions


@pytest.mark.parametrize("source", CONTENT)
def test_warning_policy_is_active_only_for_different_content(source):
    same = shell_transition_spec(source, None, source, True)
    different = shell_transition_spec(source, None, next(item for item in CONTENT if item != source), True)
    assert not same.requires_confirmation
    assert different.requires_confirmation


def test_transition_table_covers_complete_four_by_four_matrix():
    assert len(SHELL_TRANSITION_TABLE) == 16
    assert {(source.value, event.value) for source, event in SHELL_TRANSITION_TABLE} == set(PAIRS)
