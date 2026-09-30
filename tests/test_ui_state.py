from pathlib import Path
import inspect
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
from customtkinter import CTkTabview

from nenolink_ai_marker.ui_state import DocumentPreviewState, DocumentScopeState, pptx_item_selection, show_welcome
from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.badges import BadgeRepository
from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.inspection import INSPECT_EXTENSIONS
from nenolink_ai_marker.pptx_preview import PptxPreviewRenderer
from nenolink_ai_marker.pptx_processor import PptxProcessor
from test_pptx_processor import _create_pptx, _write_overlay


class _Variable:
    def __init__(self, value=""):
        self.value=value
    def get(self):
        return self.value
    def set(self, value):
        self.value=value


class _Translator:
    @staticmethod
    def text(key, **values):
        return key.format(**values) if values else key


class _Segmented:
    def __init__(self):self.values=[]; self.visible=True
    def configure(self,**values):self.values=list(values.get("values",self.values))
    def grid(self):self.visible=True
    def grid_remove(self):self.visible=False


class _Tabs:
    def __init__(self):self._segmented_button=_Segmented(); self.current=""
    def set(self,value):self.current=value
    def get(self):return self.current


def _pptx_preview_app(source: Path, badge: Path):
    app=SimpleNamespace(
        translator=_Translator(), active_content_type="pptx", active_tool=None,
        pptx_path=None, pptx_metrics=None,
        pptx_preview_renderer=PptxPreviewRenderer(), pptx_processor=PptxProcessor(),
        _pptx_warning_approved=None, pptx_file_var=_Variable(), status_var=_Variable(),
        pptx_preview_state=DocumentPreviewState(), pdf_preview_state=DocumentPreviewState(),
        pptx_selection_mode_var=_Variable("all"), pptx_selection_display_var=_Variable(),
        pptx_selected_var=_Variable("1, 3"), pptx_range_var=_Variable("1-2"), pptx_scope_validation_label=Mock(),
        badge_var=_Variable(badge.name), badges=BadgeRepository(badge.parent),
        pptx_preview_photo=None, pptx_preview_label=Mock(), pptx_slide_status=Mock(),
        pptx_previous_button=Mock(), pptx_next_button=Mock(),
        settings=lambda:MarkerSettings(), _logo_path=lambda:None, logo_enabled_var=_Variable(False),
        _confirm_pptx_limits=lambda:True,
    )
    app._set_pptx_file_summary=MethodType(MarkerApp._set_pptx_file_summary,app)
    app.update_pptx_preview=MethodType(MarkerApp.update_pptx_preview,app)
    app.reset_format_context=MethodType(MarkerApp.reset_format_context,app)
    app.document_scope_states={"pdf":DocumentScopeState(),"pptx":DocumentScopeState()}
    app._sync_document_scope_controls=MethodType(MarkerApp._sync_document_scope_controls,app)
    app._reset_document_scope=MethodType(MarkerApp._reset_document_scope,app)
    app._rebuild_document_preview=MethodType(MarkerApp._rebuild_document_preview,app)
    app._ensure_global_controls_enabled=MethodType(MarkerApp._ensure_global_controls_enabled,app)
    return app


def test_welcome_is_visible_without_an_image():
    assert show_welcome([])


def test_welcome_is_hidden_after_image_selection():
    assert not show_welcome(["selected.png"])


def test_welcome_returns_when_images_are_cleared():
    sources = ["selected.png"]
    sources.clear()
    assert show_welcome(sources)


@pytest.mark.parametrize(
    ("mode", "values", "expected"),
    [
        ("first", {}, (1,)),
        ("selected", {"selected": "2, 4, 7"}, (2, 4, 7)),
        ("range", {"ranges": "3-6"}, (3, 4, 5, 6)),
        ("range", {"ranges": "2-3, 6-7"}, (2, 3, 6, 7)),
        ("all", {}, (1, 2, 3, 4, 5, 6, 7)),
    ],
)
def test_pptx_ui_selection_modes(mode, values, expected):
    assert pptx_item_selection(mode, **values).resolve(7) == expected


def test_pptx_ui_rejects_invalid_slide_input():
    with pytest.raises(ValueError, match="whole numbers"):
        pptx_item_selection("selected", selected="2, slide 4")
    with pytest.raises(ValueError):
        pptx_item_selection("range", ranges="5-3").resolve(8)


def test_direct_document_contexts_share_the_compact_layout_factory():
    source = inspect.getsource(MarkerApp._document_context_ui)
    assert 'document_format_label=ctk.CTkLabel(panel' in source
    assert 'document_format_label.grid(row=0,column=0' in source
    assert 'pptx_scope_label=ctk.CTkLabel(panel' in source
    assert 'pptx_scope_label.grid(row=0,column=1' in source
    assert 'panel.grid(row=0,column=0,padx=20,pady=(4,8)' in source
    assert 'pptx_controls.grid(row=1,column=0,columnspan=2,rowspan=2,padx=12,pady=(0,8)' in source


def test_production_navigation_exposes_pdf_and_powerpoint_but_not_word():
    build_source = inspect.getsource(MarkerApp._build_ui)
    translation_source = inspect.getsource(MarkerApp.apply_translations)
    assert 'self.document_navigation=ctk.CTkFrame' in build_source
    assert 'self._build_content_navigation()' in translation_source
    assert 'content_pairs=(("image","content.images"),("video","content.video"),("pdf","content.pdf"),("pptx","content.powerpoint"))' in translation_source
    assert '("docx","content.word")' not in translation_source


