from pathlib import Path
import inspect
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from customtkinter import CTkTabview

from nenolink_ai_marker.ui_state import ContentWorkspaceState, DocumentPreviewState, pptx_item_selection, show_welcome
from nenolink_ai_marker.app import MarkerApp
from nenolink_ai_marker.badges import BadgeRepository
from nenolink_ai_marker.document_processing import ItemSelection
from nenolink_ai_marker.models import MarkerSettings
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


def _pptx_preview_app(source: Path, badge: Path):
    app=SimpleNamespace(
        translator=_Translator(), workspace_state=SimpleNamespace(active="pptx"),
        pptx_path=None, pptx_metrics=None, pptx_slide_number=7, pptx_slide_count=0,
        pptx_preview_renderer=PptxPreviewRenderer(), pptx_processor=PptxProcessor(),
        _pptx_warning_approved=None, pptx_file_var=_Variable(), status_var=_Variable(),
        document_preview_states={"pptx":DocumentPreviewState(),"pdf":DocumentPreviewState()},
        pptx_selection_mode_var=_Variable("all"), pptx_single_var=_Variable("1"),
        pptx_selected_var=_Variable("1, 3"), pptx_range_start_var=_Variable("1"), pptx_range_end_var=_Variable("2"),
        badge_var=_Variable(badge.name), badges=BadgeRepository(badge.parent),
        pptx_preview_photo=None, pptx_preview_label=Mock(), pptx_slide_status=Mock(),
        pptx_previous_button=Mock(), pptx_next_button=Mock(),
        settings=lambda:MarkerSettings(), _logo_path=lambda:None,
        _confirm_pptx_limits=lambda:True,
    )
    app._set_pptx_file_summary=MethodType(MarkerApp._set_pptx_file_summary,app)
    app.update_pptx_preview=MethodType(MarkerApp.update_pptx_preview,app)
    app._rebuild_document_preview_selection=MethodType(MarkerApp._rebuild_document_preview_selection,app)
    return app


def test_welcome_is_visible_without_an_image():
    assert show_welcome([])


def test_welcome_is_hidden_after_image_selection():
    assert not show_welcome(["selected.png"])


def test_welcome_returns_when_images_are_cleared():
    sources = ["selected.png"]
    sources.clear()
    assert show_welcome(sources)


def test_content_workspaces_preserve_image_and_video_selections_independently():
    state=ContentWorkspaceState()
    assert state.switch("video",[Path("photo.png")])==[]
    assert state.media_sources["image"]==[Path("photo.png")]
    assert state.switch("image",[Path("clip.mp4")])==[Path("photo.png")]
    assert state.media_sources["video"]==[Path("clip.mp4")]


def test_document_workspace_keeps_media_selections_and_reset_clears_all():
    state=ContentWorkspaceState(); state.switch("video",[Path("photo.png")]); state.switch("pptx",[Path("clip.mp4")])
    assert state.media_sources=={"image":[Path("photo.png")],"video":[Path("clip.mp4")]}
    assert state.switch("image",[])==[Path("photo.png")]
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
    document_navigation = next(line for line in source.splitlines() if 'self.document_navigation=ctk.CTkSegmentedButton' in line)
    assert 'width=' not in document_navigation
    format_button_center = 3 + 16 + (26 / 2)
    workspace_tab_center = 9 + CTkTabview._outer_spacing + (CTkTabview._button_height / 2)
    assert format_button_center == workspace_tab_center


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
    assert (app.pptx_slide_number,app.pptx_slide_count)==(1,10)
    app.pptx_preview_label.configure.assert_called_with(image="preview-image",text="")
    app.pptx_slide_status.configure.assert_called_with(text="pptx.slide_status")


