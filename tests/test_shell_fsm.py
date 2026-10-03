import pytest
from nenolink_ai_marker.shell_controller import ContentState, ContentEvent, DESTINATIONS, SHELL_TRANSITION_TABLE, ShellController

def test_shell_invariants_and_complete_table():
    assert len(ContentState) == len(ContentEvent) == 4
    assert len(SHELL_TRANSITION_TABLE) == 16
    assert set(DESTINATIONS) == {s.value for s in ContentState}
    assert "pp" not in DESTINATIONS and "media" not in DESTINATIONS and "document" not in DESTINATIONS

@pytest.mark.parametrize("entry", SHELL_TRANSITION_TABLE.items())
def test_table_execution_receipt(entry):
    (source, event), destination = entry
    controller = ShellController()
    controller.active_content_type = source.value
    controller.dispatch(event.value)
    receipt = controller.receipts[-1]
    assert receipt.source == source.value
    assert receipt.event == event.value
    assert receipt.expected_destination == destination.value
    assert receipt.final_state == destination.value
    assert receipt.workspace == destination.value
    assert "event accepted" in receipt.stages
    assert "transition table entry resolved" in receipt.stages
    assert "destination state committed" in receipt.stages

def test_same_state_receipt_preserves_state():
    controller = ShellController()
    controller.dispatch("image")
    assert controller.active_content_type == "image"
    assert controller.receipts[-1].final_state == "image"