def test_navigation_groups_share_one_compact_workspace_boundary_row():
    source = inspect.getsource(MarkerApp._build_ui)
    assert 'self.grid_rowconfigure(1,weight=1)' in source
    assert 'content_navigation_frame.grid(row=1,column=0,padx=20,pady=0,sticky="nw")' in source
    assert 'self.tabs.grid(row=1,column=0,padx=16,pady=(9,8),sticky="nsew")' in source
    assert 'self.content_navigation_frame.lift()' in source
    assert 'footer.grid(row=2,column=0' in source
    assert 'self.tools_group_label=' in source
    assert 'self.tools_navigation=' in source
    assert 'self.document_navigation=ctk.CTkFrame' in source
    format_button_center = 3 + 16 + (26 / 2)
    workspace_tab_center = 9 + CTkTabview._outer_spacing + (CTkTabview._button_height / 2)
    assert format_button_center == workspace_tab_center


def _navigation_app(active="image"):
    app=SimpleNamespace(
        active_content_type=active,active_runtime_context_type=active,media_sources={"image":[],"video":[]},active_tool=None,
        content_display_to_kind={"Images":"image","Video":"video","PDF":"pdf","PowerPoint":"pptx"},
        tab_names={"single":"Single File","batch":"Batch Processing","badges":"Badges","inspect":"Inspect File","pdf":"__pdf_context__","pptx":"__pptx_context__"},
        tabs=_Tabs(),sources=[],scan=None,pdf_path=None,pptx_path=None,tools_navigation=Mock(),media_navigation_var=_Variable(),document_navigation_var=_Variable(),
        reset_format_context=Mock(),video_controls=Mock(),_update_logo_controls=Mock(),update_preview=Mock(),_render_active_document=Mock(),
        language_menu=Mock(),reset_button=Mock(),guide_button=Mock(),media_navigation=Mock(),document_navigation=Mock(),translator=_Translator(),
    )
    app._secondary_navigation_keys=MethodType(MarkerApp._secondary_navigation_keys,app)
    app._configure_secondary_navigation=MethodType(MarkerApp._configure_secondary_navigation,app)
    app._format_has_active_work=MethodType(MarkerApp._format_has_active_work,app)
    app._set_format_navigation=MethodType(MarkerApp._set_format_navigation,app)
    app.request_content_transition=MethodType(MarkerApp.request_content_transition,app)
    app.destroy_runtime_context=MethodType(MarkerApp.destroy_runtime_context,app)
    app.initialize_clean_context=MethodType(MarkerApp.initialize_clean_context,app)
    app._render_authoritative_state=MethodType(MarkerApp._render_authoritative_state,app)
    app._validate_content_invariant=MethodType(MarkerApp._validate_content_invariant,app)
    app.visible_workspace_type=active; app.pdf_info=None; app.pptx_metrics=None; app.pdf_preview_state=DocumentPreviewState(); app.pptx_preview_state=DocumentPreviewState()
    app._ensure_global_controls_enabled=MethodType(MarkerApp._ensure_global_controls_enabled,app)
    app._confirm_format_switch=Mock(return_value=True)
    app.show_tab=MethodType(MarkerApp.show_tab,app)
    app.apply_translations=MethodType(lambda self:self._configure_secondary_navigation(),app)
    return app


@pytest.mark.parametrize("source,target",[(a,b) for a in ("image","video","pdf","pptx") for b in ("image","video","pdf","pptx") if a!=b])
def test_all_directed_content_transitions_start_clean(source,target):
    labels={"image":"Images","video":"Video","pdf":"PDF","pptx":"PowerPoint"}; app=_navigation_app(source)
    MarkerApp._configure_secondary_navigation(app)
    MarkerApp.change_content_workspace(app,labels[target])
    assert app.active_content_type==target
    assert app.reset_format_context.call_args_list==[call(source),call(target)]
    expected=() if target in {"pdf","pptx"} else ("single","batch")
    assert app._secondary_navigation_keys()==expected
    assert app.tabs.current==(app.tab_names[target] if target in {"pdf","pptx"} else app.tab_names["single"])


def test_format_switch_cancel_preserves_everything_and_continue_clears_both_contexts():
    app=_navigation_app("image"); app.sources=[Path("active.png")]; app._confirm_format_switch=Mock(return_value=False)
    MarkerApp.change_content_workspace(app,"PDF")
    assert app.active_content_type=="image" and app.sources==[Path("active.png")]
    app.reset_format_context.assert_not_called()
    app._confirm_format_switch.return_value=True
    MarkerApp.change_content_workspace(app,"PDF")
    assert app.active_content_type=="pdf"
    assert app.reset_format_context.call_args_list==[call("image"),call("pdf")]


def test_top_navigation_is_reprojected_from_authoritative_state_before_confirmation():
    app=_navigation_app("pdf"); app.pdf_path=Path("active.pdf")
    app._confirm_format_switch=Mock(return_value=False)
    assert not MarkerApp.change_content_workspace(app,"PowerPoint")
    assert app.active_content_type=="pdf"
    assert app.active_content_type=="pdf"


@pytest.mark.parametrize("tool",["badges","inspect"])
def test_auxiliary_entry_cancel_preserves_work_and_continue_clears_active_format(tool):
    app=_navigation_app("pptx"); app.pptx_path=Path("active.pptx"); app.translator=_Translator(); app._render_inspection=Mock()
    app.inspection_path=None; app.inspection_result=None; app.inspection_error=""
    app._confirm_format_switch=Mock(return_value=False)
    MarkerApp.change_auxiliary_workspace(app,tool)
    assert app.active_tool is None and app.pptx_path==Path("active.pptx")
    app.reset_format_context.assert_not_called()
    app._confirm_format_switch.return_value=True
    MarkerApp.change_auxiliary_workspace(app,tool)
    assert app.active_tool==tool
    app.reset_format_context.assert_called_once_with("pptx")
    assert app.tabs.current==app.tab_names[tool]
    assert app._secondary_navigation_keys()==()
    assert not app.tabs._segmented_button.visible


@pytest.mark.parametrize("tool,target",[(tool,target) for tool in ("badges","inspect") for target in ("image","video","pdf","pptx")])
def test_leaving_auxiliary_for_any_format_opens_clean_destination(tool,target):
    labels={"image":"Images","video":"Video","pdf":"PDF","pptx":"PowerPoint"}; app=_navigation_app("image"); app.active_tool=tool
    MarkerApp.change_content_workspace(app,labels[target])
    assert app.active_tool is None and app.active_content_type==target
    assert call(target) in app.reset_format_context.call_args_list


