import pytest
import inspect

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.shell_controller import DESTINATIONS, DEFAULT_DESTINATION, ShellController, placeholder_for


def assert_shell(controller, destination):
    transition = controller.transitions[-1]
    assert controller.destination == destination
    assert transition.next == destination
    assert transition.mounted_view == placeholder_for(destination)


def test_all_destinations_mount_their_own_placeholder_in_sequence():
    controller = ShellController()
    for destination in ("image", "video", "pdf", "pptx", "badges", "inspect", "image"):
        controller.dispatch(destination)
        assert_shell(controller, destination)


def test_reverse_order_never_restores_video():
    controller = ShellController()
    for destination in ("inspect", "badges", "pptx", "pdf", "video", "image") * 3:
        controller.dispatch(destination)
        assert_shell(controller, destination)


def test_reset_mounts_default_and_all_destinations_remain_available():
    controller = ShellController()
    controller.dispatch("pptx")
    reset = controller.dispatch("reset")
    assert reset.previous == "pptx"
    assert_shell(controller, DEFAULT_DESTINATION)
    for destination in ("pdf", "inspect", "video", "pptx", "badges", "image"):
        controller.dispatch(destination)
        assert_shell(controller, destination)


@pytest.mark.parametrize("destination", DESTINATIONS)
def test_each_transition_records_authoritative_state_and_mounted_view(destination):
    controller = ShellController()
    transition = controller.dispatch(destination)
    assert (transition.previous, transition.event, transition.next) == ("image", destination, destination)
    assert transition.mounted_view == f"{destination.upper()} TEST"


def test_unknown_event_is_rejected_without_changing_state():
    controller = ShellController()
    with pytest.raises(ValueError):
        controller.dispatch("document-workspace")
    assert controller.destination == DEFAULT_DESTINATION


def test_active_app_shell_has_one_controller_and_one_common_host():
    source = inspect.getsource(MarkerApp)
    assert "self.shell_controller = ShellController()" in source
    assert "self.content_host = ctk.CTkFrame(self)" in source
    assert "_single_ui" not in source
    assert "_document_context_ui" not in source
    assert "_batch_ui" not in source
    assert "_settings_ui" not in source
    assert "_inspect_ui" not in source