def test_pptx_preview_navigation_changes_index_and_keeps_rendered_image(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.pptx_metrics=app.pptx_processor.document_metrics(source); app.pptx_slide_count=10; app.pptx_slide_number=1
    app.update_pptx_preview=MethodType(MarkerApp.update_pptx_preview,app)
    with patch("nenolink_ai_marker.app.ctk.CTkImage",return_value="preview-image"):
        app._rebuild_document_preview_selection()
        MarkerApp.change_pptx_preview_slide(app,1)
        assert app.pptx_slide_number==2
        MarkerApp.change_pptx_preview_slide(app,-1)
    assert app.pptx_slide_number==1
    assert app.pptx_preview_label.configure.call_args.kwargs["text"]==""


def test_missing_badge_replaces_stale_choose_placeholder_with_unavailable(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.badge_var.set("missing.png")
    MarkerApp.update_pptx_preview(app)
    app.pptx_preview_label.configure.assert_called_with(image=None,text="pptx.preview_unavailable")


def test_pptx_control_changes_refresh_preview_and_scope_rebuilds_it():
    changed_source=inspect.getsource(MarkerApp.changed)
    selection_source=inspect.getsource(MarkerApp.change_pptx_selection_mode)
    assert "self.update_pptx_preview()" in changed_source
    assert "self._rebuild_document_preview_selection()" in selection_source


def test_document_preview_state_rebuilds_all_single_arbitrary_and_range():
    state=DocumentPreviewState()
    assert state.rebuild(ItemSelection(),10)==1 and state.items==tuple(range(1,11))
    assert state.rebuild(ItemSelection("single",(1,)),10)==1 and state.items==(1,)
    assert state.move(1)==1
    assert state.rebuild(ItemSelection("selected",(2,5,8)),10)==2
    assert [state.current,state.move(1),state.move(1),state.move(-1),state.move(-1)]==[2,5,8,5,2]
    assert state.rebuild(ItemSelection("range",start=3,end=7),10)==3 and state.items==(3,4,5,6,7)


def test_pptx_scope_change_rebuilds_preview_from_first_selected_slide(tmp_path):
    source=tmp_path/"ten-slides.pptx"; _create_pptx(source,10)
    badge=tmp_path/"ai-assisted.png"; _write_overlay(badge,(190,20,40,255),(160,50))
    app=_pptx_preview_app(source,badge); app.pptx_path=source; app.pptx_metrics=app.pptx_processor.document_metrics(source)
    app.pptx_selection_display_to_value={"All":"all","Single":"single","Selected":"selected","Range":"range"}
    app._update_pptx_selection_fields=Mock(); app.update_pptx_preview=Mock()
    app._rebuild_document_preview_selection()
    assert app.document_preview_states["pptx"].items==tuple(range(1,11))
    app.pptx_single_var.set("1"); MarkerApp.change_pptx_selection_mode(app,"Single")
    assert app.document_preview_states["pptx"].items==(1,) and app.pptx_slide_number==1
    app.pptx_selected_var.set("2,5,8"); MarkerApp.change_pptx_selection_mode(app,"Selected")
    assert app.document_preview_states["pptx"].items==(2,5,8) and app.pptx_slide_number==2
    app.pptx_range_start_var.set("3"); app.pptx_range_end_var.set("7"); MarkerApp.change_pptx_selection_mode(app,"Range")
    assert app.document_preview_states["pptx"].items==(3,4,5,6,7) and app.pptx_slide_number==3


def test_pdf_selection_uses_same_preview_sequence_semantics():
    app=SimpleNamespace(
        workspace_state=SimpleNamespace(active="pdf"), document_preview_states={"pdf":DocumentPreviewState()},
        pptx_metrics=None, pdf_info=SimpleNamespace(metrics=SimpleNamespace(item_count=8)),
        pptx_selection_mode_var=_Variable("selected"), pptx_single_var=_Variable("1"), pptx_selected_var=_Variable("2,5,8"),
        pptx_range_start_var=_Variable("1"), pptx_range_end_var=_Variable("2"), pptx_slide_number=1, pptx_slide_count=0,
        pptx_preview_photo=object(), update_pptx_preview=Mock(), status_var=_Variable(), translator=_Translator(),
        pptx_preview_label=Mock(), pptx_slide_status=Mock(), pptx_previous_button=Mock(), pptx_next_button=Mock(),
    )
    assert MarkerApp._rebuild_document_preview_selection(app)
    assert app.document_preview_states["pdf"].items==(2,5,8) and app.pptx_slide_number==2
    app.update_pdf_preview=Mock(); MarkerApp.change_pdf_preview_page(app,1); assert app.pptx_slide_number==5
    MarkerApp.change_pdf_preview_page(app,1); assert app.pptx_slide_number==8
    MarkerApp.change_pdf_preview_page(app,-1); assert app.pptx_slide_number==5