def test_batch_is_internal_and_clears_incompatible_single_file_state():
    app=_navigation_app("image"); app.active_media_mode="single"; app.tabs.current=app.tab_names["batch"]
    MarkerApp._on_media_mode_changed(app)
    app.reset_format_context.assert_called_once_with("image")
    assert app.active_media_mode=="batch"


def test_global_reset_is_an_unconditional_locked_state_recovery_path():
    source=inspect.getsource(MarkerApp.reset_application)
    recovery=inspect.getsource(MarkerApp._create_fresh_runtime_state)
    assert 'self.active_tool=None' in recovery
    assert 'self.active_content_type="image"' in recovery
    assert "_destroy_all_runtime_contexts" in source and "_create_fresh_runtime_state" in source
    assert "_confirm_format_switch(" not in source and "askokcancel" not in source
    assert "dialog.destroy()" in inspect.getsource(MarkerApp._destroy_all_runtime_contexts)


def test_documents_have_no_secondary_navigation_and_media_cannot_open_document_contexts():
    app=SimpleNamespace(active_content_type="video",active_tool=None,tabs=_Tabs(),tab_names={"single":"Single","batch":"Batch","badges":"Badges","inspect":"Inspect","pdf":"__pdf_context__","pptx":"__pptx_context__"})
    app._secondary_navigation_keys=MethodType(MarkerApp._secondary_navigation_keys,app)
    MarkerApp.show_tab(app,"pdf"); assert app.tabs.current==""
    MarkerApp.show_tab(app,"single"); assert app.tabs.current=="Single"
    app.active_content_type="pdf"; app.tabs.current=""
    MarkerApp.show_tab(app,"single"); MarkerApp.show_tab(app,"batch"); assert app.tabs.current==""


def test_document_inspect_is_global_but_pdf_and_pptx_processing_remains_unsupported():
    assert ".pdf" not in INSPECT_EXTENSIONS and ".pptx" not in INSPECT_EXTENSIONS
    app=SimpleNamespace(active_content_type="pdf",active_tool=None)
    assert MarkerApp._secondary_navigation_keys(app)==()
    assert 'INSPECT_EXTENSIONS | {".pdf",".pptx"}' in inspect.getsource(MarkerApp.choose_inspection_file)


@pytest.mark.parametrize("suffix",[".pdf",".pptx"])
def test_known_unimplemented_document_inspection_reports_not_supported_not_error(tmp_path,suffix):
    source=tmp_path/f"known{suffix}"; source.write_bytes(b"known-format")
    app=SimpleNamespace(
        translator=_Translator(),inspection_path=None,inspection_result=None,inspection_error="",inspection_unsupported=False,
        inspect_file_var=_Variable(),inspect_format_var=_Variable(),inspect_status_var=_Variable(),inspect_software_var=_Variable(),inspect_label_var=_Variable(),inspect_version_var=_Variable(),inspect_message_var=_Variable(),
    )
    app._render_inspection=MethodType(MarkerApp._render_inspection,app)
    with patch("nenolink_ai_marker.app.filedialog.askopenfilename",return_value=str(source)):
        MarkerApp.choose_inspection_file(app)
    assert app.inspection_unsupported and not app.inspection_error
    assert app.inspect_status_var.get()=="inspect.not_supported_yet"
    assert app.inspect_status_var.get()!="inspect.error"


def test_supported_inspector_failure_still_reports_inspection_error(tmp_path):
    source=tmp_path/"broken.png"; source.write_bytes(b"not-an-image")
    app=SimpleNamespace(
        translator=_Translator(),inspection_path=None,inspection_result=None,inspection_error="",inspection_unsupported=False,
        inspect_file_var=_Variable(),inspect_format_var=_Variable(),inspect_status_var=_Variable(),inspect_software_var=_Variable(),inspect_label_var=_Variable(),inspect_version_var=_Variable(),inspect_message_var=_Variable(),
    )
    app._render_inspection=MethodType(MarkerApp._render_inspection,app)
    with patch("nenolink_ai_marker.app.filedialog.askopenfilename",return_value=str(source)):
        MarkerApp.choose_inspection_file(app)
    assert app.inspection_error and not app.inspection_unsupported
    assert app.inspect_status_var.get()=="inspect.error"


@pytest.mark.parametrize(("source","target"),[("image","pdf"),("video","pdf"),("image","pptx"),("video","pptx"),("pdf","image"),("pptx","video")])
def test_secondary_navigation_is_recreated_for_destination_owner(source,target):
    labels={"image":"Images","video":"Video","pdf":"PDF","pptx":"PowerPoint"}; app=_navigation_app(source)
    MarkerApp._configure_secondary_navigation(app)
    MarkerApp.change_content_workspace(app,labels[target])
    expected=() if target in {"pdf","pptx"} else ("single","batch")
    assert app._secondary_navigation_keys()==expected
    if expected:assert app.tabs._segmented_button.values==[app.tab_names[key] for key in expected] and app.tabs._segmented_button.visible
    else:assert not app.tabs._segmented_button.visible


def test_document_context_is_created_only_by_the_external_controller():
    source = inspect.getsource(MarkerApp._create_context_widgets)
    assert 'self._document_context_ui(tab)' in source
    assert 'self.pdf_context_widgets=None; self.pptx_context_widgets=None' in inspect.getsource(MarkerApp._build_ui)


def test_top_level_buttons_only_emit_a_central_content_transition():
    source = inspect.getsource(MarkerApp._build_content_navigation)
    assert 'command=lambda destination=kind: self.request_content_transition(destination)' in source
    assert 'CTkSegmentedButton' not in source
    lifecycle = inspect.getsource(MarkerApp.destroy_runtime_context) + inspect.getsource(MarkerApp.initialize_clean_context)
    assert 'MarkerApp._destroy_context_widgets' in lifecycle
    assert 'MarkerApp._create_context_widgets' in lifecycle


