import pytest
import inspect
from types import SimpleNamespace
from unittest.mock import patch

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.shell_controller import DESTINATIONS, DEFAULT_DESTINATION, ShellController, placeholder_for


def assert_shell(controller, destination):
    transition = controller.transitions[-1]
    if destination in {"badges", "inspect"}:
        assert controller.active_tool == destination
    else:
        assert controller.active_content_type == destination
        assert controller.active_tool is None
    assert transition.next == destination
    assert transition.mounted_view == placeholder_for(destination)


def test_all_destinations_mount_their_own_placeholder_in_sequence():
    controller = ShellController()
    for destination in ("image", "video", "pdf", "pptx", "badges", "inspect"):
        before = controller.active_content_type
        controller.dispatch(destination)
        assert_shell(controller, destination)
        if destination in {"badges", "inspect"}: assert controller.active_content_type == before
    controller.dispatch("back")
    assert_shell(controller, "pptx")


def test_reverse_order_never_restores_video():
    controller = ShellController()
    for destination in ("inspect", "badges", "pptx", "pdf", "video", "image") * 3:
        before = controller.active_content_type
        controller.dispatch(destination)
        assert_shell(controller, destination)
        if destination in {"badges", "inspect"}: assert controller.active_content_type == before


def test_reset_mounts_default_and_all_destinations_remain_available():
    controller = ShellController()
    controller.dispatch("pptx")
    reset = controller.dispatch("reset")
    assert reset.previous == "pptx"
    assert_shell(controller, DEFAULT_DESTINATION)
    for destination in ("pdf", "video", "pptx", "image"):
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
    assert "batch_mode" not in source


def test_pdf_phase_one_is_a_clean_marker_app_workspace_shell():
    source = inspect.getsource(MarkerApp)
    assert "def _mount_pdf_workspace" in source
    assert 'text="PDF"' in source
    assert "Choose PDF" in source
    assert "PdfPreviewRenderer(self.processor)" in source
    assert "_document_context_ui" not in source


def test_pdf_preview_updates_widget_indicator_and_navigation(monkeypatch, tmp_path):
    from PIL import Image
    import nenolink_ai_marker.app as app_module

    class Widget:
        def __init__(self): self.values = {}
        def configure(self, **kwargs): self.values.update(kwargs)

    class Renderer:
        def render(self, path, page, badge, settings):
            return SimpleNamespace(image=Image.new("RGBA", (20, 20)), page_number=page, page_count=43)

    fake = SimpleNamespace(pdf_path=tmp_path / "original.pdf", pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=43)), pdf_current_page=1, pdf_preview_renderer=Renderer(), pdf_preview_label=Widget(), pdf_page_status=Widget(), pdf_previous_button=Widget(), pdf_next_button=Widget(), pdf_preview_photo=None, settings=lambda: SimpleNamespace())
    monkeypatch.setattr(app_module.ctk, "CTkImage", lambda **kwargs: kwargs)
    MarkerApp.render_pdf_preview(fake)
    assert fake.pdf_preview_label.values["image"]
    assert fake.pdf_page_status.values["text"] == "1 / 43"
    assert fake.pdf_previous_button.values["state"] == "disabled"
    assert fake.pdf_next_button.values["state"] == "normal"


def test_pdf_scope_update_is_independent_from_physical_preview():
    class Entry:
        def __init__(self, value): self.value = value
        def get(self): return self.value
    class Message:
        def __init__(self): self.text = ""
        def configure(self, **kwargs): self.text = kwargs["text"]
    fake = SimpleNamespace(pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=12)), pdf_scope_mode="selected", pdf_scope_entry=Entry("2,4,7"), pdf_scope_message=Message(), pdf_active_scope=(), pdf_scope_input="", pdf_current_page=9, render_pdf_preview=lambda: None)
    MarkerApp.update_pdf_scope(fake)
    assert fake.pdf_active_scope == (2, 4, 7)
    assert fake.pdf_current_page == 2
    fake.pdf_scope_entry.value = "2,99"
    MarkerApp.update_pdf_scope(fake)
    assert fake.pdf_active_scope == (2, 4, 7)
    assert fake.pdf_current_page == 2


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

    def _video_has_active_work(self):
        return False

    def _unmount_image_workspace(self):
        self.unmounted += 1
        self.active_work = False

    def _unmount_video_workspace(self):
        pass

    def render_shell_state(self):
        self.rendered.append(self.shell_controller.destination)


@pytest.mark.parametrize("destination", ("video", "pdf", "pptx", "badges", "inspect"))
def test_actual_image_callback_unmounts_then_mounts_each_destination(destination):
    app = _ImageShellCallbackHarness()
    app.dispatch_shell_event(destination)
    if destination in {"badges", "inspect"}:
        assert app.shell_controller.active_content_type == "image" and app.shell_controller.active_tool == destination
        app.dispatch_shell_event("back")
    else:
        assert app.shell_controller.destination == destination
        assert app.unmounted == 1
        app.dispatch_shell_event("image")
    assert app.shell_controller.active_content_type == "image"


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


def test_tools_preserve_active_content_and_do_not_call_loss_warning():
    app = _ImageShellCallbackHarness(active_work=True)
    with patch("nenolink_ai_marker.app.messagebox.askokcancel") as warning:
        app.dispatch_shell_event("badges")
        assert app.shell_controller.active_content_type == "image"
        assert app.shell_controller.active_tool == "badges"
        assert app.unmounted == 0
        app.dispatch_shell_event("back")
        app.dispatch_shell_event("inspect")
        app.dispatch_shell_event("back")
    warning.assert_not_called()
    assert app.shell_controller.active_content_type == "image"
    assert app.active_work is True
