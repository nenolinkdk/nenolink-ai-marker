from pathlib import Path
import inspect
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
from customtkinter import CTkTabview

from nenolink_ai_marker.ui_state import ContentWorkspaceState, DocumentPreviewState, DocumentScopeState, pptx_item_selection, show_welcome
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
    def __init__(self):self.values=[]
    def configure(self,**values):self.values=list(values.get("values",self.values))


class _Tabs:
    def __init__(self):self._segmented_button=_Segmented(); self.current=""
    def set(self,value):self.current=value
    def get(self):return self.current


def _pptx_preview_app(source: Path, badge: Path):
    app=SimpleNamespace(
        translator=_Translator(), workspace_state=SimpleNamespace(active="pptx"),
        pptx_path=None, pptx_metrics=None,
        pptx_preview_renderer=PptxPreviewRenderer(), pptx_processor=PptxProcessor(),
        _pptx_warning_approved=None, pptx_file_var=_Variable(), status_var=_Variable(),
        pptx_preview_state=DocumentPreviewState(), pdf_preview_state=DocumentPreviewState(),
        pptx_selection_mode_var=_Variable("all"), pptx_selection_display_var=_Variable(), pptx_single_var=_Variable("1"),
        pptx_selected_var=_Variable("1, 3"), pptx_range_start_var=_Variable("1"), pptx_range_end_var=_Variable("2"),
        badge_var=_Variable(badge.name), badges=BadgeRepository(badge.parent),
        pptx_preview_photo=None, pptx_preview_label=Mock(), pptx_slide_status=Mock(),
        pptx_previous_button=Mock(), pptx_next_button=Mock(),
        settings=lambda:MarkerSettings(), _logo_path=lambda:None,
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


def test_content_workspace_switch_starts_a_clean_media_context():
    state=ContentWorkspaceState()
    assert state.switch("video",[Path("photo.png")])==[]
    assert state.media_sources["image"]==[]
    assert state.switch("image",[Path("clip.mp4")])==[]
    assert state.media_sources["video"]==[]


def test_document_workspace_does_not_retain_hidden_media_selections():
    state=ContentWorkspaceState(); state.switch("video",[Path("photo.png")]); state.switch("pptx",[Path("clip.mp4")])
    assert state.media_sources=={"image":[],"video":[]}
    assert state.switch("image",[])==[]
    state.clear()
    assert state.active=="image" and state.media_sources=={"image":[],"video":[]}


@pytest.mark.parametrize(
    ("mode", "values", "expected"),
    [
        ("single", {"single": "3"}, (3,)),
        ("selected", {"selected": "2, 4, 7"}, (2, 4, 7)),
        ("range", {"start": "3", "end": "6"}, (3, 4, 5, 6)),
        ("all", {}, (1, 2, 3, 4, 5, 6, 7)),
    ],
)
def test_pptx_ui_selection_modes(mode, values, expected):
    assert pptx_item_selection(mode, **values).resolve(7) == expected


def test_pptx_ui_rejects_invalid_slide_input():
    with pytest.raises(ValueError, match="whole numbers"):
        pptx_item_selection("selected", selected="2, slide 4")


def test_document_workspace_headings_share_the_compact_top_row():
    source = inspect.getsource(MarkerApp._document_ui)
    assert 'document_format_label=ctk.CTkLabel(panel' in source
    assert 'document_format_label.grid(row=0,column=0' in source
    assert 'pptx_scope_label=ctk.CTkLabel(panel' in source
    assert 'pptx_scope_label.grid(row=0,column=1' in source
    assert 'panel.grid(row=0,column=0,padx=20,pady=(4,8)' in source
    assert 'pptx_controls.grid(row=1,column=0,columnspan=2,rowspan=2,padx=12,pady=(0,8)' in source


def test_production_navigation_exposes_pdf_and_powerpoint_but_not_word():
    build_source = inspect.getsource(MarkerApp._build_ui)
    translation_source = inspect.getsource(MarkerApp.apply_translations)
    assert 'values=["PDF","PowerPoint / Slides"]' in build_source
    assert 'values=["PDF","PowerPoint / Slides","Word"]' not in build_source
    assert 'content_pairs=(("image","content.images"),("video","content.video"),("pdf","content.pdf"),("pptx","content.powerpoint"))' in translation_source
    assert 'self.document_navigation.configure(values=[t("content.pdf"),t("content.powerpoint")])' in translation_source
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
    document_navigation = next(line for line in source.splitlines() if 'self.document_navigation=ctk.CTkSegmentedButton' in line)
    assert 'width=' not in document_navigation
    format_button_center = 3 + 16 + (26 / 2)
    workspace_tab_center = 9 + CTkTabview._outer_spacing + (CTkTabview._button_height / 2)
    assert format_button_center == workspace_tab_center


def _navigation_app(active="image"):
    app=SimpleNamespace(
        workspace_state=SimpleNamespace(active=active,media_sources={"image":[],"video":[]}), active_auxiliary=None,
        content_display_to_kind={"Images":"image","Video":"video","PDF":"pdf","PowerPoint":"pptx"},
        tab_names={"single":"Single File","documents":"Document Workspace","batch":"Batch Processing","badges":"Badges","inspect":"Inspect File"},
        tabs=_Tabs(),sources=[],scan=None,pdf_path=None,pptx_path=None,tools_navigation=Mock(),media_navigation_var=_Variable(),document_navigation_var=_Variable(),
        reset_format_context=Mock(),video_controls=Mock(),_update_logo_controls=Mock(),update_preview=Mock(),_render_document_workspace=Mock(),
        language_menu=Mock(),reset_button=Mock(),guide_button=Mock(),media_navigation=Mock(),document_navigation=Mock(),translator=_Translator(),
    )
    app._secondary_navigation_keys=MethodType(MarkerApp._secondary_navigation_keys,app)
    app._configure_secondary_navigation=MethodType(MarkerApp._configure_secondary_navigation,app)
    app._format_has_active_work=MethodType(MarkerApp._format_has_active_work,app)
    app._set_format_navigation=MethodType(MarkerApp._set_format_navigation,app)
    app._restore_top_level_navigation=MethodType(MarkerApp._restore_top_level_navigation,app)
    app.switch_top_level=MethodType(MarkerApp.switch_top_level,app)
    app._switch_top_level=MethodType(MarkerApp._switch_top_level,app)
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
    assert app.workspace_state.active==target
    assert app.reset_format_context.call_args_list==[call(source),call(target)]
    expected=("documents",) if target in {"pdf","pptx"} else ("single","batch")
    assert app._secondary_navigation_keys()==expected
    assert app.tabs.current==(app.tab_names["documents"] if target in {"pdf","pptx"} else app.tab_names["single"])


def test_format_switch_cancel_preserves_everything_and_continue_clears_both_contexts():
    app=_navigation_app("image"); app.sources=[Path("active.png")]; app._confirm_format_switch=Mock(return_value=False)
    MarkerApp.change_content_workspace(app,"PDF")
    assert app.workspace_state.active=="image" and app.sources==[Path("active.png")]
    app.reset_format_context.assert_not_called()
    app._confirm_format_switch.return_value=True
    MarkerApp.change_content_workspace(app,"PDF")
    assert app.workspace_state.active=="pdf"
    assert app.reset_format_context.call_args_list==[call("image"),call("pdf")]


@pytest.mark.parametrize("tool",["badges","inspect"])
def test_auxiliary_entry_cancel_preserves_work_and_continue_clears_active_format(tool):
    app=_navigation_app("pptx"); app.pptx_path=Path("active.pptx"); app.translator=_Translator(); app._render_inspection=Mock()
    app.inspection_path=None; app.inspection_result=None; app.inspection_error=""
    app._confirm_format_switch=Mock(return_value=False)
    MarkerApp.change_auxiliary_workspace(app,tool)
    assert app.active_auxiliary is None and app.pptx_path==Path("active.pptx")
    app.reset_format_context.assert_not_called()
    app._confirm_format_switch.return_value=True
    MarkerApp.change_auxiliary_workspace(app,tool)
    assert app.active_auxiliary==tool
    app.reset_format_context.assert_called_once_with("pptx")
    assert app.tabs.current==app.tab_names[tool]


@pytest.mark.parametrize("tool,target",[(tool,target) for tool in ("badges","inspect") for target in ("image","video","pdf","pptx")])
def test_leaving_auxiliary_for_any_format_opens_clean_destination(tool,target):
    labels={"image":"Images","video":"Video","pdf":"PDF","pptx":"PowerPoint"}; app=_navigation_app("image"); app.active_auxiliary=tool
    MarkerApp.change_content_workspace(app,labels[target])
    assert app.active_auxiliary is None and app.workspace_state.active==target
    assert call(target) in app.reset_format_context.call_args_list


def test_batch_is_internal_and_clears_incompatible_single_file_state():
    app=_navigation_app("image"); app.internal_workspace="single"; app.tabs.current=app.tab_names["batch"]
    MarkerApp._on_internal_workspace_changed(app)
    app.reset_format_context.assert_called_once_with("image")
    assert app.internal_workspace=="batch"


def test_global_reset_is_an_unconditional_locked_state_recovery_path():
    source=inspect.getsource(MarkerApp.reset_application)
    assert "active_auxiliary=None" in source
    assert "workspace_state.clear()" in source
    assert "_reset_application_state()" in source
    assert "_confirm_format_switch(" not in source and "askokcancel" not in source
    assert "_format_switch_dialog.destroy()" in inspect.getsource(MarkerApp._reset_application_state)


def test_media_cannot_open_document_tab_and_documents_cannot_open_media_tabs():
    app=SimpleNamespace(workspace_state=SimpleNamespace(active="video"),tabs=_Tabs(),tab_names={"single":"Single","documents":"Documents","batch":"Batch","badges":"Badges","inspect":"Inspect"})
    app._secondary_navigation_keys=MethodType(MarkerApp._secondary_navigation_keys,app)
    MarkerApp.show_tab(app,"documents"); assert app.tabs.current==""
    MarkerApp.show_tab(app,"single"); assert app.tabs.current=="Single"
    app.workspace_state.active="pdf"; app.tabs.current=""
    MarkerApp.show_tab(app,"single"); MarkerApp.show_tab(app,"batch"); MarkerApp.show_tab(app,"inspect"); assert app.tabs.current==""
    MarkerApp.show_tab(app,"documents"); assert app.tabs.current=="Documents"


def test_document_inspect_is_global_but_pdf_and_pptx_processing_remains_unsupported():
    assert ".pdf" not in INSPECT_EXTENSIONS and ".pptx" not in INSPECT_EXTENSIONS
    app=SimpleNamespace(workspace_state=SimpleNamespace(active="pdf"))
    assert MarkerApp._secondary_navigation_keys(app)==("documents",)
    assert 'INSPECT_EXTENSIONS | {".pdf",".pptx"}' in inspect.getsource(MarkerApp.choose_inspection_file)


def test_docx_ui_exposes_only_reliable_alignment_and_hides_margin_controls():
    source = inspect.getsource(MarkerApp.apply_translations)
    assert 't("docx.position.left"):"bottom-left"' in source
    assert 't("docx.position.center"):"center"' in source
    assert 't("docx.position.right"):"bottom-right"' in source
    assert 'self.pptx_margin_label.grid_remove()' in source
    assert 'self.pptx_logo_margin_label.grid_remove()' in source


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
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.badge_var.set("missing.png")
    MarkerApp.update_pptx_preview(app)
    app.pptx_preview_label.configure.assert_called_with(image=None,text="pptx.preview_unavailable")


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


def test_pptx_scope_change_starts_a_fresh_context_at_slide_one(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.pptx_metrics=app.pptx_processor.document_metrics(source)
    app.pptx_selection_display_to_value={"All":"all","Single":"single","Selected":"selected","Range":"range"}
    app._update_pptx_selection_fields=Mock(); app.update_pptx_preview=Mock(); app.pptx_preview_state.initialize(10); app.pptx_preview_state.move(3)
    MarkerApp.change_pptx_selection_mode(app,"Single")
    assert app.pptx_single_var.get()=="1" and app.pptx_preview_state.current==1
    app.pptx_selected_var.set("2,5,8"); MarkerApp.change_pptx_selection_mode(app,"Selected")
    assert app.pptx_preview_state.current==1 and app.pptx_selected_var.get()==""
    app.pptx_range_start_var.set("3"); app.pptx_range_end_var.set("7"); MarkerApp.change_pptx_selection_mode(app,"Range")
    assert app.pptx_preview_state.current==1 and (app.pptx_range_start_var.get(),app.pptx_range_end_var.get())==("1","2")
    MarkerApp.change_pptx_selection_mode(app,"All")
    assert app.pptx_preview_state.current==1
    MarkerApp.change_pptx_selection_mode(app,"Single")
    MarkerApp.change_pptx_preview_slide(app,3)
    assert app.pptx_preview_state.current==4 and app.pptx_single_var.get()=="4"


def test_pdf_scope_is_independent_from_physical_preview_navigation():
    app=SimpleNamespace(
        workspace_state=SimpleNamespace(active="pdf"), pdf_preview_state=DocumentPreviewState(),
        pptx_metrics=None, pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=8)),
        pptx_selection_mode_var=_Variable("selected"), pptx_single_var=_Variable("1"), pptx_selected_var=_Variable("2,5,8"),
        pptx_range_start_var=_Variable("1"), pptx_range_end_var=_Variable("2"),
        pptx_preview_photo=object(), update_pptx_preview=Mock(), status_var=_Variable(), translator=_Translator(),
        pptx_preview_label=Mock(), pptx_slide_status=Mock(), pptx_previous_button=Mock(), pptx_next_button=Mock(),
    )
    app.pdf_preview_state.initialize(8); app.update_pdf_preview=Mock()
    MarkerApp.change_pdf_preview_page(app,1); assert app.pdf_preview_state.current==2
    MarkerApp.change_pdf_preview_page(app,1); assert app.pdf_preview_state.current==3
    MarkerApp.change_pdf_preview_page(app,-1); assert app.pdf_preview_state.current==2
    assert app.pptx_selected_var.get()=="2,5,8"