def test_selecting_ten_slide_pptx_initializes_and_renders_slide_one(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge)
    with patch("nenolink_ai_marker.app.filedialog.askopenfilename",return_value=str(source)), patch("nenolink_ai_marker.app.ctk.CTkImage",return_value="preview-image"):
        MarkerApp.choose_pptx(app)
    assert app.pptx_metrics.item_count==10
    assert (app.pptx_preview_state.current,app.pptx_preview_state.count)==(1,10)
    app.pptx_preview_label.configure.assert_called_with(image="preview-image",text="")
    app.pptx_slide_status.configure.assert_called_with(text="pptx.slide_status")


def test_pptx_preview_navigation_changes_index_and_keeps_rendered_image(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.pptx_metrics=app.pptx_processor.document_metrics(source); app.pptx_preview_state.initialize(10)
    app.update_pptx_preview=MethodType(MarkerApp.update_pptx_preview,app)
    with patch("nenolink_ai_marker.app.ctk.CTkImage",return_value="preview-image"):
        MarkerApp.change_pptx_preview_slide(app,1)
        assert app.pptx_preview_state.current==2
        MarkerApp.change_pptx_preview_slide(app,-1)
    assert app.pptx_preview_state.current==1
    assert app.pptx_preview_label.configure.call_args.kwargs["text"]==""


def test_missing_badge_replaces_stale_choose_placeholder_with_unavailable(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.pptx_preview_state.initialize(10); app.document_scope_states["pptx"].active_scope=tuple(range(1,11)); app.badge_var.set("missing.png")
    MarkerApp.update_pptx_preview(app)
    app.pptx_preview_label.configure.assert_called_with(image=None,text="pptx.preview_unavailable")


def test_pptx_page_outside_active_scope_renders_without_overlay(tmp_path):
    source=tmp_path/"three-slides.pptx"; _create_pptx(source,3)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source
    app.pptx_preview_state.initialize(3,2); app.document_scope_states["pptx"].active_scope=(1,)
    app.badge_var.set("missing.png")
    with patch("nenolink_ai_marker.app.ctk.CTkImage",return_value="preview-image"):
        MarkerApp.update_pptx_preview(app)
    app.pptx_preview_label.configure.assert_called_with(image="preview-image",text="")
    assert app.document_scope_states["pptx"].active_scope==(1,)


def test_pptx_control_changes_refresh_preview_but_scope_is_output_only():
    changed_source=inspect.getsource(MarkerApp.changed)
    selection_source=inspect.getsource(MarkerApp.change_pptx_selection_mode)
    assert "self.update_pptx_preview()" in changed_source
    assert "_rebuild_document_preview_selection" not in selection_source


def test_document_preview_state_navigates_physical_items_with_boundaries():
    state=DocumentPreviewState()
    assert state.initialize(10)==1 and (state.current,state.count)==(1,10)
    assert not state.can_previous and state.can_next
    assert state.move(1)==2
    assert state.move(99)==10 and state.can_previous and not state.can_next
    assert state.move(-99)==1


def test_pptx_scope_and_physical_preview_navigation_are_independent(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.pptx_metrics=app.pptx_processor.document_metrics(source)
    app.pptx_selection_display_to_value={"All":"all","First":"first","Selected":"selected","Range":"range"}
    app._update_pptx_selection_fields=Mock(); app.update_pptx_preview=Mock(); app.pptx_preview_state.initialize(10); app.pptx_preview_state.move(3)
    MarkerApp.change_pptx_selection_mode(app,"First")
    assert app.document_scope_states["pptx"].active_scope==(1,) and app.pptx_preview_state.current==1
    MarkerApp.change_pptx_preview_slide(app,3)
    assert app.pptx_preview_state.current==4 and app.document_scope_states["pptx"].active_scope==(1,)
    MarkerApp.change_pptx_selection_mode(app,"Selected")
    assert app.document_scope_states["pptx"].active_scope==(1,) and app.pptx_preview_state.current==4
    app.pptx_selected_var.set("2,5,8")
    assert app.document_scope_states["pptx"].active_scope==(1,)
    MarkerApp.commit_document_selection(app)
    assert app.pptx_preview_state.current==2 and app.document_scope_states["pptx"].active_scope==(2,5,8)
    MarkerApp.change_pptx_preview_slide(app,1)
    assert app.pptx_preview_state.current==3 and app.document_scope_states["pptx"].active_scope==(2,5,8)
    MarkerApp.change_pptx_selection_mode(app,"Range"); app.pptx_range_var.set("3-7"); MarkerApp.commit_document_selection(app)
    assert app.pptx_preview_state.current==3 and app.document_scope_states["pptx"].active_scope==(3,4,5,6,7)
    MarkerApp.change_pptx_selection_mode(app,"All")
    assert app.pptx_preview_state.current==1 and app.document_scope_states["pptx"].active_scope==tuple(range(1,11))


def test_editable_scope_requires_update_and_invalid_update_preserves_applied_scope(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.pptx_metrics=app.pptx_processor.document_metrics(source)
    app.pptx_selection_display_to_value={"All":"all","First":"first","Selected":"selected","Range":"range"}
    app._update_pptx_selection_fields=Mock(); app.update_pptx_preview=Mock(); app.pptx_preview_state.initialize(10)
    app.document_scope_states["pptx"].active_scope=tuple(range(1,11))
    MarkerApp.change_pptx_selection_mode(app,"Selected")
    app.pptx_selected_var.set("2,4,7")
    assert app.document_scope_states["pptx"].active_scope==tuple(range(1,11)) and app.pptx_preview_state.current==1
    MarkerApp.commit_document_selection(app)
    assert app.document_scope_states["pptx"].active_scope==(2,4,7) and app.pptx_preview_state.current==2
    app.pptx_selected_var.set("2,wrong")
    MarkerApp.commit_document_selection(app)
    assert app.document_scope_states["pptx"].active_scope==(2,4,7) and app.pptx_preview_state.current==2
    app.pptx_scope_validation_label.configure.assert_called_with(text="document.scope_invalid")


def test_pdf_preview_navigation_browses_all_pages_without_changing_scope():
    app=SimpleNamespace(
        active_content_type="pdf", active_tool=None, pdf_preview_state=DocumentPreviewState(),
        pptx_metrics=None, pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=8)),
        pptx_selection_mode_var=_Variable("selected"), pptx_selected_var=_Variable("2,5,8"), pptx_range_var=_Variable("1-2"),
        pptx_preview_photo=object(), update_pptx_preview=Mock(), status_var=_Variable(), translator=_Translator(),
        pptx_preview_label=Mock(), pptx_slide_status=Mock(), pptx_previous_button=Mock(), pptx_next_button=Mock(),
    )
    app.document_scope_states={"pdf":DocumentScopeState("selected",selected="2,5,8",active_scope=(2,5,8))}
    app.pdf_preview_state.initialize(8,2); app.update_pdf_preview=Mock()
    MarkerApp.change_pdf_preview_page(app,1); assert app.pdf_preview_state.current==3
    MarkerApp.change_pdf_preview_page(app,1); assert app.pdf_preview_state.current==4
    MarkerApp.change_pdf_preview_page(app,-1); assert app.pdf_preview_state.current==3
    assert app.document_scope_states["pdf"].active_scope==(2,5,8)
    assert app.pptx_selected_var.get()=="2,5,8"


def test_document_format_contexts_are_unloaded_instead_of_preserved():
    app=SimpleNamespace(
        active_content_type="pdf",processor=Mock(), pdf_path=Path("old.pdf"), pptx_path=Path("old.pptx"),
        pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=43)), pptx_metrics=SimpleNamespace(item_count=10),
        pdf_preview_state=DocumentPreviewState(), pptx_preview_state=DocumentPreviewState(),
        _pdf_warning_approved=object(),_pdf_signature_approved=object(),_pptx_warning_approved=object(),
        pptx_preview_renderer=Mock(), pptx_selection_mode_var=_Variable("selected"),
        pptx_selected_var=_Variable("2,5,8"),pptx_range_var=_Variable("3-7"),
        pptx_preview_photo=object(),pptx_preview_label=Mock(),pptx_slide_status=Mock(),pptx_previous_button=Mock(),pptx_next_button=Mock(),status_var=_Variable(),
    )
    app.pdf_preview_state.initialize(43); app.pdf_preview_state.move(11); app.pptx_preview_state.initialize(10)
    MarkerApp.reset_format_context(app,"pdf")
    assert app.pdf_path is None and app.pdf_info is None and (app.pdf_preview_state.current,app.pdf_preview_state.count)==(1,0)
    MarkerApp.reset_format_context(app,"pptx")
    assert app.pptx_path is None and app.pptx_metrics is None and (app.pptx_preview_state.current,app.pptx_preview_state.count)==(1,0)


