from types import SimpleNamespace
from unittest.mock import Mock
import inspect
from types import MethodType

from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.ui_state import DocumentPreviewState


class _Variable:
    def __init__(self,value=""):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value


def test_render_start_view_restores_localized_welcome_state():
    app = SimpleNamespace(
        show_tab=Mock(),
        update_idletasks=Mock(),
        preview_photo=object(),
        preview_image=object(),
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
    assert app.preview_image is None
    app.preview_label.configure.assert_called_once_with(image=None, text="")
    app.preview_label.grid_remove.assert_called_once_with()
    app.welcome_title.configure.assert_called_once_with(text="da:welcome.title")
    app.welcome_tagline.configure.assert_called_once_with(text="da:welcome.tagline")
    app.welcome_description1.configure.assert_called_once_with(text="da:welcome.description1")
    app.welcome_description2.configure.assert_called_once_with(text="da:welcome.description2")
    app._show_welcome.assert_called_once_with()
    app.welcome_frame.lift.assert_called_once_with()


def test_back_navigation_only_selects_single_file_tab():
    app = SimpleNamespace(active_tool="badges",active_content_type="image",initialize_clean_context=Mock(),_render_authoritative_state=Mock())

    MarkerApp.navigate_home(app)

    assert app.active_tool is None
    app.initialize_clean_context.assert_called_once_with("image")
    app._render_authoritative_state.assert_called_once()


def test_back_navigation_returns_to_authoritative_document_content():
    app=SimpleNamespace(active_tool="inspect",active_content_type="pdf",initialize_clean_context=Mock(),_render_authoritative_state=Mock())
    MarkerApp.navigate_home(app)
    assert app.active_tool is None
    app.initialize_clean_context.assert_called_once_with("pdf")
    app._render_authoritative_state.assert_called_once()


def test_clear_document_states_removes_pdf_pptx_files_scopes_and_previews():
    pptx_state=DocumentPreviewState(8,10); pdf_state=DocumentPreviewState(4,8)
    app=SimpleNamespace(
        active_content_type="pptx",pptx_path="slides.pptx",pptx_metrics=object(),_pptx_warning_approved=object(),
        pdf_path="pages.pdf",pdf_info=object(),_pdf_warning_approved=object(),_pdf_signature_approved=object(),
        docx_path=None,docx_info=None,_docx_warning_approved=None,
        pptx_preview_state=pptx_state,pdf_preview_state=pdf_state,
        pptx_selection_mode_var=_Variable("selected"),pptx_selected_var=_Variable("2,5,8"),pptx_range_var=_Variable("3-7"),
        pptx_file_var=_Variable("old filename"),pptx_preview_photo=object(),
        pptx_preview_renderer=Mock(),docx_preview_renderer=Mock(),processor=Mock(),pptx_preview_label=Mock(),pptx_slide_status=Mock(),pptx_previous_button=Mock(),pptx_next_button=Mock(),
    )
    app.reset_format_context=MethodType(MarkerApp.reset_format_context,app)
    MarkerApp._clear_document_states(app)
    assert app.pptx_path is app.pdf_path is None
    assert app.pptx_metrics is app.pdf_info is None
    assert (pptx_state.current,pptx_state.count)==(1,0) and (pdf_state.current,pdf_state.count)==(1,0)
    assert app.pptx_selection_mode_var.get()=="all"
    assert (app.pptx_selected_var.get(),app.pptx_range_var.get())==("","1-2")
    assert app.pptx_file_var.get()=="" and app.pptx_preview_photo is None
    app.pptx_previous_button.configure.assert_called_with(state="disabled")
    app.pptx_next_button.configure.assert_called_with(state="disabled")
    assert pptx_state.initialize(10)==1
    assert pdf_state.initialize(8)==1


def test_global_reset_clears_media_and_document_state_through_central_operations():
    destroy=inspect.getsource(MarkerApp._destroy_all_runtime_contexts)
    source=inspect.getsource(MarkerApp._create_fresh_runtime_state)
    wrapper=inspect.getsource(MarkerApp.reset_application)
    assert 'self.active_content_type="image"' in source
    assert 'self.media_sources={"image":[],"video":[]}' in source
    assert 'self.active_tool=None' in source
    assert 'for renderer_name in ("preview_renderer","pdf_preview_renderer","pptx_preview_renderer")' in destroy
    assert "MarkerApp._destroy_all_runtime_contexts(self)" in wrapper
    assert "MarkerApp._create_fresh_runtime_state(self)" in wrapper