def test_document_format_contexts_are_unloaded_instead_of_preserved():
    app=SimpleNamespace(
        processor=Mock(), pdf_path=Path("old.pdf"), pptx_path=Path("old.pptx"),
        pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=43)), pptx_metrics=SimpleNamespace(item_count=10),
        pdf_preview_state=DocumentPreviewState(), pptx_preview_state=DocumentPreviewState(),
        _pdf_warning_approved=object(),_pdf_signature_approved=object(),_pptx_warning_approved=object(),
        pptx_preview_renderer=Mock(), pptx_selection_mode_var=_Variable("selected"),pptx_single_var=_Variable("5"),
        pptx_selected_var=_Variable("2,5,8"),pptx_range_start_var=_Variable("3"),pptx_range_end_var=_Variable("7"),
        pptx_preview_photo=object(),pptx_preview_label=Mock(),pptx_slide_status=Mock(),pptx_previous_button=Mock(),pptx_next_button=Mock(),status_var=_Variable(),
    )
    app.pdf_preview_state.initialize(43); app.pdf_preview_state.move(11); app.pptx_preview_state.initialize(10)
    MarkerApp.reset_format_context(app,"pdf")
    assert app.pdf_path is None and app.pdf_info is None and (app.pdf_preview_state.current,app.pdf_preview_state.count)==(1,0)
    MarkerApp.reset_format_context(app,"pptx")
    assert app.pptx_path is None and app.pptx_metrics is None and (app.pptx_preview_state.current,app.pptx_preview_state.count)==(1,0)