def test_format_switch_clears_source_and_destination_contexts():
    app=SimpleNamespace(
        content_display_to_kind={"PowerPoint":"pptx"}, active_content_type="pdf", active_runtime_context_type="pdf", active_tool=None, media_sources={"image":[],"video":[]}, sources=[Path("old.pdf")],
        reset_format_context=Mock(), show_tab=Mock(), _render_active_document=Mock(), apply_translations=Mock(), tools_navigation=Mock(),
        _format_has_active_work=Mock(return_value=False), language_menu=Mock(),reset_button=Mock(),guide_button=Mock(),media_navigation=Mock(),document_navigation=Mock(),media_navigation_var=_Variable(),document_navigation_var=_Variable(),
    )
    app.destroy_runtime_context=MethodType(MarkerApp.destroy_runtime_context,app); app.initialize_clean_context=MethodType(MarkerApp.initialize_clean_context,app); app._render_authoritative_state=Mock(); app.request_content_transition=MethodType(MarkerApp.request_content_transition,app)
    MarkerApp.change_content_workspace(app,"PowerPoint")
    assert app.reset_format_context.call_args_list==[call("pdf"),call("pptx")]
    assert app.active_content_type=="pptx"


def test_pdf_scope_sequence_resets_navigation_and_old_scope_fields():
    app=SimpleNamespace(
        active_content_type="pdf", active_tool=None, processor=Mock(),
        pdf_path=Path("document.pdf"), pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=43)),
        pdf_preview_state=DocumentPreviewState(5,43), _pdf_warning_approved=object(), _pdf_signature_approved=object(),
        pptx_selection_mode_var=_Variable("all"), pptx_selected_var=_Variable("2,5,8"),
        pptx_range_var=_Variable("3-7"), pptx_preview_photo=object(), pptx_scope_validation_label=Mock(),
        pptx_selection_display_to_value={"All":"all","First":"first","Selected":"selected","Range":"range"},
        pptx_selection_display_var=_Variable("All"),
        _update_pptx_selection_fields=Mock(), update_pptx_preview=Mock(),update_pdf_preview=Mock(),translator=_Translator(),
        pptx_preview_label=Mock(),pptx_slide_status=Mock(),pptx_previous_button=Mock(),pptx_next_button=Mock(),status_var=_Variable(),
        language_menu=Mock(),reset_button=Mock(),guide_button=Mock(),media_navigation=Mock(),document_navigation=Mock(),tools_navigation=Mock(),
    )
    app.reset_format_context=MethodType(MarkerApp.reset_format_context,app)
    for label,mode in (("First","first"),("Selected","selected"),("Range","range"),("All","all")):
        MarkerApp.change_pptx_selection_mode(app,label)
        assert app.pptx_selection_mode_var.get()==mode
        if mode in {"all","first"}:assert app.pdf_preview_state.current==1 and app.pdf_preview_state.count==43
        assert (app.pptx_selected_var.get(),app.pptx_range_var.get())==("","1-2")


