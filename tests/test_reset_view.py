from types import SimpleNamespace
from unittest.mock import Mock

from nenolink_ai_marker.app import MarkerApp


def test_render_start_view_restores_localized_welcome_state():
    app = SimpleNamespace(
        show_tab=Mock(),
        update_idletasks=Mock(),
        preview_photo=object(),
        preview_label=Mock(),
        welcome_title=Mock(),
        welcome_tagline=Mock(),
        welcome_description1=Mock(),
        welcome_description2=Mock(),
        welcome_frame=Mock(),
        translator=SimpleNamespace(text=lambda key: f"da:{key}"),
        _show_welcome=Mock(),
    )

    MarkerApp.render_start_view(app)

    app.show_tab.assert_called_once_with("single")
    app.update_idletasks.assert_called_once_with()
    assert app.preview_photo is None
    app.preview_label.configure.assert_called_once_with(image=None, text="")
    app.preview_label.grid_remove.assert_called_once_with()
    app.welcome_title.configure.assert_called_once_with(text="da:welcome.title")
    app.welcome_tagline.configure.assert_called_once_with(text="da:welcome.tagline")
    app.welcome_description1.configure.assert_called_once_with(text="da:welcome.description1")
    app.welcome_description2.configure.assert_called_once_with(text="da:welcome.description2")
    app._show_welcome.assert_called_once_with()
    app.welcome_frame.lift.assert_called_once_with()


def test_back_navigation_only_selects_single_file_tab():
    app = SimpleNamespace(show_tab=Mock())

    MarkerApp.navigate_home(app)

    app.show_tab.assert_called_once_with("single")