def test_format_switch_clears_source_and_destination_contexts():
    app=SimpleNamespace(
        content_display_to_kind={"PowerPoint":"pptx"}, workspace_state=SimpleNamespace(active="pdf"), active_auxiliary=None, sources=[Path("old.pdf")],
        reset_format_context=Mock(), show_tab=Mock(), _render_document_workspace=Mock(), apply_translations=Mock(), tools_navigation=Mock(),
        _format_has_active_work=Mock(return_value=False), language_menu=Mock(),reset_button=Mock(),guide_button=Mock(),media_navigation=Mock(),document_navigation=Mock(),media_navigation_var=_Variable(),document_navigation_var=_Variable(),
    )
    MarkerApp.change_content_workspace(app,"PowerPoint")
    assert app.reset_format_context.call_args_list==[call("pdf"),call("pptx")]
    assert app.workspace_state.active=="pptx"


def test_pdf_scope_sequence_resets_navigation_and_old_scope_fields():
    app=SimpleNamespace(
        workspace_state=SimpleNamespace(active="pdf"), processor=Mock(),
        pdf_path=Path("document.pdf"), pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=43)),
        pdf_preview_state=DocumentPreviewState(5,43), _pdf_warning_approved=object(), _pdf_signature_approved=object(),
        pptx_selection_mode_var=_Variable("all"), pptx_single_var=_Variable("9"), pptx_selected_var=_Variable("2,5,8"),
        pptx_range_start_var=_Variable("3"), pptx_range_end_var=_Variable("7"), pptx_preview_photo=object(),
        pptx_selection_display_to_value={"All":"all","One":"single","Selected":"selected","Range":"range"},
        pptx_selection_display_var=_Variable("All"),
        _update_pptx_selection_fields=Mock(), update_pptx_preview=Mock(),update_pdf_preview=Mock(),translator=_Translator(),
        pptx_preview_label=Mock(),pptx_slide_status=Mock(),pptx_previous_button=Mock(),pptx_next_button=Mock(),status_var=_Variable(),
        language_menu=Mock(),reset_button=Mock(),guide_button=Mock(),media_navigation=Mock(),document_navigation=Mock(),tools_navigation=Mock(),
    )
    app.reset_format_context=MethodType(MarkerApp.reset_format_context,app)
    for label,mode in (("One","single"),("Selected","selected"),("Range","range"),("All","all")):
        MarkerApp.change_pptx_selection_mode(app,label)
        assert app.pptx_selection_mode_var.get()==mode
        assert app.pdf_preview_state.current==1 and app.pdf_preview_state.count==43
        assert (app.pptx_single_var.get(),app.pptx_selected_var.get(),app.pptx_range_start_var.get(),app.pptx_range_end_var.get())==("1","","1","2")