def test_visual_setting_callbacks_do_not_reset_document_context():
    for method in (MarkerApp.changed,MarkerApp.select_badge,MarkerApp.logo_changed,MarkerApp.change_position_display):
        assert "reset_format_context" not in inspect.getsource(method)


def _stateful_navigation_app(active="image"):
    app=_navigation_app(active); app.pdf_path=None; app.pptx_path=None
    def reset(kind):
        if kind in {"image","video"}:app.sources=[]; app.media_sources[kind]=[]
        elif kind=="pdf":app.pdf_path=None
        elif kind=="pptx":app.pptx_path=None
    app.reset_format_context=Mock(side_effect=reset)
    return app


CONTENT_TYPES=("image","video","pdf","pptx")
DIRECTED_CONTENT_TRANSITIONS=tuple((source,target) for source in CONTENT_TYPES for target in CONTENT_TYPES if source!=target)


def _external_fsm_app(active):
    app=_navigation_app(active)
    app.pdf_info=None; app.pptx_metrics=None
    app.pdf_preview_state=DocumentPreviewState(); app.pptx_preview_state=DocumentPreviewState()
    app.document_scope_states={"pdf":DocumentScopeState(),"pptx":DocumentScopeState()}
    app.format_cache={kind:None for kind in CONTENT_TYPES}
    app.reset_log=[]
    def reset(kind):
        # Both source destruction and destination initialisation must happen
        # while that format is the active owner of its state.
        assert app.active_content_type==kind
        app.reset_log.append(kind)
        app.format_cache[kind]=None
        if kind in {"image","video"}:
            app.media_sources[kind]=[]
            app.sources=[]
        elif kind=="pdf":
            app.pdf_path=None; app.pdf_info=None; app.pdf_preview_state.clear(); app.document_scope_states["pdf"].reset()
        else:
            app.pptx_path=None; app.pptx_metrics=None; app.pptx_preview_state.clear(); app.document_scope_states["pptx"].reset()
    app.reset_format_context=Mock(side_effect=reset)
    MarkerApp._set_format_navigation(app,active)
    MarkerApp._configure_secondary_navigation(app)
    return app


def _dirty_format(app,kind):
    app.format_cache[kind]=f"{kind}-cache"
    if kind in {"image","video"}:
        path=Path(f"active.{ 'mp4' if kind=='video' else 'png' }")
        app.media_sources[kind]=[path]
        if app.active_content_type==kind:app.sources=[path]
    elif kind=="pdf":
        app.pdf_path=Path("active.pdf"); app.pdf_info=object(); app.pdf_preview_state.initialize(9,6)
        app.document_scope_states["pdf"]=DocumentScopeState("selected","2,5",active_scope=(2,5))
    else:
        app.pptx_path=Path("active.pptx"); app.pptx_metrics=object(); app.pptx_preview_state.initialize(8,4)
        app.document_scope_states["pptx"]=DocumentScopeState("range",ranges="3-6",active_scope=(3,4,5,6))


def _fsm_snapshot(app):
    return (
        app.active_content_type,app.active_runtime_context_type,app.visible_workspace_type,app.active_tool,tuple(app.sources),
        tuple(app.media_sources["image"]),tuple(app.media_sources["video"]),
        app.pdf_path,app.pdf_info,app.pdf_preview_state.current,app.pdf_preview_state.count,
        app.document_scope_states["pdf"].mode,app.document_scope_states["pdf"].active_scope,
        app.pptx_path,app.pptx_metrics,app.pptx_preview_state.current,app.pptx_preview_state.count,
        app.document_scope_states["pptx"].mode,app.document_scope_states["pptx"].active_scope,
        tuple(sorted(app.format_cache.items())),app.tabs.current,
        app.media_navigation_var.get(),app.document_navigation_var.get(),
    )


def _assert_clean_destination(app,target):
    assert app.active_content_type==target and app.active_tool is None
    assert app.active_runtime_context_type==target and app.visible_workspace_type==target
    assert app.format_cache[target] is None
    if target in {"image","video"}:
        assert app.sources==[] and app.media_sources[target]==[]
        assert app.tabs.current==app.tab_names["single"]
        assert app._secondary_navigation_keys()==("single","batch")
        assert app.document_navigation_var.get()==""
    elif target=="pdf":
        assert app.pdf_path is None and app.pdf_info is None and app.pdf_preview_state==DocumentPreviewState()
        assert app.document_scope_states["pdf"]==DocumentScopeState()
        assert app.tabs.current==app.tab_names["pdf"]
        assert app._secondary_navigation_keys()==()
        assert app.media_navigation_var.get()==""
    else:
        assert app.pptx_path is None and app.pptx_metrics is None and app.pptx_preview_state==DocumentPreviewState()
        assert app.document_scope_states["pptx"]==DocumentScopeState()
        assert app.tabs.current==app.tab_names["pptx"]
        assert app._secondary_navigation_keys()==()
        assert app.media_navigation_var.get()==""


@pytest.mark.parametrize(("source","target"),DIRECTED_CONTENT_TRANSITIONS)
def test_external_fsm_no_data_opens_clean_destination(source,target):
    app=_external_fsm_app(source); _dirty_format(app,target)
    app._confirm_format_switch=Mock(return_value=False)
    assert MarkerApp.request_content_transition(app,target)
    app._confirm_format_switch.assert_not_called()
    assert app.reset_log==[source,target]
    _assert_clean_destination(app,target)


@pytest.mark.parametrize(("source","target"),DIRECTED_CONTENT_TRANSITIONS)
def test_external_fsm_active_data_cancel_preserves_source_exactly(source,target):
    app=_external_fsm_app(source); _dirty_format(app,source)
    before=_fsm_snapshot(app); app._confirm_format_switch=Mock(return_value=False)
    assert not MarkerApp.request_content_transition(app,target)
    assert _fsm_snapshot(app)==before and app.reset_log==[]


