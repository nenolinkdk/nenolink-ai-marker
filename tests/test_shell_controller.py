import pytest
import inspect
from types import SimpleNamespace
from unittest.mock import patch

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


def test_active_app_has_one_shell_owner_and_only_image_is_connected():
    source = inspect.getsource(MarkerApp)
    assert "self.shell_controller = ShellController()" in source
    assert "self.content_host = ctk.CTkFrame(self)" in source
    assert "self._build_image_workspace()" in source
    assert "def _build_image_workspace" in source
    assert "_mount_image_workspace" in source
    assert "_unmount_image_workspace" in source
    assert "_document_context_ui" not in source
    assert "_batch_ui" not in source
    assert "_settings_ui" not in source
    assert "_inspect_ui" not in source
    assert "_single_ui" not in source
    for legacy_state in ("video_mode_var", "batch_suffix_var", "media_sources", "active_media_mode"):
        assert legacy_state not in source


def test_image_module_does_not_own_outer_navigation_state():
    source = inspect.getsource(MarkerApp)
    image_module = source[source.index("# --- Image module lifecycle"):]
    assert "shell_controller.dispatch(" not in image_module
    assert "content_buttons[" not in image_module
    assert "content_host =" not in image_module


class _ImageShellCallbackHarness:
    """Exercise MarkerApp's actual shell callback without creating Tk."""

    dispatch_shell_event = MarkerApp.dispatch_shell_event
    reset_shell = MarkerApp.reset_shell

    def __init__(self, active_work=False):
        self.shell_controller = ShellController()
        self.translator = SimpleNamespace(text=lambda key: key)
        self.active_work = active_work
        self.unmounted = 0
        self.rendered = []

    def _image_has_active_work(self):
        return self.active_work

    def _unmount_image_workspace(self):
        self.unmounted += 1
        self.active_work = False

    def render_shell_state(self):
        self.rendered.append(self.shell_controller.destination)


@pytest.mark.parametrize("destination", ("video", "pdf", "pptx", "badges", "inspect"))
def test_actual_image_callback_unmounts_then_mounts_each_destination(destination):
    app = _ImageShellCallbackHarness()
    app.dispatch_shell_event(destination)
    assert app.shell_controller.destination == destination
    assert app.unmounted == 1
    app.dispatch_shell_event("image")
    assert app.shell_controller.destination == "image"
    assert app.rendered == [destination, "image"]


def test_loaded_image_cancel_keeps_image_and_continue_clears_before_switch():
    app = _ImageShellCallbackHarness(active_work=True)
    with patch("nenolink_ai_marker.app.messagebox.askokcancel", return_value=False):
        app.dispatch_shell_event("pdf")
    assert app.shell_controller.destination == "image"
    assert app.active_work is True and app.unmounted == 0
    with patch("nenolink_ai_marker.app.messagebox.askokcancel", return_value=True):
        app.dispatch_shell_event("pdf")
    assert app.shell_controller.destination == "pdf"
    assert app.active_work is False and app.unmounted == 1


def test_reset_is_unconditional_and_returns_a_clean_image_shell():
    app = _ImageShellCallbackHarness(active_work=True)
    app.reset_shell()
    assert app.shell_controller.destination == "image"
    assert app.active_work is False and app.unmounted == 1