def test_visual_setting_callbacks_do_not_reset_document_context():
    for method in (MarkerApp.changed,MarkerApp.select_badge,MarkerApp.logo_changed,MarkerApp.change_position_display):
        assert "reset_format_context" not in inspect.getsource(method)


def _stateful_navigation_app(active="image"):
    app=_navigation_app(active); app.pdf_path=None; app.pptx_path=None
    def reset(kind):
        if kind in {"image","video"}:app.sources=[]; app.workspace_state.media_sources[kind]=[]
        elif kind=="pdf":app.pdf_path=None
        elif kind=="pptx":app.pptx_path=None
    app.reset_format_context=Mock(side_effect=reset)
    return app


@pytest.mark.parametrize("sequence",[
    ("image","pptx","image","pdf","video","pptx","pdf","image"),
    ("pdf","pptx","image","pdf"),
    ("image","pptx","image","video","pdf"),
    ("pptx","pdf","pptx","video","image"),
])
def test_repeated_top_level_sequences_never_retain_stale_files(sequence):
    app=_stateful_navigation_app(sequence[0])
    for target in sequence[1:]:
        if app.workspace_state.active in {"image","video"}:app.sources=[Path(f"active-{app.workspace_state.active}")]
        elif app.workspace_state.active=="pdf":app.pdf_path=Path("active.pdf")
        else:app.pptx_path=Path("active.pptx")
        assert MarkerApp.switch_top_level(app,target)
        assert app.workspace_state.active==target and app.active_auxiliary is None
        assert app.pdf_path is None and app.pptx_path is None and app.sources==[]
        expected=app.tab_names["documents"] if target in {"pdf","pptx"} else app.tab_names["single"]
        assert app.tabs.current==expected
        for control in (app.media_navigation,app.document_navigation,app.tools_navigation,app.reset_button):control.configure.assert_any_call(state="normal")