@pytest.mark.parametrize(("source","target"),DIRECTED_CONTENT_TRANSITIONS)
def test_external_fsm_active_data_continue_destroys_source_and_activates_clean_destination(source,target):
    app=_external_fsm_app(source); _dirty_format(app,source); _dirty_format(app,target)
    app._confirm_format_switch=Mock(return_value=True)
    assert MarkerApp.request_content_transition(app,target)
    assert app.reset_log==[source,target]
    assert app.format_cache[source] is None
    _assert_clean_destination(app,target)


def test_pdf_with_data_to_pptx_continue_regression_opens_clean_pptx():
    app=_external_fsm_app("pdf"); _dirty_format(app,"pdf"); _dirty_format(app,"pptx")
    app._confirm_format_switch=Mock(return_value=True)
    assert MarkerApp.request_content_transition(app,"pptx")
    assert app.pdf_path is None and app.pdf_preview_state==DocumentPreviewState()
    assert app.document_scope_states["pdf"]==DocumentScopeState()
    _assert_clean_destination(app,"pptx")


@pytest.mark.parametrize("sequence",[
    ("image","pptx","image","pdf","video","pptx","pdf","image"),
    ("pdf","pptx","image","pdf"),
    ("image","pptx","image","video","pdf"),
    ("pptx","pdf","pptx","video","image"),
])
def test_repeated_top_level_sequences_never_retain_stale_files(sequence):
    app=_stateful_navigation_app(sequence[0])
    for target in sequence[1:]:
        if app.active_content_type in {"image","video"}:app.sources=[Path(f"active-{app.active_content_type}")]
        elif app.active_content_type=="pdf":app.pdf_path=Path("active.pdf")
        else:app.pptx_path=Path("active.pptx")
        assert MarkerApp.request_content_transition(app,target)
        assert app.active_content_type==target and app.active_tool is None
        assert app.pdf_path is None and app.pptx_path is None and app.sources==[]
        expected=app.tab_names[target] if target in {"pdf","pptx"} else app.tab_names["single"]
        assert app.tabs.current==expected
        for control in (app.media_navigation,app.document_navigation,app.tools_navigation,app.reset_button):control.configure.assert_any_call(state="normal")


def test_pdf_badges_image_inspect_video_sequence_and_badges_back_are_defined():
    app=_stateful_navigation_app("pdf"); app.pdf_path=Path("active.pdf"); app._render_inspection=Mock(); app.inspection_path=None; app.inspection_result=None; app.inspection_error=""
    app.change_content_workspace=MethodType(MarkerApp.change_content_workspace,app)
    assert MarkerApp.change_auxiliary_workspace(app,"badges") and app.active_tool=="badges" and app.pdf_path is None
    assert MarkerApp.request_content_transition(app,"image") and app.tabs.current==app.tab_names["single"]
    assert MarkerApp.change_auxiliary_workspace(app,"inspect") and app.active_tool=="inspect"
    assert MarkerApp.request_content_transition(app,"video") and app.active_tool is None and app.active_content_type=="video"
    assert MarkerApp.change_auxiliary_workspace(app,"badges")
    assert MarkerApp.request_content_transition(app,"image")
    assert MarkerApp.change_auxiliary_workspace(app,"badges")
    MarkerApp.navigate_home(app)
    assert app.active_content_type=="image" and app.tabs.current==app.tab_names["single"]


def _hard_reset_app(active,data):
    app=_external_fsm_app(active)
    if data:_dirty_format(app,active)
    app.active_tool=None; app._format_switch_dialog=None; app._reset_after_id=None; app.scan=object() if data else None
    app.inspection_path=Path("old.png") if data else None; app.inspection_result=object() if data else None; app.inspection_error="old" if data else ""; app.inspection_unsupported=data
    app.preview_photo=object() if data else None; app.preview_image=object() if data else None; app.pptx_preview_photo=object() if data else None
    app.preview_renderer=Mock(); app.pdf_preview_renderer=Mock(); app.pptx_preview_renderer=Mock(); app.cancel_event=Mock()
    for name,value in (("badge_source_var","custom"),("badge_var","other.png"),("position_var","top-left"),("size_var",99),("margin_var",99),("opacity_var",1),("batch_suffix_var","_old"),("video_mode_var","end"),("video_duration_var",99),("logo_enabled_var",True),("logo_position_var","bottom-right"),("logo_size_var",99),("logo_margin_var",99),("logo_opacity_var",1),("pdf_badge_enabled_var",False),("pptx_selection_mode_var","range"),("pptx_selected_var","2,5"),("pptx_range_var","3-7"),("status_var","stale"),("scan_summary_var","stale"),("progress_text_var","stale"),("pptx_file_var","stale")):
        setattr(app,name,_Variable(value))
    app.progress=Mock(); app.render_start_view=Mock(); app._render_authoritative_state=Mock()
    return app


@pytest.mark.parametrize(("active","data"),[(kind,data) for kind in CONTENT_TYPES for data in (False,True)])
def test_hard_reset_from_every_content_state_equals_fresh_start(active,data):
    app=_hard_reset_app(active,data)
    MarkerApp._destroy_all_runtime_contexts(app); MarkerApp._create_fresh_runtime_state(app)
    assert app.active_content_type=="image" and app.media_sources=={"image":[],"video":[]}
    assert app.active_runtime_context_type==app.visible_workspace_type=="image"
    assert app.active_tool is None and app.sources==[] and app.scan is None
    assert app.pdf_path is None and app.pptx_path is None and app.inspection_path is None
    assert app.pdf_preview_state==DocumentPreviewState() and app.pptx_preview_state==DocumentPreviewState()
    assert all(state==DocumentScopeState() for state in app.document_scope_states.values())
    assert app.status_var.get()==""


