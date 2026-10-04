from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.shell_controller import ShellController, ShellTransitionExecutor


CONTENT = ("image", "video", "pdf", "pptx")


class Host:
    def __init__(self):
        self.children = []

    def clear(self):
        self.children.clear()


def _app():
    app = MarkerApp.__new__(MarkerApp)
    app.shell_controller = ShellController()
    app._shell_executor = ShellTransitionExecutor()
    app.active_content_type = "image"
    app.active_tool = None
    app.mounted_view = ""
    app.shell_trace = []
    app.content_host = Host()
    app.content_buttons = {key: Mock() for key in CONTENT}
    app.translator = SimpleNamespace(text=lambda key: key)
    app._format_has_active_work = lambda _kind: False
    app._confirm_format_switch = Mock(return_value=True)
    app._unmount_tool = lambda: None
    app._mount_tool = lambda _tool: None
    app.image_workspace = None
    app.video_workspace = None
    app._clear_content_host = lambda: app.content_host.clear()
    app._unmount_image_workspace = lambda: app.content_host.clear()
    app._unmount_video_workspace = lambda: app.content_host.clear()
    app._clear_workspace_runtime = lambda _kind: app.content_host.clear()

    class Workspace:
        def __init__(self, kind):
            self.kind = kind
            self.cleared = 0
            self.unmounted = 0
        def mount(self, host):
            host.clear()
            host.children.append(self.kind)
            setattr(app, f"{self.kind}_workspace", self.kind)
        def project(self):
            return None
        def clear_runtime_state(self):
            self.cleared += 1
        def unmount(self):
            self.unmounted += 1

    app._workspace_registry = {kind: Workspace(kind) for kind in CONTENT}
    app.pdf_path = app.pdf_info = app.pptx_path = app.pptx_metrics = None
    app.pdf_current_page = app.pptx_current_slide = 0
    app.pdf_preview_photo = app.pptx_preview_photo = None
    app.pdf_scope_mode = app.pptx_scope_mode = "all"
    app.pdf_active_scope = app.pptx_active_scope = ()
    app.pdf_scope_input = app.pptx_scope_input = ""
    app.pptx_state = SimpleNamespace(clear=lambda: None)
    return app


def _route(app, target):
    assert MarkerApp.request_content_transition(app, target)
    assert app.shell_controller.active_content_type == target
    assert app.active_content_type == target
    assert app.mounted_view == target.upper()
    assert app.content_host.children == [target]
    assert len(app.content_host.children) == 1


@pytest.mark.parametrize("target", CONTENT)
def test_initial_access_uses_common_route_and_mounts_non_empty_host(target):
    _route(_app(), target)


@pytest.mark.parametrize("source,target", [(a, b) for a in CONTENT for b in CONTENT if a != b])
def test_all_directed_content_transitions_use_common_route(source, target):
    app = _app()
    _route(app, source)
    _route(app, target)


@pytest.mark.parametrize("target", CONTENT)
def test_same_state_selection_preserves_existing_mount(target):
    app = _app()
    _route(app, target)
    before = list(app.content_host.children)
    assert MarkerApp.request_content_transition(app, target)
    assert app.content_host.children == before


def test_active_work_cancel_continue_and_reset_follow_common_algorithm():
    app = _app()
    _route(app, "pdf")
    app._format_has_active_work = lambda kind: kind == "pdf"
    app._confirm_format_switch.return_value = False
    assert not MarkerApp.request_content_transition(app, "pptx")
    assert app.shell_controller.active_content_type == "pdf"
    assert app.content_host.children == ["pdf"]
    app._confirm_format_switch.return_value = True
    assert MarkerApp.request_content_transition(app, "pptx")
    assert app.shell_controller.active_content_type == "pptx"
    app._format_has_active_work = lambda _kind: False
    app._clear_workspace_runtime = lambda _kind: app.content_host.clear()
    app.shell_controller.dispatch("reset")
    MarkerApp.render_shell_state(app)
    assert app.shell_controller.active_content_type == "image"
    assert app.content_host.children == ["image"]


def test_actual_navigation_callback_guards_content_but_not_tool_overlay():
    app = _app()
    MarkerApp.dispatch_shell_event(app, "pptx")
    app._format_has_active_work = lambda kind: kind == "pptx"
    app._confirm_format_switch.return_value = False
    # Content-to-content uses the guard through the public callback.
    MarkerApp.dispatch_shell_event(app, "pdf")
    assert app.shell_controller.active_content_type == "pptx"
    assert app._confirm_format_switch.called
    app._confirm_format_switch.reset_mock()
    # Content-to-tool never invokes the content guard.
    MarkerApp.dispatch_shell_event(app, "badges")
    assert app.shell_controller.active_tool == "badges"
    assert not app._confirm_format_switch.called
    # Tool-to-underlying-content closes the overlay without warning/remount.
    before = list(app.content_host.children)
    MarkerApp.dispatch_shell_event(app, "pptx")
    assert app.shell_controller.active_tool is None
    assert app.shell_controller.active_content_type == "pptx"
    assert app.content_host.children == before
    assert not app._confirm_format_switch.called


def test_tool_to_different_content_uses_underlying_active_work_guard():
    app = _app()
    MarkerApp.dispatch_shell_event(app, "pptx")
    app._format_has_active_work = lambda kind: kind == "pptx"
    MarkerApp.dispatch_shell_event(app, "badges")
    app._confirm_format_switch.return_value = False
    MarkerApp.dispatch_shell_event(app, "pdf")
    assert app.shell_controller.active_content_type == "pptx"
    assert app.shell_controller.active_tool == "badges"
    assert app._confirm_format_switch.called