def test_pdf_badges_image_inspect_video_sequence_and_badges_back_are_defined():
    app=_stateful_navigation_app("pdf"); app.pdf_path=Path("active.pdf"); app._render_inspection=Mock(); app.inspection_path=None; app.inspection_result=None; app.inspection_error=""
    app.change_content_workspace=MethodType(MarkerApp.change_content_workspace,app)
    assert MarkerApp.switch_top_level(app,"badges") and app.active_auxiliary=="badges" and app.pdf_path is None
    assert MarkerApp.switch_top_level(app,"image") and app.tabs.current==app.tab_names["single"]
    assert MarkerApp.switch_top_level(app,"inspect") and app.active_auxiliary=="inspect"
    assert MarkerApp.switch_top_level(app,"video") and app.active_auxiliary is None and app.workspace_state.active=="video"
    assert MarkerApp.switch_top_level(app,"badges")
    assert MarkerApp.switch_top_level(app,"image")
    assert MarkerApp.switch_top_level(app,"badges")
    MarkerApp.navigate_home(app)
    assert app.workspace_state.active=="image" and app.tabs.current==app.tab_names["single"]


def test_global_reset_recovers_even_when_internal_reset_raises():
    app=SimpleNamespace(
        _reset_application_state=Mock(side_effect=RuntimeError("broken preview")),active_auxiliary="badges",
        workspace_state=ContentWorkspaceState(active="pdf"),sources=[Path("stale.pdf")],tools_navigation=Mock(),
        scan=object(),inspection_path=Path("old.png"),inspection_result=object(),inspection_error="old",pdf_path=Path("old.pdf"),pdf_info=object(),pptx_path=Path("old.pptx"),pptx_metrics=object(),
        pdf_preview_state=DocumentPreviewState(3,4),pptx_preview_state=DocumentPreviewState(2,5),pptx_preview_photo=object(),document_scope_states={"pdf":DocumentScopeState("range"),"pptx":DocumentScopeState("single")},
        media_navigation_var=_Variable(),document_navigation_var=_Variable(),content_display_to_kind={"Images":"image"},
        _configure_secondary_navigation=Mock(),render_start_view=Mock(),language_menu=Mock(),reset_button=Mock(),guide_button=Mock(),media_navigation=Mock(),document_navigation=Mock(),
    )
    MarkerApp.reset_application(app)
    assert app.workspace_state.active=="image" and app.sources==[] and app.active_auxiliary is None
    assert app.pdf_path is app.pptx_path is None and app.scan is None and app.inspection_path is None
    app.reset_button.configure.assert_called_with(state="normal")