@pytest.mark.parametrize(("source","target"),[(source,target) for source in CONTENT_TYPES for target in CONTENT_TYPES])
def test_data_reset_then_every_destination_matches_fresh_transition(source,target):
    app=_hard_reset_app(source,True)
    MarkerApp._destroy_all_runtime_contexts(app); MarkerApp._create_fresh_runtime_state(app)
    app.format_cache={kind:None for kind in CONTENT_TYPES}
    app._render_authoritative_state=MethodType(MarkerApp._render_authoritative_state,app)
    app._render_authoritative_state()
    assert MarkerApp.request_content_transition(app,target)
    _assert_clean_destination(app,target)


def test_repeated_reset_transition_sequence_without_process_restart():
    app=_hard_reset_app("pdf",True)
    for target in ("pptx","video","pdf"):
        MarkerApp._destroy_all_runtime_contexts(app); MarkerApp._create_fresh_runtime_state(app)
        app._render_authoritative_state=MethodType(MarkerApp._render_authoritative_state,app)
        assert MarkerApp.request_content_transition(app,target)
        _assert_clean_destination(app,target)


@pytest.mark.parametrize(("source","target"),[("pdf","pptx"),("pptx","video"),("video","pdf")])
def test_global_reset_callback_then_immediate_navigation_matches_fresh_start(source,target):
    app=_hard_reset_app(source,True); app.custom_badge_var=_Variable("retained-folder")
    app.refresh_badges=Mock(); app.apply_translations=Mock(); app._save=Mock(); app.translator=_Translator(); app._ensure_global_controls_enabled=Mock()
    MarkerApp.reset_application(app)
    assert app.active_content_type==app.active_runtime_context_type==app.visible_workspace_type=="image"
    assert app.custom_badge_var.get()=="retained-folder"
    app.format_cache={kind:None for kind in CONTENT_TYPES}; app._render_authoritative_state=MethodType(MarkerApp._render_authoritative_state,app)
    assert MarkerApp.request_content_transition(app,target)
    _assert_clean_destination(app,target)


def test_reported_pdf_pptx_image_video_pdf_sequence_uses_one_transition_controller():
    app=_external_fsm_app("pdf"); _dirty_format(app,"pdf")
    app._confirm_format_switch=Mock(return_value=True)
    for target in ("pptx","image","video","pdf"):
        assert MarkerApp.request_content_transition(app,target)
        _assert_clean_destination(app,target)
        _dirty_format(app,target)


def _attach_direct_document_context_projection(app):
    app.translator=_Translator(); app.pdf_file_var=_Variable(); app.pptx_file_var=_Variable()
    app.pdf_badge_enabled_var=_Variable(True); app.pptx_selection_mode_var=_Variable("all"); app.pptx_selection_display_var=_Variable()
    widget_names=("document_format_label","pptx_file_label","pptx_choose_button","pptx_badge_label","pdf_badge_enable","pptx_badge_menu","pptx_scope_label","pptx_selection_menu","pptx_selected_label","pptx_range_label","pptx_metadata_note","pptx_process_button","pptx_language_label","pptx_language_menu")
    app.pdf_context_widgets=SimpleNamespace(**{name:Mock(name=f"pdf_{name}") for name in widget_names})
    app.pptx_context_widgets=SimpleNamespace(**{name:Mock(name=f"pptx_{name}") for name in widget_names})
    app._bind_document_context_widgets=MethodType(MarkerApp._bind_document_context_widgets,app)
    app._sync_document_scope_controls=Mock(); app._update_pptx_selection_fields=Mock(); app._update_pptx_logo_controls=Mock(); app.update_pptx_preview=Mock()
    def summary():
        if app.active_content_type=="pdf":app.pdf_file_var.set("PDF clean")
        else:app.pptx_file_var.set("PPTX clean")
    app._set_active_document_summary=summary
    app._synchronize_document_widgets=MethodType(MarkerApp._synchronize_document_widgets,app)
    app._render_active_document=MethodType(MarkerApp._render_active_document,app)
    return app


def test_gui_command_pdf_data_to_pptx_continue_renders_only_direct_pptx_context():
    app=_attach_direct_document_context_projection(_external_fsm_app("pdf")); _dirty_format(app,"pdf")
    app._confirm_format_switch=Mock(return_value=True)
    assert MarkerApp.change_content_workspace(app,"PowerPoint")
    _assert_clean_destination(app,"pptx")
    app.pptx_context_widgets.pptx_choose_button.configure.assert_called_with(text="pptx.choose")
    app.pptx_context_widgets.pptx_scope_label.configure.assert_called_with(text="pptx.scope")
    app.pptx_context_widgets.pptx_process_button.configure.assert_called_with(text="pptx.process")
    app.pptx_context_widgets.pptx_file_label.configure.assert_called_with(textvariable=app.pptx_file_var)
    app.pdf_context_widgets.pptx_choose_button.configure.assert_not_called()
    assert app.pdf_path is None and app.pdf_info is None and app.pdf_preview_state==DocumentPreviewState()
    assert not app.tabs._segmented_button.visible


def test_gui_command_pptx_data_to_pdf_continue_renders_only_direct_pdf_context():
    app=_attach_direct_document_context_projection(_external_fsm_app("pptx")); _dirty_format(app,"pptx")
    app._confirm_format_switch=Mock(return_value=True)
    assert MarkerApp.change_content_workspace(app,"PDF")
    _assert_clean_destination(app,"pdf")
    app.pdf_context_widgets.pptx_choose_button.configure.assert_called_with(text="pdf.choose")
    app.pdf_context_widgets.pptx_scope_label.configure.assert_called_with(text="pdf.scope")
    app.pdf_context_widgets.pptx_process_button.configure.assert_called_with(text="pdf.process")
    app.pdf_context_widgets.pptx_file_label.configure.assert_called_with(textvariable=app.pdf_file_var)
    app.pptx_context_widgets.pptx_choose_button.configure.assert_not_called()
    assert app.pptx_path is None and app.pptx_metrics is None and app.pptx_preview_state==DocumentPreviewState()
    assert not app.tabs._segmented_button.visible
