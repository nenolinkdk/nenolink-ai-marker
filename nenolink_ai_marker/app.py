from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import subprocess
import webbrowser
from tkinter import TclError, filedialog, messagebox
import customtkinter as ctk
from PIL import Image

from . import __version__
from .badges import BadgeSourceManager, choose_badge_selection
from .batch import BatchProcessor, BatchResult, FolderScan, VIDEO_EXTENSIONS, destination_root, extract_video_frame, find_ffmpeg, hidden_subprocess_kwargs, is_above_recommended_size, scan_folder
from .config import ConfigStore
from .document_processing import ItemSelection, ProcessingRequest, settings_for_documents
from .image_output import ImageProcessingRequest
from .document_limits import DocumentMetrics, assess_document
from .guide import open_user_guide
from .i18n import LANGUAGES, Translator
from .inspection import INSPECT_EXTENSIONS, InspectionResult, human_file_size, inspect_file
from .metadata import marker_metadata
from .models import MarkerSettings
from .paths import badge_directory, locale_directory, localized_user_guide_path, welcome_image_path
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS
from .preview import ImagePreviewRenderer
from .pptx_processor import PptxProcessor
from .pptx_preview import PptxPreviewRenderer
from .pptx_state import PptxWorkspaceState, PptxEvent, apply_pptx_visual_event
from .pptx_workspace import PptxWorkspace, PPTX_STATE_TOKEN
from .workspace_state import ImageWorkspaceState, VideoWorkspaceState, PdfWorkspaceState, visual_projection, PdfEvent, apply_pdf_event
from .image_workspace import ImageWorkspace
from .video_workspace import VideoWorkspace
from .pdf_workspace import PdfWorkspace
from .workspace_ui import WORKSPACE_LAYOUT, build_badge_section, build_logo_section, build_workspace_control_template, build_badge_visual
from .pdf_processor import PasswordProtectedPdfError, PdfInfo, PdfProcessor
from .pdf_preview import PdfPreviewRenderer
from .docx_processor import DocxInfo, DocxProcessor
from .docx_preview import DocxPreviewRenderer
from .shortcut import ShortcutError, create_desktop_shortcut
from .ui_state import DocumentPreviewState, DocumentScopeState, pptx_item_selection, show_welcome
from .update_check import UpdateCheckError, check_for_update, is_approved_update_url, should_check_automatically
from .shell_controller import DESTINATIONS, ShellController, placeholder_for, shell_transition_spec, ShellTransitionExecutor

def _runtime_boot_logger():
    """Return a flushed application logger for packaged runtime diagnostics."""
    path = os.environ.get("NENOLINK_BOOT_LOG")
    def write(message: str) -> None:
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8") as stream:
                stream.write(str(message) + "\n")
                stream.flush()
        except OSError:
            return
    return write

class _ShellRuntimeAdapter:
    def __init__(self, app):
        self.app = app
        self.destination_lookup = "not_attempted"
        self.resolved_workspace = ""
        self.mount_result = "not_attempted"
        self.project_result = "not_attempted"
        self.tool_result = "not_attempted"
        self.cleared_workspaces = []
        self.clear_failures = []
    def begin_receipt(self, spec):
        self.destination_lookup = "not_attempted"
        self.resolved_workspace = ""
        self.mount_result = "not_attempted"
        self.project_result = "not_attempted"
        self.tool_result = "not_attempted"
        self.cleared_workspaces = []
        self.clear_failures = []
    def preserve_source(self): return None
    def clear_source(self, source): self.app._workspace_registry[source].clear_runtime_state()
    def clean_destination(self, destination): self.app._workspace_registry[destination].enter_clean()
    def clear_all_workspaces(self):
        for source in DESTINATIONS:
            try:
                self.app._workspace_registry[source].clear_runtime_state()
                self.cleared_workspaces.append(source)
            except Exception as error:
                self.clear_failures.append(f"{source}: {type(error).__name__}: {error}")
                raise
    def unmount_source(self, source): self.app._workspace_registry[source].unmount()
    def mount_destination(self, destination):
        self.destination_lookup = "success" if destination in self.app._workspace_registry else "failure"
        workspace = self.app._workspace_registry[destination]
        self.resolved_workspace = type(workspace).__name__
        # Commit the destination in the authoritative Shell FSM before any
        # destination mount/projection can observe or render it.
        if self.app.shell_controller.active_content_type != destination:
            self.app.shell_controller.dispatch(destination)
        workspace.mount(self.app.content_host)
        self.mount_result = "success"
    def project_destination(self, destination):
        self.app._workspace_registry[destination].project()
        self.project_result = "success"
        self.app.mounted_view = destination.upper()
    def mount_tool(self, tool):
        self.app._mount_tool(tool)
        self.app.shell_controller.dispatch(tool)
        self.tool_result = "success"
        self.app.mounted_view = tool.upper()
    def unmount_tool(self): self.app._unmount_tool()
    def clear_tool(self): self.app.shell_controller.active_tool = None
    def record_receipt(self, receipt):
        self.app.last_shell_receipt = receipt
        self.app.shell_controller.receipts.append(receipt)


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    """A local scroll area whose scrollbar is only shown on overflow."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scrollbar_needed = True
        self.bind("<Configure>", self._schedule_scrollbar_update, add="+")
        self._parent_canvas.bind("<Configure>", self._schedule_scrollbar_update, add="+")

    def _schedule_scrollbar_update(self, _event=None):
        self.after_idle(self.update_scrollbar_visibility)

    def update_scrollbar_visibility(self):
        bounds = self._parent_canvas.bbox("all")
        needed = bool(bounds and bounds[3] - bounds[1] > self._parent_canvas.winfo_height() + 1)
        if needed and not self.scrollbar_needed:
            self._scrollbar.grid(row=1, column=1, sticky="nsew")
        elif not needed and self.scrollbar_needed:
            self._scrollbar.grid_remove(); self._parent_canvas.yview_moveto(0)
        self.scrollbar_needed = needed


class LegacyMarkerApp(ctk.CTk):
    def __init__(self) -> None:
        boot_log=os.environ.get("NENOLINK_BOOT_LOG")
        def boot(message):
            if boot_log:
                with open(boot_log,"a",encoding="utf-8") as stream:stream.write(message+"\n")
        self._boot=boot
        boot("MarkerApp init started")
        boot(f"Tk paths ready: {os.environ.get('TCL_LIBRARY')}")
        super().__init__(); boot("CTk initialized")
        self.geometry("1280x720"); self.minsize(980, 680)
        self.processor = ImageProcessor(); self.preview_renderer = ImagePreviewRenderer(self.processor); self.batch_processor = BatchProcessor(self.processor)
        self.config_store = ConfigStore(); saved = self.config_store.load()
        # Clean v1.0.3 sessions start in English; locale changes are explicit
        # global events and are projected without rebuilding workspaces.
        self.translator = Translator(locale_directory(), saved.language)
        self.badge_sources = BadgeSourceManager(badge_directory())
        self.badges = self.badge_sources.repository(saved.badge_source, saved.custom_badge_folder)
        self.sources: list[Path] = []; self.media_sources={"image":[],"video":[]}; self.scan: FolderScan | None = None
        self.active_content_type="image"; self.active_runtime_context_type="image"; self.active_tool: str | None = None; self.active_media_mode="single"; self.visible_workspace_type="image"; self._format_switch_dialog=None
        self.pptx_path: Path | None = None; self.pptx_processor=PptxProcessor(); self.pptx_preview_renderer=PptxPreviewRenderer(self.processor)
        self.pptx_metrics: DocumentMetrics | None=None; self._pptx_warning_approved=None
        self.pptx_preview_photo=None
        self.pptx_preview_state=DocumentPreviewState(); self.pdf_preview_state=DocumentPreviewState()
        self.document_scope_states={"pdf":DocumentScopeState(),"pptx":DocumentScopeState()}
        self.pdf_path: Path | None=None; self.pdf_processor=PdfProcessor(); self.pdf_preview_renderer=PdfPreviewRenderer(self.processor); self.pdf_info: PdfInfo | None=None; self._pdf_warning_approved=None; self._pdf_signature_approved=None
        self.docx_path: Path | None=None; self.docx_processor=DocxProcessor(); self.docx_preview_renderer=DocxPreviewRenderer(self.processor); self.docx_info: DocxInfo | None=None; self._docx_warning_approved=None
        self.inspection_path: Path | None = None; self.inspection_result: InspectionResult | None = None; self.inspection_error = ""; self.inspection_unsupported=False
        self._reset_after_id = None
        self._automatic_update_attempted = False; self._update_check_running = False
        self._available_update_version = ""; self._available_update_url = ""
        self.cancel_event = threading.Event(); self.preview_photo = None; self.preview_image = None; self.badge_photo = None; self.single_badge_photo = None; self.welcome_photo = None; self.welcome_image = None
        self.gallery_photos = []; self.gallery_buttons = {}; self.badge_display_to_file = {}
        self.badge_var=ctk.StringVar(value=saved.badge_name); self.position_var=ctk.StringVar(value=saved.position)
        self.position_display_var=ctk.StringVar()
        self.size_var=ctk.IntVar(value=saved.size_percent); self.margin_var=ctk.IntVar(value=saved.margin); self.opacity_var=ctk.IntVar(value=saved.opacity)
        self.language_var=ctk.StringVar(value=Translator.language_name(saved.language)); self.badge_source_var=ctk.StringVar(value=saved.badge_source)
        self.custom_badge_var=ctk.StringVar(value=saved.custom_badge_folder); self.input_folder_var=ctk.StringVar(value=saved.input_folder)
        self.output_preference_var=ctk.StringVar(value=saved.output_preference); self.output_folder_var=ctk.StringVar(value=saved.output_folder)
        self.output_subfolder_var=ctk.StringVar(value=saved.output_subfolder); self.batch_suffix_var=ctk.StringVar(value=saved.batch_filename_suffix); self.recursive_var=ctk.BooleanVar(value=saved.include_subfolders)
        self.preserve_var=ctk.BooleanVar(value=saved.preserve_folder_structure); self.images_var=ctk.BooleanVar(value=saved.process_images)
        self.videos_var=ctk.BooleanVar(value=saved.process_videos); self.skip_var=ctk.BooleanVar(value=saved.skip_processed)
        self.video_mode_var=ctk.StringVar(value=saved.video_mode); self.video_mode_display_var=ctk.StringVar(); self.video_duration_var=ctk.IntVar(value=saved.video_duration)
        self.logo_enabled_var=ctk.BooleanVar(value=saved.logo_enabled); self.logo_path_var=ctk.StringVar(value=saved.logo_path); self.logo_filename_var=ctk.StringVar(value=Path(saved.logo_path).name if saved.logo_path else "—")
        self.logo_position_var=ctk.StringVar(value=saved.logo_position); self.logo_position_display_var=ctk.StringVar()
        self.logo_size_var=ctk.IntVar(value=saved.logo_size_percent); self.logo_margin_var=ctk.IntVar(value=saved.logo_margin); self.logo_opacity_var=ctk.IntVar(value=saved.logo_opacity)
        self.automatic_update_var=ctk.BooleanVar(value=saved.automatic_update_check); self.last_update_check=saved.last_update_check
        self.shortcut_offer_shown=saved.shortcut_offer_shown; self.shortcut_offer_dialog=None
        self.status_var=ctk.StringVar(); self.badge_name_var=ctk.StringVar(); self.badge_description_var=ctk.StringVar(); self.badge_display_var=ctk.StringVar()
        self.scan_summary_var=ctk.StringVar(); self.progress_text_var=ctk.StringVar()
        self.pdf_file_var=ctk.StringVar(); self.pptx_file_var=ctk.StringVar(); self.pptx_selection_mode_var=ctk.StringVar(value="all"); self.pptx_selection_display_var=ctk.StringVar()
        self.pdf_badge_enabled_var=ctk.BooleanVar(value=True)
        self.docx_scope_var=ctk.StringVar(value="entire-document")
        self.pptx_selected_var=ctk.StringVar(value="1, 3"); self.pptx_range_var=ctk.StringVar(value="1-2"); self.pptx_language_var=ctk.StringVar(value=Translator.language_name("en"))
        self.inspect_file_var=ctk.StringVar(); self.inspect_format_var=ctk.StringVar(); self.inspect_status_var=ctk.StringVar(); self.inspect_software_var=ctk.StringVar(); self.inspect_label_var=ctk.StringVar(); self.inspect_version_var=ctk.StringVar(); self.inspect_message_var=ctk.StringVar()
        self._build_ui(); boot("UI built"); self.apply_translations(); self.refresh_badges(False); self._validate_saved_logo(); boot("resources loaded"); self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(250, self._automatic_update_check)
        if os.environ.get("NENOLINK_VERIFY_FILE_DIALOG") == "1":
            self.after(800, self.image_workspace_owner.choose_files)
        if os.environ.get("NENOLINK_VERIFY_BADGE_FOLDER_DIALOG") == "1":
            self.after(800, self.browse_custom_badges)
        elif getattr(sys,"frozen",False) and not self.shortcut_offer_shown:
            self.after(700,self._show_first_run_shortcut_offer)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(1,weight=1)
        header=ctk.CTkFrame(self,corner_radius=0); header.grid(row=0,column=0,sticky="ew"); header.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(header,text="Nenolink AI Marker",font=ctk.CTkFont(size=24,weight="bold")).grid(row=0,column=0,padx=20,pady=14)
        self.update_notification=ctk.CTkLabel(header,text="",text_color="#d62828",font=ctk.CTkFont(weight="bold"),cursor="hand2")
        self.update_notification.grid(row=0,column=1,padx=8); self.update_notification.bind("<Button-1>",self._open_update_page); self.update_notification.grid_remove()
        self.language_menu=ctk.CTkOptionMenu(header,variable=self.language_var,values=list(LANGUAGES),command=self.change_language,width=150); self.language_menu.grid(row=0,column=2,padx=8)
        self.reset_button=ctk.CTkButton(header,text="",command=lambda:self.dispatch_shell_event("reset"),width=100); self.reset_button.grid(row=0,column=3,padx=8)
        self.guide_button=ctk.CTkButton(header,text="",command=self.open_guide,width=170); self.guide_button.grid(row=0,column=4,padx=(8,20))
        self.content_display_to_kind={}; self.content_buttons={}
        self.content_navigation_frame=ctk.CTkFrame(self,height=1,fg_color=("gray90","gray18"),corner_radius=8); self.content_navigation_frame.grid(row=1,column=0,padx=20,pady=0,sticky="nw")
        group_font=ctk.CTkFont(size=13,weight="bold")
        media_group=ctk.CTkFrame(self.content_navigation_frame,height=1,fg_color="transparent"); media_group.grid(row=0,column=0,padx=(8,6),pady=(3,3),sticky="w")
        self.media_group_label=ctk.CTkLabel(media_group,text="",text_color=("gray35","gray75"),font=group_font,height=16); self.media_group_label.grid(row=0,column=0,pady=0,sticky="w")
        self.media_navigation=ctk.CTkFrame(media_group,fg_color="transparent"); self.media_navigation.grid(row=1,column=0,pady=0,sticky="w")
        ctk.CTkFrame(self.content_navigation_frame,width=1,height=1,fg_color=("gray72","gray35")).grid(row=0,column=1,padx=4,pady=4,sticky="ns")
        documents_group=ctk.CTkFrame(self.content_navigation_frame,height=1,fg_color="transparent"); documents_group.grid(row=0,column=2,padx=(6,8),pady=(3,3),sticky="w")
        self.documents_group_label=ctk.CTkLabel(documents_group,text="",text_color=("gray35","gray75"),font=group_font,height=16); self.documents_group_label.grid(row=0,column=0,pady=0,sticky="w")
        self.document_navigation=ctk.CTkFrame(documents_group,fg_color="transparent"); self.document_navigation.grid(row=1,column=0,pady=0,sticky="w")
        ctk.CTkFrame(self.content_navigation_frame,width=1,height=1,fg_color=("gray72","gray35")).grid(row=0,column=3,padx=4,pady=4,sticky="ns")
        tools_group=ctk.CTkFrame(self.content_navigation_frame,height=1,fg_color="transparent"); tools_group.grid(row=0,column=4,padx=(6,8),pady=(3,3),sticky="w")
        self.tools_group_label=ctk.CTkLabel(tools_group,text="",text_color=("gray35","gray75"),font=group_font,height=16); self.tools_group_label.grid(row=0,column=0,pady=0,sticky="w")
        self.tools_navigation=ctk.CTkSegmentedButton(tools_group,values=["Badges","Inspect File"],command=self.change_auxiliary_workspace,height=26,dynamic_resizing=True); self.tools_navigation.grid(row=1,column=0,pady=0,sticky="w")
        self.tabs=ctk.CTkTabview(self,command=self._on_media_mode_changed); self.tabs.grid(row=1,column=0,padx=16,pady=(9,8),sticky="nsew")
        self.content_navigation_frame.lift()
        # PDF and PPTX own separate, direct contexts.  The tabview's own
        # selector is only the compact secondary navigation for media.
        self.tab_names={"single":self.translator.text("tab.single"),"batch":self.translator.text("tab.batch"),"badges":self.translator.text("tab.badges"),"inspect":self.translator.text("tab.inspect"),"pdf":"__pdf_context__","pptx":"__pptx_context__"}
        self.single_tab=self.tabs.add(self.tab_names["single"]); self.batch_tab=self.tabs.add(self.tab_names["batch"]); self.settings_tab=self.tabs.add(self.tab_names["badges"]); self.inspect_tab=self.tabs.add(self.tab_names["inspect"]); self.pdf_tab=self.tabs.add(self.tab_names["pdf"]); self.pptx_tab=self.tabs.add(self.tab_names["pptx"])
        # Only the active content owns live widgets.  PDF/PPTX contexts are
        # created by the central transition controller, never by navigation.
        # Image and Video controls are mounted exclusively by their workspaces.
        self._batch_ui(); self._settings_ui(); self._inspect_ui()
        self.pdf_context_widgets=None; self.pptx_context_widgets=None
        footer=ctk.CTkFrame(self,corner_radius=0,fg_color="transparent"); footer.grid(row=2,column=0,padx=20,pady=(0,8),sticky="ew"); footer.grid_columnconfigure(1,weight=1)
        footer_left=ctk.CTkFrame(footer,corner_radius=0,fg_color="transparent"); footer_left.grid(row=0,column=0,sticky="w")
        self.footer_copyright_label=ctk.CTkLabel(footer_left,text=f"© Copyright Henrik Nielsen - nenolink.com · v{__version__} ·",text_color="gray60"); self.footer_copyright_label.grid(row=0,column=0,sticky="w")
        self.footer_update_link=ctk.CTkLabel(footer_left,text="",text_color="gray60",cursor="hand2"); self.footer_update_link.grid(row=0,column=1,padx=(4,0),sticky="w"); self._footer_update_callback=lambda _event:self.check_for_updates(); self.footer_update_link.bind("<Button-1>",self._footer_update_callback)
        self.status_label=ctk.CTkLabel(footer,textvariable=self.status_var,text_color="gray60",anchor="e"); self.status_label.grid(row=0,column=1,padx=(20,0),sticky="ew")

    def _secondary_navigation_keys(self):
        if self.active_tool in {"badges","inspect"}:
            return ()
        if self.active_content_type in {"pdf","pptx"}:
            return ()
        return ("single","batch")

    def _configure_secondary_navigation(self,preferred=None):
        keys=self._secondary_navigation_keys(); values=[self.tab_names[key] for key in keys]
        if keys:
            self.tabs._segmented_button.configure(values=values); self.tabs._segmented_button.grid()
            target=preferred if preferred in keys else "single"
        else:
            self.tabs._segmented_button.grid_remove()
            target=self.active_tool or self.active_content_type
        self.tabs.set(self.tab_names[target])
        if target in {"single","batch"}:self.active_media_mode=target

    def _on_media_mode_changed(self):
        key=next((key for key,name in self.tab_names.items() if name==self.tabs.get()),None)
        if key not in self._secondary_navigation_keys() or key==self.active_media_mode:return
        if key=="batch" and self.active_content_type in {"image","video"}:self.reset_format_context(self.active_content_type)
        self.active_media_mode=key

    def _document_context_ui(self, tab) -> SimpleNamespace:
        """Build one direct PDF or PowerPoint presentation context.

        The returned widgets are deliberately independent for each format;
        only their construction is shared.
        """
        tab.grid_columnconfigure(0,weight=1); tab.grid_rowconfigure(0,weight=1)
        panel=ctk.CTkFrame(tab); panel.grid(row=0,column=0,padx=20,pady=(4,8),sticky="nsew"); panel.grid_columnconfigure((0,1),weight=1); panel.grid_rowconfigure(2,weight=1)
        self.document_format_label=ctk.CTkLabel(panel,text="",font=ctk.CTkFont(size=24,weight="bold")); self.document_format_label.grid(row=0,column=0,padx=20,pady=(4,2),sticky="w")
        self.pptx_controls=ctk.CTkFrame(panel,fg_color="transparent"); self.pptx_controls.grid(row=1,column=0,columnspan=2,rowspan=2,padx=12,pady=(0,8),sticky="nsew"); self.pptx_controls.grid_columnconfigure((0,1),weight=1)
        left=ctk.CTkFrame(self.pptx_controls); left.grid(row=0,column=0,padx=(0,6),sticky="nsew"); left.grid_columnconfigure(0,weight=1)
        right=ctk.CTkFrame(self.pptx_controls); right.grid(row=0,column=1,padx=(6,0),sticky="nsew"); right.grid_columnconfigure(0,weight=1)
        self.pptx_choose_button=ctk.CTkButton(left,text="",command=self.choose_active_document,height=28); self.pptx_choose_button.grid(row=0,column=0,padx=12,pady=(8,2),sticky="ew")
        self.pptx_file_label=ctk.CTkLabel(left,textvariable=self.pptx_file_var,anchor="w",wraplength=390); self.pptx_file_label.grid(row=1,column=0,padx=12,pady=(0,3),sticky="ew")
        self.pptx_badge_label=ctk.CTkLabel(left,text="",font=ctk.CTkFont(weight="bold")); self.pptx_badge_label.grid(row=2,column=0,padx=12,pady=(2,0),sticky="w")
        self.pdf_badge_enable=ctk.CTkCheckBox(left,text="",variable=self.pdf_badge_enabled_var,command=self.pdf_overlay_changed); self.pdf_badge_enable.grid(row=2,column=0,padx=12,pady=(2,0),sticky="w"); self.pdf_badge_enable.grid_remove()
        self.pptx_badge_menu=ctk.CTkOptionMenu(left,variable=self.badge_display_var,values=["—"],command=self.select_badge_display,height=28); self.pptx_badge_menu.grid(row=3,column=0,padx=12,pady=1,sticky="ew")
        self.pptx_position_label=ctk.CTkLabel(left,text=""); self.pptx_position_label.grid(row=4,column=0,padx=12,pady=(3,0),sticky="w")
        self.pptx_position_menu=ctk.CTkOptionMenu(left,variable=self.position_display_var,values=["—"],command=self.change_position_display,height=28); self.pptx_position_menu.grid(row=5,column=0,padx=12,pady=1,sticky="ew")
        self.pptx_size_label=ctk.CTkLabel(left,text=""); self.pptx_size_label.grid(row=6,column=0,padx=12,pady=(2,0),sticky="w")
        self.pptx_size_slider=ctk.CTkSlider(left,from_=1,to=100,number_of_steps=99,variable=self.size_var,command=self.changed); self.pptx_size_slider.grid(row=7,column=0,padx=14,sticky="ew")
        self.pptx_opacity_label=ctk.CTkLabel(left,text=""); self.pptx_opacity_label.grid(row=8,column=0,padx=14,pady=(4,0),sticky="w")
        self.pptx_opacity_slider=ctk.CTkSlider(left,from_=0,to=100,number_of_steps=100,variable=self.opacity_var,command=self.changed); self.pptx_opacity_slider.grid(row=9,column=0,padx=14,sticky="ew")
        self.pptx_margin_label=ctk.CTkLabel(left,text=""); self.pptx_margin_label.grid(row=10,column=0,padx=14,pady=(4,0),sticky="w")
        self.pptx_margin_slider=ctk.CTkSlider(left,from_=0,to=250,number_of_steps=250,variable=self.margin_var,command=self.changed); self.pptx_margin_slider.grid(row=11,column=0,padx=14,sticky="ew")
        self.pptx_logo_enable=ctk.CTkCheckBox(left,text="",variable=self.logo_enabled_var,command=self.logo_changed); self.pptx_logo_enable.grid(row=12,column=0,padx=12,pady=(3,1),sticky="w")
        self.pptx_logo_choose=ctk.CTkButton(left,text="",command=self.choose_logo,height=26); self.pptx_logo_choose.grid(row=13,column=0,padx=12,pady=1,sticky="ew")
        ctk.CTkLabel(left,textvariable=self.logo_filename_var,text_color="gray60",anchor="w").grid(row=14,column=0,padx=12,pady=(0,2),sticky="ew")
        self.pptx_logo_settings=ctk.CTkFrame(left,fg_color="transparent"); self.pptx_logo_settings.grid(row=15,column=0,padx=12,pady=(0,6),sticky="ew"); self.pptx_logo_settings.grid_columnconfigure((0,1),weight=1)
        self.pptx_logo_position_menu=ctk.CTkOptionMenu(self.pptx_logo_settings,variable=self.logo_position_display_var,values=["—"],command=self.change_logo_position,height=26); self.pptx_logo_position_menu.grid(row=0,column=0,columnspan=2,sticky="ew")
        self.pptx_logo_size_label=ctk.CTkLabel(self.pptx_logo_settings,text="",height=20); self.pptx_logo_size_label.grid(row=1,column=0,columnspan=2,sticky="w")
        ctk.CTkSlider(self.pptx_logo_settings,from_=1,to=100,number_of_steps=99,variable=self.logo_size_var,command=self.changed,height=12).grid(row=2,column=0,columnspan=2,sticky="ew")
        self.pptx_logo_margin_label=ctk.CTkLabel(self.pptx_logo_settings,text="",height=20); self.pptx_logo_margin_label.grid(row=3,column=0,padx=(0,4),sticky="w")
        self.pptx_logo_opacity_label=ctk.CTkLabel(self.pptx_logo_settings,text="",height=20); self.pptx_logo_opacity_label.grid(row=3,column=1,padx=(4,0),sticky="w")
        self.pptx_logo_margin_slider=ctk.CTkSlider(self.pptx_logo_settings,from_=0,to=250,number_of_steps=250,variable=self.logo_margin_var,command=self.changed,height=12); self.pptx_logo_margin_slider.grid(row=4,column=0,padx=(0,4),sticky="ew")
        ctk.CTkSlider(self.pptx_logo_settings,from_=0,to=100,number_of_steps=100,variable=self.logo_opacity_var,command=self.changed,height=12).grid(row=4,column=1,padx=(4,0),sticky="ew")

        self.pptx_scope_label=ctk.CTkLabel(panel,text="",font=ctk.CTkFont(weight="bold")); self.pptx_scope_label.grid(row=0,column=1,padx=26,pady=(4,2),sticky="w")
        self.pptx_selection_menu=ctk.CTkOptionMenu(right,variable=self.pptx_selection_display_var,values=["—"],command=self.change_pptx_selection_mode); self.pptx_selection_menu.grid(row=1,column=0,padx=14,pady=2,sticky="ew")
        self.pptx_selected_frame=ctk.CTkFrame(right,fg_color="transparent"); self.pptx_selected_frame.grid_columnconfigure(0,weight=1)
        self.pptx_selected_label=ctk.CTkLabel(self.pptx_selected_frame,text="",anchor="w"); self.pptx_selected_label.grid(row=0,column=0,sticky="w"); self.pptx_selected_entry=ctk.CTkEntry(self.pptx_selected_frame,textvariable=self.pptx_selected_var); self.pptx_selected_entry.grid(row=1,column=0,sticky="ew")
        self.pptx_selected_update_button=ctk.CTkButton(self.pptx_selected_frame,text="",command=self.commit_document_selection,height=26); self.pptx_selected_update_button.grid(row=2,column=0,pady=(4,0),sticky="e")
        self.pptx_range_frame=ctk.CTkFrame(right,fg_color="transparent"); self.pptx_range_frame.grid_columnconfigure(0,weight=1)
        self.pptx_range_label=ctk.CTkLabel(self.pptx_range_frame,text="",anchor="w"); self.pptx_range_label.grid(row=0,column=0,sticky="w"); self.pptx_range_entry=ctk.CTkEntry(self.pptx_range_frame,textvariable=self.pptx_range_var); self.pptx_range_entry.grid(row=1,column=0,sticky="ew")
        self.pptx_range_update_button=ctk.CTkButton(self.pptx_range_frame,text="",command=self.commit_document_selection,height=26); self.pptx_range_update_button.grid(row=2,column=0,pady=(4,0),sticky="e")
        self.pptx_scope_validation_label=ctk.CTkLabel(right,text="",text_color=("#b42318","#ff8178"),anchor="w",wraplength=390); self.pptx_scope_validation_label.grid(row=4,column=0,padx=14,pady=(0,2),sticky="ew")
        self.pptx_language_label=ctk.CTkLabel(right,text=""); self.pptx_language_label.grid(row=5,column=0,padx=14,pady=(4,0),sticky="w")
        self.pptx_language_menu=ctk.CTkOptionMenu(right,variable=self.pptx_language_var,values=list(LANGUAGES)); self.pptx_language_menu.grid(row=6,column=0,padx=14,pady=2,sticky="ew")
        self.pptx_preview_label=ctk.CTkLabel(right,text="",height=220,fg_color=("gray92","gray13"),corner_radius=6); self.pptx_preview_label.grid(row=7,column=0,padx=14,pady=(5,2),sticky="nsew")
        self.pptx_preview_navigation=ctk.CTkFrame(right,fg_color="transparent"); self.pptx_preview_navigation.grid(row=8,column=0,padx=14,pady=1)
        self.pptx_previous_button=ctk.CTkButton(self.pptx_preview_navigation,text="◀",width=42,height=25,command=lambda:self.change_document_preview_page(-1)); self.pptx_previous_button.grid(row=0,column=0,padx=3)
        self.pptx_slide_status=ctk.CTkLabel(self.pptx_preview_navigation,text="—",width=120); self.pptx_slide_status.grid(row=0,column=1,padx=3)
        self.pptx_next_button=ctk.CTkButton(self.pptx_preview_navigation,text="▶",width=42,height=25,command=lambda:self.change_document_preview_page(1)); self.pptx_next_button.grid(row=0,column=2,padx=3)
        self.pptx_metadata_note=ctk.CTkLabel(right,text="",text_color="gray60",wraplength=390,justify="left"); self.pptx_metadata_note.grid(row=9,column=0,padx=14,pady=(2,1),sticky="w")
        self.pptx_process_button=ctk.CTkButton(right,text="",command=self.process_active_document,height=28); self.pptx_process_button.grid(row=10,column=0,padx=14,pady=(3,8),sticky="ew")
        return SimpleNamespace(**{name:getattr(self,name) for name in self._document_widget_names})

    _document_widget_names=(
        "document_format_label","pptx_controls","pptx_choose_button","pptx_file_label",
        "pptx_badge_label","pdf_badge_enable","pptx_badge_menu","pptx_position_label",
        "pptx_position_menu","pptx_size_label","pptx_size_slider","pptx_opacity_label",
        "pptx_opacity_slider","pptx_margin_label","pptx_margin_slider","pptx_logo_enable",
        "pptx_logo_choose","pptx_logo_settings","pptx_logo_position_menu","pptx_logo_size_label",
        "pptx_logo_margin_label","pptx_logo_opacity_label","pptx_logo_margin_slider",
        "pptx_scope_label","pptx_selection_menu","pptx_selected_frame","pptx_selected_label",
        "pptx_selected_entry","pptx_selected_update_button","pptx_range_frame","pptx_range_label",
        "pptx_range_entry","pptx_range_update_button","pptx_scope_validation_label",
        "pptx_language_label","pptx_language_menu","pptx_preview_label","pptx_preview_navigation",
        "pptx_previous_button","pptx_slide_status","pptx_next_button","pptx_metadata_note",
        "pptx_process_button",
    )

    def _bind_document_context_widgets(self, format_type: str) -> None:
        """Bind generic document actions to the visible, direct context."""
        context=self.pdf_context_widgets if format_type=="pdf" else self.pptx_context_widgets
        if context is None:
            return
        for name,value in vars(context).items():
            setattr(self,name,value)

    def _load_welcome_image(self,diagnostic):
        path=welcome_image_path()
        try:
            with Image.open(path) as opened:self.welcome_image=opened.convert("RGBA")
        except OSError as error:
            diagnostic(f"Welcome illustration unavailable at {path}: {error}")
            self.welcome_illustration.configure(text="◇")

    def _resize_welcome(self,event=None):
        if self.welcome_image is None:return
        width=max(240,(event.width if event else self.welcome_frame.winfo_width())-48); height=max(135,(event.height if event else self.welcome_frame.winfo_height())-210)
        ratio=min(width/self.welcome_image.width,height/self.welcome_image.height); size=(max(1,int(self.welcome_image.width*ratio)),max(1,int(self.welcome_image.height*ratio)))
        self.welcome_photo=ctk.CTkImage(light_image=self.welcome_image,dark_image=self.welcome_image,size=size); self.welcome_illustration.configure(image=self.welcome_photo,text="")

    def _show_welcome(self):
        self.preview_label.grid_remove(); self.welcome_frame.grid(row=0,column=0,padx=18,pady=14,sticky="nsew"); self._resize_welcome()

    def _show_preview(self):
        self.welcome_frame.grid_remove(); self.preview_label.grid(row=0,column=0,padx=12,pady=12,sticky="nsew")

    def render_start_view(self):
        """Restore the visible startup view after the tab switch has settled."""
        self.show_tab("single"); self.update_idletasks()
        self.preview_photo=None; self.preview_image=None; self.preview_label.configure(image=None,text=""); self.preview_label.grid_remove()
        self.welcome_title.configure(text=self.translator.text("welcome.title")); self.welcome_tagline.configure(text=self.translator.text("welcome.tagline"))
        self.welcome_description1.configure(text=self.translator.text("welcome.description1")); self.welcome_description2.configure(text=self.translator.text("welcome.description2"))
        self._show_welcome(); self.welcome_frame.lift()

    def _finish_reset_view(self):
        self._reset_after_id=None
        try:self.render_start_view()
        except TclError:pass
        self.status_var.set(self.translator.text("status.reset"))

    def _slider(self,parent,var,start,end,row):
        label=ctk.CTkLabel(parent,text=""); label.grid(row=row,column=0,padx=14,pady=(4,0),sticky="w")
        ctk.CTkSlider(parent,from_=start,to=end,number_of_steps=end-start,variable=var,command=self.changed).grid(row=row+1,column=0,padx=14,pady=(1,3),sticky="ew")
        return label

    def _settings_ui(self) -> None:
        tab=self.settings_tab; tab.grid_columnconfigure(0,weight=1); tab.grid_rowconfigure(3,weight=1)
        source=ctk.CTkFrame(tab); self.badge_source_frame=source; source.grid(row=0,column=0,padx=16,pady=(6,3),sticky="ew"); source.grid_columnconfigure(0,weight=1)
        self.badges_back_button=ctk.CTkButton(tab,text="",command=self.navigate_home,width=110); self.badges_back_button.grid(row=0,column=1,padx=(0,16),pady=(6,3),sticky="ne")
        self.badge_source_heading=ctk.CTkLabel(source,text="",font=ctk.CTkFont(weight="bold")); self.badge_source_heading.grid(row=0,column=0,padx=12,pady=(5,2),sticky="w")
        self.standard_badge_radio=ctk.CTkRadioButton(source,text="",variable=self.badge_source_var,value="standard",command=self.change_badge_source); self.standard_badge_radio.grid(row=1,column=0,padx=16,pady=2,sticky="w")
        self.custom_badge_radio=ctk.CTkRadioButton(source,text="",variable=self.badge_source_var,value="custom",command=self.change_badge_source); self.custom_badge_radio.grid(row=2,column=0,padx=16,pady=2,sticky="w")
        self.custom_controls=ctk.CTkFrame(source,fg_color="transparent"); self.custom_controls.grid(row=3,column=0,padx=16,pady=(2,5),sticky="ew"); self.custom_controls.grid_columnconfigure(0,weight=1)
        self.custom_folder_label=ctk.CTkLabel(self.custom_controls,text=""); self.custom_folder_label.grid(row=0,column=0,columnspan=2,sticky="w")
        self.custom_entry=ctk.CTkEntry(self.custom_controls,textvariable=self.custom_badge_var); self.custom_entry.grid(row=1,column=0,padx=(0,8),pady=4,sticky="ew")
        self.choose_badge_folder_button=ctk.CTkButton(self.custom_controls,text="",command=self.browse_custom_badges); self.choose_badge_folder_button.grid(row=1,column=1,padx=4,pady=4)
        self.refresh_button=ctk.CTkButton(self.custom_controls,text="",command=self.refresh_badges); self.refresh_button.grid(row=1,column=2,padx=(4,0),pady=4)
        self.update_controls=ctk.CTkFrame(source,fg_color="transparent"); self.update_controls.grid(row=4,column=0,padx=16,pady=(1,5),sticky="ew"); self.update_controls.grid_columnconfigure(0,weight=1)
        self.automatic_update_checkbox=ctk.CTkCheckBox(self.update_controls,text="",variable=self.automatic_update_var,command=self._automatic_update_preference_changed); self.automatic_update_checkbox.grid(row=0,column=0,pady=4,sticky="w")
        self.update_privacy_label=ctk.CTkLabel(self.update_controls,text="",text_color="gray60",justify="left",anchor="w",wraplength=850); self.update_privacy_label.grid(row=1,column=0,columnspan=2,pady=(2,0),sticky="ew")
        self.desktop_shortcut_button=ctk.CTkButton(self.update_controls,text="",command=self.create_shortcut,width=180,height=28); self.desktop_shortcut_button.grid(row=2,column=0,pady=(8,0),sticky="w")
        self.badge_help=ctk.CTkLabel(tab,text="",justify="left",anchor="w",wraplength=1050); self.badge_help.grid(row=1,column=0,columnspan=2,padx=20,pady=1,sticky="ew")
        self.badge_gallery_title=ctk.CTkLabel(tab,text="",font=ctk.CTkFont(size=18,weight="bold")); self.badge_gallery_title.grid(row=2,column=0,columnspan=2,padx=16,pady=(4,1),sticky="w")
        self.gallery=ctk.CTkScrollableFrame(tab); self.gallery.grid(row=3,column=0,columnspan=2,padx=16,pady=(2,8),sticky="nsew")
        for column in range(5): self.gallery.grid_columnconfigure(column,weight=1)

    def _batch_ui(self) -> None:
        tab=self.batch_tab; tab.grid_columnconfigure(0,weight=1); tab.grid_rowconfigure(1,weight=1)
        self.batch_title=ctk.CTkLabel(tab,text="",font=ctk.CTkFont(size=20,weight="bold")); self.batch_title.grid(row=0,column=0,padx=16,pady=(12,4),sticky="w")
        self.batch_back_button=ctk.CTkButton(tab,text="",command=self.navigate_home,width=110); self.batch_back_button.grid(row=0,column=1,padx=16,pady=(12,4),sticky="e")
        page=AutoHideScrollableFrame(tab,fg_color="transparent"); self.batch_page=page; page.grid(row=1,column=0,columnspan=2,padx=8,pady=(2,10),sticky="nsew"); page.grid_columnconfigure(0,weight=1)
        input_section=ctk.CTkFrame(page); input_section.grid(row=0,column=0,padx=8,pady=5,sticky="ew"); input_section.grid_columnconfigure(0,weight=1)
        self.input_label=ctk.CTkLabel(input_section,text="",font=ctk.CTkFont(weight="bold")); self.input_label.grid(row=0,column=0,padx=12,pady=(8,2),sticky="w")
        self.batch_size_guidance=ctk.CTkLabel(input_section,text="",justify="left",text_color="gray60"); self.batch_size_guidance.grid(row=0,column=1,padx=12,pady=(8,2),sticky="e")
        ctk.CTkEntry(input_section,textvariable=self.input_folder_var).grid(row=1,column=0,padx=12,pady=(2,8),sticky="ew")
        self.choose_input_button=ctk.CTkButton(input_section,text="",command=self.choose_input_folder); self.choose_input_button.grid(row=1,column=1,padx=12,pady=(2,8))
        output=ctk.CTkFrame(page); output.grid(row=1,column=0,padx=8,pady=5,sticky="ew"); output.grid_columnconfigure(0,weight=1)
        self.batch_output_heading=ctk.CTkLabel(output,text="",font=ctk.CTkFont(weight="bold")); self.batch_output_heading.grid(row=0,column=0,padx=12,pady=(8,2),sticky="w")
        self.output_subfolder_radio=ctk.CTkRadioButton(output,text="",variable=self.output_preference_var,value="subfolder",command=self.changed); self.output_subfolder_radio.grid(row=1,column=0,padx=12,pady=3,sticky="w")
        ctk.CTkEntry(output,textvariable=self.output_subfolder_var).grid(row=2,column=0,padx=32,pady=3,sticky="ew")
        self.output_separate_radio=ctk.CTkRadioButton(output,text="",variable=self.output_preference_var,value="separate",command=self.changed); self.output_separate_radio.grid(row=3,column=0,padx=12,pady=3,sticky="w")
        ctk.CTkEntry(output,textvariable=self.output_folder_var).grid(row=4,column=0,padx=(32,8),pady=3,sticky="ew")
        self.choose_output_button=ctk.CTkButton(output,text="",command=self.choose_output_folder); self.choose_output_button.grid(row=4,column=1,padx=(4,12),pady=3)
        self.batch_suffix_label=ctk.CTkLabel(output,text=""); self.batch_suffix_label.grid(row=5,column=0,padx=12,pady=(4,1),sticky="w")
        self.batch_suffix_entry=ctk.CTkEntry(output,textvariable=self.batch_suffix_var); self.batch_suffix_entry.grid(row=6,column=0,padx=32,pady=(1,8),sticky="ew"); self.batch_suffix_entry.bind("<FocusOut>",self.changed)
        badge_section=ctk.CTkFrame(page); badge_section.grid(row=2,column=0,padx=8,pady=5,sticky="ew"); badge_section.grid_columnconfigure(1,weight=1)
        self.batch_badge_heading=ctk.CTkLabel(badge_section,text="",font=ctk.CTkFont(weight="bold")); self.batch_badge_heading.grid(row=0,column=0,padx=12,pady=8,sticky="w")
        self.batch_badge_value=ctk.CTkLabel(badge_section,textvariable=self.badge_name_var,anchor="w"); self.batch_badge_value.grid(row=0,column=1,padx=12,pady=8,sticky="ew")
        self.batch_logo_label=ctk.CTkLabel(badge_section,text="",font=ctk.CTkFont(weight="bold")); self.batch_logo_label.grid(row=1,column=0,padx=12,pady=(0,8),sticky="w")
        self.batch_logo_value=ctk.CTkLabel(badge_section,text="",anchor="w"); self.batch_logo_value.grid(row=1,column=1,padx=12,pady=(0,8),sticky="ew")
        options=ctk.CTkFrame(page); options.grid(row=3,column=0,padx=8,pady=5,sticky="ew"); self.batch_options_heading=ctk.CTkLabel(options,text="",font=ctk.CTkFont(weight="bold")); self.batch_options_heading.grid(row=0,column=0,columnspan=3,padx=12,pady=(8,2),sticky="w"); self.batch_checks=[]
        for i,(key,var) in enumerate((("batch.recursive",self.recursive_var),("batch.preserve",self.preserve_var),("batch.images",self.images_var),("batch.videos",self.videos_var),("batch.skip",self.skip_var))):
            check=ctk.CTkCheckBox(options,text="",variable=var,command=self.changed); check.grid(row=1+i//3,column=i%3,padx=12,pady=(4,8),sticky="w"); self.batch_checks.append((key,check))
        self.batch_video_controls=ctk.CTkFrame(page); self.batch_video_controls.grid(row=4,column=0,padx=8,pady=5,sticky="ew")
        self.batch_video_settings_heading=ctk.CTkLabel(self.batch_video_controls,text="",font=ctk.CTkFont(weight="bold")); self.batch_video_settings_heading.grid(row=0,column=0,columnspan=4,padx=12,pady=(8,2),sticky="w")
        self.batch_video_mode_label=ctk.CTkLabel(self.batch_video_controls,text=""); self.batch_video_mode_label.grid(row=1,column=0,padx=12,pady=(2,8))
        self.batch_video_mode_menu=ctk.CTkOptionMenu(self.batch_video_controls,variable=self.video_mode_display_var,values=["—"],command=self.change_video_mode); self.batch_video_mode_menu.grid(row=0,column=1,padx=8)
        self.batch_video_mode_menu.grid_configure(row=1,pady=(2,8))
        self.batch_video_duration_label=ctk.CTkLabel(self.batch_video_controls,text=""); self.batch_video_duration_label.grid(row=1,column=2,padx=(18,4),pady=(2,8))
        self.batch_video_duration_entry=ctk.CTkEntry(self.batch_video_controls,textvariable=self.video_duration_var,width=70); self.batch_video_duration_entry.grid(row=1,column=3,padx=(4,12),pady=(2,8)); self.batch_video_duration_entry.bind("<FocusOut>",self.changed)
        buttons=ctk.CTkFrame(page,fg_color="transparent"); buttons.grid(row=5,column=0,padx=8,pady=6,sticky="w")
        self.scan_button=ctk.CTkButton(buttons,text="",command=self.scan_input_folder); self.scan_button.grid(row=0,column=0,padx=(0,8))
        self.start_batch_button=ctk.CTkButton(buttons,text="",command=self.start_batch); self.start_batch_button.grid(row=0,column=1,padx=8)
        self.cancel_batch_button=ctk.CTkButton(buttons,text="",command=self.cancel_batch,state="disabled"); self.cancel_batch_button.grid(row=0,column=2,padx=8)
        progress_section=ctk.CTkFrame(page); progress_section.grid(row=6,column=0,padx=8,pady=5,sticky="ew"); progress_section.grid_columnconfigure(0,weight=1)
        self.batch_progress_heading=ctk.CTkLabel(progress_section,text="",font=ctk.CTkFont(weight="bold")); self.batch_progress_heading.grid(row=0,column=0,padx=12,pady=(8,2),sticky="w")
        ctk.CTkLabel(progress_section,textvariable=self.scan_summary_var,justify="left",anchor="w",wraplength=1050).grid(row=1,column=0,padx=12,pady=3,sticky="ew")
        self.progress=ctk.CTkProgressBar(progress_section); self.progress.set(0); self.progress.grid(row=2,column=0,padx=12,pady=6,sticky="ew")
        ctk.CTkLabel(progress_section,textvariable=self.progress_text_var,justify="left",anchor="w",wraplength=1050).grid(row=3,column=0,padx=12,pady=(3,8),sticky="ew")

    def _inspect_ui(self) -> None:
        tab=self.inspect_tab; tab.grid_columnconfigure(0,weight=1); tab.grid_rowconfigure(1,weight=1)
        self.inspect_title=ctk.CTkLabel(tab,text="",font=ctk.CTkFont(size=20,weight="bold")); self.inspect_title.grid(row=0,column=0,padx=20,pady=(14,4),sticky="w")
        self.inspect_back_button=ctk.CTkButton(tab,text="",command=self.navigate_home,width=110); self.inspect_back_button.grid(row=0,column=1,padx=20,pady=(14,4),sticky="e")
        page=AutoHideScrollableFrame(tab,fg_color="transparent"); self.inspect_page=page; page.grid(row=1,column=0,columnspan=2,padx=12,pady=(2,14),sticky="nsew"); page.grid_columnconfigure(0,weight=1)
        self.inspect_intro=ctk.CTkLabel(page,text="",anchor="w",justify="left",wraplength=950); self.inspect_intro.grid(row=0,column=0,padx=16,pady=(10,8),sticky="ew")
        self.inspect_choose_button=ctk.CTkButton(page,text="",command=self.choose_inspection_file); self.inspect_choose_button.grid(row=1,column=0,padx=16,pady=8,sticky="w")
        file_section=ctk.CTkFrame(page); file_section.grid(row=2,column=0,padx=16,pady=8,sticky="ew"); file_section.grid_columnconfigure(1,weight=1)
        self.inspect_selected_heading=ctk.CTkLabel(file_section,text="",font=ctk.CTkFont(weight="bold")); self.inspect_selected_heading.grid(row=0,column=0,columnspan=2,padx=12,pady=(10,5),sticky="w")
        self.inspect_file_label=ctk.CTkLabel(file_section,text=""); self.inspect_file_label.grid(row=1,column=0,padx=12,pady=3,sticky="w")
        ctk.CTkLabel(file_section,textvariable=self.inspect_file_var,anchor="w").grid(row=1,column=1,padx=12,pady=3,sticky="ew")
        self.inspect_format_label=ctk.CTkLabel(file_section,text=""); self.inspect_format_label.grid(row=2,column=0,padx=12,pady=(3,10),sticky="w")
        ctk.CTkLabel(file_section,textvariable=self.inspect_format_var,anchor="w").grid(row=2,column=1,padx=12,pady=(3,10),sticky="ew")
        result_section=ctk.CTkFrame(page); result_section.grid(row=3,column=0,padx=16,pady=8,sticky="ew"); result_section.grid_columnconfigure(1,weight=1)
        self.inspect_metadata_heading=ctk.CTkLabel(result_section,text="",font=ctk.CTkFont(size=18,weight="bold")); self.inspect_metadata_heading.grid(row=0,column=0,columnspan=2,padx=12,pady=(10,6),sticky="w")
        self.inspect_status_label=ctk.CTkLabel(result_section,text="",font=ctk.CTkFont(weight="bold")); self.inspect_status_label.grid(row=1,column=0,padx=12,pady=4,sticky="w")
        ctk.CTkLabel(result_section,textvariable=self.inspect_status_var,anchor="w").grid(row=1,column=1,padx=12,pady=4,sticky="ew")
        self.inspect_software_label=ctk.CTkLabel(result_section,text=""); self.inspect_software_label.grid(row=2,column=0,padx=12,pady=4,sticky="w")
        ctk.CTkLabel(result_section,textvariable=self.inspect_software_var,anchor="w").grid(row=2,column=1,padx=12,pady=4,sticky="ew")
        self.inspect_ai_label=ctk.CTkLabel(result_section,text=""); self.inspect_ai_label.grid(row=3,column=0,padx=12,pady=4,sticky="w")
        ctk.CTkLabel(result_section,textvariable=self.inspect_label_var,anchor="w").grid(row=3,column=1,padx=12,pady=4,sticky="ew")
        self.inspect_marker_version_label=ctk.CTkLabel(result_section,text=""); self.inspect_marker_version_label.grid(row=4,column=0,padx=12,pady=4,sticky="w")
        ctk.CTkLabel(result_section,textvariable=self.inspect_version_var,anchor="w").grid(row=4,column=1,padx=12,pady=4,sticky="ew")
        self.inspect_result_message=ctk.CTkLabel(result_section,textvariable=self.inspect_message_var,anchor="w",justify="left",wraplength=900,text_color="gray65"); self.inspect_result_message.grid(row=5,column=0,columnspan=2,padx=12,pady=(8,12),sticky="ew")
        self._render_inspection()

    def apply_translations(self) -> None:
        t=self.translator.text; self.title(f"Nenolink AI Marker {__version__}"); self.guide_button.configure(text=t("button.user_guide")); self.reset_button.configure(text=t("button.reset")); self.batch_back_button.configure(text=t("button.back")); self.badges_back_button.configure(text=t("button.back")); self.inspect_back_button.configure(text=t("button.back")); self.automatic_update_checkbox.configure(text=t("update.automatic")); self.footer_update_link.configure(text=t("update.check")); self.update_privacy_label.configure(text=t("update.privacy")); self.desktop_shortcut_button.configure(text=t("shortcut.create")); self._render_update_notification()
        content_pairs=(("image","content.images"),("video","content.video"),("pdf","content.pdf"),("pptx","content.powerpoint"))
        self.content_display_to_kind={t(key):kind for kind,key in content_pairs}
        self._build_content_navigation()
        self.media_group_label.configure(text=t("content.media_group")); self.documents_group_label.configure(text=t("content.documents_group")); self.tools_group_label.configure(text=t("content.tools_group")); self.tools_navigation.configure(values=[t("tab.badges"),t("tab.inspect")])
        for key,translation_key in (("single","tab.single"),("batch","tab.batch"),("badges","tab.badges"),("inspect","tab.inspect")):
            new=t(translation_key); old=self.tab_names[key]
            if old != new:self.tabs.rename(old,new); self.tab_names[key]=new
        self.open_button.configure(text="1. "+t("button.open_media")); self.process_button.configure(text=t("button.process_video") if self.active_content_type=="video" else t("button.process")); self.file_label.configure(text=t("files.none") if not self.sources else t("files.selected",count=len(self.sources),name=self.sources[0].name))
        self.file_size_guidance.configure(text=t("files.size_guidance")); self.batch_size_guidance.configure(text=t("files.size_guidance_short"))
        self.video_mode_display_to_value={t("video.mode.permanent"):"permanent",t("video.mode.beginning"):"beginning",t("video.mode.end"):"end"}
        video_values=list(self.video_mode_display_to_value); self.video_mode_menu.configure(values=video_values); self.batch_video_mode_menu.configure(values=video_values)
        self.video_mode_display_var.set(next((label for label,value in self.video_mode_display_to_value.items() if value==self.video_mode_var.get()),t("video.mode.permanent")))
        self.video_settings_heading.configure(text=t("video.settings")); self.batch_video_settings_heading.configure(text=t("video.settings")); self.video_mode_label.configure(text=t("video.badge")); self.batch_video_mode_label.configure(text=t("video.badge")); self._update_video_duration_controls()
        self.position_label.configure(text="3. "+t("position")); self.size_label.configure(text="4. "+t("size.value",value=self.size_var.get())); self.margin_label.configure(text="5. "+t("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text="6. "+t("opacity.value",value=self.opacity_var.get()))
        self.badge_source_heading.configure(text=t("badge.source_label")); self.standard_badge_radio.configure(text=t("badge.source_standard")); self.custom_badge_radio.configure(text=t("badge.source_custom")); self.custom_folder_label.configure(text=t("badge.custom_path")+":"); self.custom_entry.configure(placeholder_text=t("badge.custom_path"))
        self.position_display_to_value={t("position.top_left"):"top-left",t("position.top_right"):"top-right",t("position.bottom_left"):"bottom-left",t("position.bottom_right"):"bottom-right",t("position.center"):"center"}; self.position_menu.configure(values=list(self.position_display_to_value)); self.position_display_var.set(next((label for label,value in self.position_display_to_value.items() if value==self.position_var.get()),t("position.bottom_right")))
        self.logo_position_display_to_value=dict(self.position_display_to_value); self.logo_position_menu.configure(values=list(self.logo_position_display_to_value)); self.logo_position_display_var.set(next((label for label,value in self.logo_position_display_to_value.items() if value==self.logo_position_var.get()),t("position.top_left")))
        self.logo_heading.configure(text=t("logo.title")); self.logo_enable.configure(text=t("logo.enable")); self.logo_choose.configure(text=t("logo.choose")); self.logo_position_label.configure(text=t("logo.position")); self.logo_images_only.configure(text=t("logo.images_only")); self._update_logo_labels(); self._update_logo_controls()
        self.choose_badge_folder_button.configure(text=t("button.choose_badge_folder")); self.refresh_button.configure(text=t("badge.refresh")); self.badge_gallery_title.configure(text=t("badge.gallery")); self.badge_help.configure(text=t("badge.help")); self._show_badge_source_controls()
        self.batch_title.configure(text=t("tab.batch")); self.input_label.configure(text=t("batch.input")); self.batch_output_heading.configure(text=t("batch.output")); self.batch_badge_heading.configure(text=t("badge")); self.batch_options_heading.configure(text=t("batch.options")); self.batch_progress_heading.configure(text=t("batch.progress_heading")); self.choose_input_button.configure(text=t("button.choose_input")); self.choose_output_button.configure(text=t("button.choose_output")); self.output_subfolder_radio.configure(text=t("batch.output_subfolder")); self.output_separate_radio.configure(text=t("batch.output_separate")); self.batch_suffix_label.configure(text=t("batch.filename_suffix"))
        self.batch_logo_label.configure(text=t("logo.title")); self._update_batch_logo_value()
        self.welcome_title.configure(text=t("welcome.title")); self.welcome_tagline.configure(text=t("welcome.tagline")); self.welcome_description1.configure(text=t("welcome.description1")); self.welcome_description2.configure(text=t("welcome.description2"))
        for key,check in self.batch_checks: check.configure(text=t(key))
        self.scan_button.configure(text=t("button.scan_folder")); self.start_batch_button.configure(text=t("button.start_batch")); self.cancel_batch_button.configure(text=t("button.cancel_batch"))
        self.inspect_title.configure(text=t("inspect.title")); self.inspect_intro.configure(text=t("inspect.intro")); self.inspect_choose_button.configure(text=t("inspect.choose")); self.inspect_selected_heading.configure(text=t("inspect.selected")); self.inspect_file_label.configure(text=t("inspect.file")); self.inspect_format_label.configure(text=t("inspect.format_size")); self.inspect_metadata_heading.configure(text=t("inspect.metadata")); self.inspect_status_label.configure(text=t("inspect.status")); self.inspect_software_label.configure(text=t("inspect.software")); self.inspect_ai_label.configure(text=t("inspect.ai_label")); self.inspect_marker_version_label.configure(text=t("inspect.marker_version")); self._render_inspection()
        self._synchronize_document_widgets()

    def change_language(self,name):
        self.translator.set_language(LANGUAGES.get(name,"en")); self.apply_translations()
        workspace = getattr(self, "pptx_workspace_state", None)
        if self.shell_controller.active_content_type == "pptx" and self.shell_controller.active_tool is None and workspace is not None:
            workspace.apply_language(self.translator)
        self._save()
    def _build_content_navigation(self):
        """Build passive buttons: only the controller is allowed to select one."""
        for frame, kinds in ((self.media_navigation, ("image", "video")), (self.document_navigation, ("pdf", "pptx"))):
            for child in frame.winfo_children(): child.destroy()
            for column, kind in enumerate(kinds):
                label=next(label for label, value in self.content_display_to_kind.items() if value==kind)
                button=ctk.CTkButton(frame, text=label, height=26, width=0,
                    command=lambda destination=kind: self.request_content_transition(destination))
                button.grid(row=0,column=column,padx=(0 if column==0 else 3,0),pady=0,sticky="w")
                self.content_buttons[kind]=button

    def change_content_workspace(self,label):
        """Compatibility entry point for tests/old callers; it owns no UI state."""
        target=self.content_display_to_kind.get(label, label if label in {"image","video","pdf","pptx"} else None)
        return self.request_content_transition(target) if target else False

    def request_content_transition(self,destination):
        """Execute content navigation exclusively through the Shell table."""
        if destination not in self._workspace_registry:
            raise ValueError(f"Unknown content destination: {destination}")
        source = self.shell_controller.active_content_type
        active = self._format_has_active_work(source)
        spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, active)
        self.last_shell_spec = spec
        if spec.requires_confirmation:
            if not self._confirm_format_switch(source, destination):
                spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, active, "cancel")
                self.last_shell_spec = spec
                self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
                return False
            spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, active, "continue")
            self.last_shell_spec = spec
        try:
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
        except RuntimeError:
            return False
        self.render_shell_state(remount=False)
        return True

    def _format_has_active_work(self,format_type):
        if format_type == "image": return self.image_workspace_owner.has_active_work()
        if format_type == "video": return self.video_workspace_owner.has_active_work()
        if format_type == "batch": return bool(self.scan)
        if format_type=="pdf":return self.pdf_path is not None
        if format_type=="pptx":return self.pptx_path is not None
        return False

    def _confirm_format_switch(self,source,target):
        result={"continue":False}; dialog=ctk.CTkToplevel(self); self._format_switch_dialog=dialog; dialog.title(self.translator.text("navigation.switch_title")); dialog.transient(self); dialog.resizable(False,False)
        ctk.CTkLabel(dialog,text=self.translator.text("navigation.switch_message"),wraplength=420,justify="left").grid(row=0,column=0,columnspan=2,padx=24,pady=(22,18))
        def close(value):result["continue"]=value; self._format_switch_dialog=None; dialog.destroy()
        ctk.CTkButton(dialog,text=self.translator.text("navigation.cancel"),command=lambda:close(False),fg_color="transparent",border_width=1).grid(row=1,column=0,padx=(24,6),pady=(0,22))
        ctk.CTkButton(dialog,text=self.translator.text("navigation.continue"),command=lambda:close(True)).grid(row=1,column=1,padx=(6,24),pady=(0,22))
        dialog.protocol("WM_DELETE_WINDOW",lambda:close(False)); self.wait_window(dialog); self._format_switch_dialog=None
        return result["continue"]

    def change_auxiliary_workspace(self,label):
        target="badges" if label in {"badges",self.translator.text("tab.badges")} else "inspect"
        if self.active_tool==target:return True
        # Tools are overlays, never content transitions: preserve the active
        # workspace and do not show a loss-of-work confirmation.
        self.active_tool=target
        if target=="inspect":self.inspection_path=None; self.inspection_result=None; self.inspection_error=""; self.inspection_unsupported=False
        self.render_shell_state(); return True

    def reset_format_context(self,format_type,preserve_visual_settings=True,*,keep_file=False,scope="all"):
        """Reset file/navigation state without touching shared badge/logo styling."""
        if format_type == "image":
            self.image_workspace_owner.clear_runtime_state()
            self.media_sources["image"] = []
            return
        if format_type == "video":
            self.video_workspace_owner.clear_runtime_state()
            self.media_sources["video"] = []
            return
        if format_type not in {"pdf","pptx","docx"}:return
        if not hasattr(self,"document_scope_states"):self.document_scope_states={"pdf":DocumentScopeState(),"pptx":DocumentScopeState()}
        if format_type in self.document_scope_states:self.document_scope_states[format_type].reset(scope)
        if self.active_content_type==format_type and hasattr(self,"pptx_selection_mode_var"):MarkerApp._sync_document_scope_controls(self,format_type)
        self.pptx_preview_photo=None
        if format_type=="pdf":
            self._pdf_warning_approved=None; self._pdf_signature_approved=None
            if hasattr(self,"processor"):self.pdf_preview_renderer=PdfPreviewRenderer(self.processor)
            if not keep_file:self.pdf_path=None; self.pdf_info=None; self.pdf_preview_state.clear()
            elif self.pdf_info:self.pdf_preview_state.initialize(self.pdf_info.metrics.item_count)
        elif format_type=="pptx":
            self._pptx_warning_approved=None
            renderer=getattr(self,"pptx_preview_renderer",None)
            if renderer is not None:renderer.clear()
            workspace=getattr(self,"pptx_workspace_state",None)
            if workspace is not None:
                workspace.clear_runtime_state()
            if not keep_file:self.pptx_path=None; self.pptx_metrics=None; self.pptx_preview_state.clear()
            elif self.pptx_metrics:self.pptx_preview_state.initialize(self.pptx_metrics.item_count)
        else:
            self._docx_warning_approved=None; self.docx_preview_renderer.clear()
            if not keep_file:self.docx_path=None; self.docx_info=None
        if format_type in {"pdf","pptx"} and hasattr(self,"pptx_selection_display_to_value"):
            display=next((label for label,value in self.pptx_selection_display_to_value.items() if value==scope),None)
            if display:self.pptx_selection_display_var.set(display)
        if format_type in {"pdf","pptx"} and hasattr(self,"pptx_selected_frame"):self._update_pptx_selection_fields()
        if getattr(self,"pptx_preview_label",None):self.pptx_preview_label.configure(image=None,text="")
        if getattr(self,"pptx_slide_status",None):self.pptx_slide_status.configure(text="")
        if getattr(self,"pptx_scope_validation_label",None):self.pptx_scope_validation_label.configure(text="")
        if getattr(self,"pptx_previous_button",None):self.pptx_previous_button.configure(state="disabled"); self.pptx_next_button.configure(state="disabled")
        if hasattr(self,"status_var"):self.status_var.set("")

    def _sync_document_scope_controls(self,format_type):
        state=self.document_scope_states[format_type]
        self.pptx_selection_mode_var.set(state.mode); self.pptx_selected_var.set(state.selected); self.pptx_range_var.set(state.ranges)

    def _capture_document_scope_controls(self,format_type):
        state=self.document_scope_states[format_type]
        state.mode=self.pptx_selection_mode_var.get(); state.selected=self.pptx_selected_var.get(); state.ranges=self.pptx_range_var.get()

    def _reset_document_scope(self,format_type,mode):
        """Internal reset: preserve the file and visuals, rebuild preview safely."""
        if not hasattr(self,"document_scope_states"):self.document_scope_states={"pdf":DocumentScopeState(),"pptx":DocumentScopeState()}
        state=self.document_scope_states[format_type]
        if mode in {"selected","range"}:
            state.begin_edit(mode); MarkerApp._sync_document_scope_controls(self,format_type); self._update_pptx_selection_fields(); self.pptx_scope_validation_label.configure(text=""); return
        state.mode=mode; MarkerApp._sync_document_scope_controls(self,format_type)
        total=self.pdf_info.metrics.item_count if format_type=="pdf" and self.pdf_info else self.pptx_metrics.item_count if format_type=="pptx" and self.pptx_metrics else 0
        try:scope=state.normalize(total) if total else ()
        except ValueError:scope=()
        if format_type=="pdf":
            self.pdf_preview_state.initialize(total,scope[0] if scope else 1); self.pdf_preview_renderer=PdfPreviewRenderer(self.processor)
        else:
            self.pptx_preview_state.initialize(total,scope[0] if scope else 1); self.pptx_preview_renderer.clear()
        display=next((label for label,value in self.pptx_selection_display_to_value.items() if value==mode),None)
        if display and hasattr(self,"pptx_selection_display_var"):self.pptx_selection_display_var.set(display)
        self.pptx_scope_validation_label.configure(text="")
        self._update_pptx_selection_fields()
        if not scope and total:
            self.pptx_preview_photo=None; key="pdf.selected_hint" if format_type=="pdf" else "pptx.selected_hint"
            self.pptx_preview_label.configure(image=None,text=self.translator.text(key)); self.pptx_slide_status.configure(text=""); self.pptx_previous_button.configure(state="disabled"); self.pptx_next_button.configure(state="disabled")
            MarkerApp._ensure_global_controls_enabled(self)
            return
        try:MarkerApp._rebuild_document_preview(self,format_type)
        finally:MarkerApp._ensure_global_controls_enabled(self)

    def _rebuild_document_preview(self,format_type):
        try:
            if format_type=="pdf":self.update_pdf_preview()
            else:self.update_pptx_preview()
        except Exception:
            self.pptx_preview_photo=None; key="pdf.preview_unavailable" if format_type=="pdf" else "pptx.preview_unavailable"
            self.pptx_preview_label.configure(image=None,text=self.translator.text(key)); self.pptx_slide_status.configure(text=""); self.pptx_previous_button.configure(state="disabled"); self.pptx_next_button.configure(state="disabled")

    def _ensure_global_controls_enabled(self):
        for name in ("language_menu","reset_button","guide_button","media_navigation","document_navigation","tools_navigation"):
            control=getattr(self,name,None)
            if control is None:continue
            try:control.configure(state="normal")
            except (TclError,AttributeError):pass

    def _render_active_document(self):
        if self.active_content_type not in {"pdf","pptx"}:return
        self._bind_document_context_widgets(self.active_content_type)
        if not hasattr(self,"document_format_label"):return
        label=next((display for display,kind in self.content_display_to_kind.items() if kind==self.active_content_type),self.active_content_type.upper())
        self.document_format_label.configure(text=label)
        self._synchronize_document_widgets()

    def _synchronize_document_widgets(self):
        """Render every shared document widget solely from active_content_type."""
        if self.active_content_type not in {"pdf","pptx"} or not hasattr(self,"pptx_choose_button"):return
        t=self.translator.text; is_pdf=self.active_content_type=="pdf"
        self.pptx_file_label.configure(textvariable=self.pdf_file_var if is_pdf else self.pptx_file_var)
        self.pptx_choose_button.configure(text=t("pdf.choose") if is_pdf else t("pptx.choose"))
        self.pptx_badge_label.configure(text=t("badge")); self.pdf_badge_enable.configure(text=t("pdf.add_badge"))
        value=lambda name, default: getattr(getattr(self,name,None),"get",lambda:default)()
        for name, text in (("pptx_position_label",t("position")),("pptx_size_label",t("size.value",value=value("size_var",0))),("pptx_opacity_label",t("opacity.value",value=value("opacity_var",0))),("pptx_margin_label",t("margin.value",value=value("margin_var",0))),("pptx_logo_enable",t("logo.enable")),("pptx_logo_choose",t("logo.choose")),("pptx_logo_size_label",t("logo.size",value=value("logo_size_var",0))),("pptx_logo_margin_label",t("logo.margin",value=value("logo_margin_var",0))),("pptx_logo_opacity_label",t("logo.opacity",value=value("logo_opacity_var",0)))):
            widget=getattr(self,name,None)
            if widget:widget.configure(text=text)
        if getattr(self,"pptx_badge_menu",None):self.pptx_badge_menu.configure(values=list(getattr(self,"badge_display_to_file",{})) or [t("badge.none")])
        if getattr(self,"pptx_position_menu",None):self.pptx_position_menu.configure(values=list(self.position_display_to_value)); self.pptx_logo_position_menu.configure(values=list(self.logo_position_display_to_value))
        if is_pdf:self.pptx_badge_label.grid_remove(); self.pdf_badge_enable.grid()
        else:self.pptx_badge_label.grid(); self.pdf_badge_enable.grid_remove()
        self.pptx_badge_menu.configure(state="normal" if not is_pdf or self.pdf_badge_enabled_var.get() else "disabled")
        scope_prefix="pdf.scope" if is_pdf else "pptx.scope"
        self._sync_document_scope_controls(self.active_content_type)
        self.pptx_scope_label.configure(text=t(scope_prefix))
        self.pptx_selection_display_to_value={t(scope_prefix+".first"):"first",t(scope_prefix+".selected"):"selected",t(scope_prefix+".range"):"range",t(scope_prefix+".all"):"all"}
        self.pptx_selection_menu.configure(values=list(self.pptx_selection_display_to_value))
        self.pptx_selection_display_var.set(next((display for display,value in self.pptx_selection_display_to_value.items() if value==self.pptx_selection_mode_var.get()),t(scope_prefix+".all")))
        self.pptx_selected_label.configure(text=t("pdf.selected_hint") if is_pdf else t("pptx.selected_hint")); self.pptx_range_label.configure(text=t("pdf.range_hint") if is_pdf else t("pptx.range_hint"))
        for name in ("pptx_selected_update_button","pptx_range_update_button"):
            widget=getattr(self,name,None)
            if widget:widget.configure(text=t("document.scope_update"))
        self.pptx_metadata_note.configure(text=t("pdf.metadata_note") if is_pdf else t("pptx.metadata_note")); self.pptx_process_button.configure(text=t("pdf.process") if is_pdf else t("pptx.process"))
        if is_pdf:self.pptx_language_label.grid_remove(); self.pptx_language_menu.grid_remove()
        else:self.pptx_language_label.grid(); self.pptx_language_menu.grid()
        self._set_active_document_summary(); self._update_pptx_selection_fields(); self._update_pptx_logo_controls(); self.update_pptx_preview()

    def _validate_content_invariant(self):
        if self.visible_workspace_type!=self.active_content_type or self.active_runtime_context_type!=self.active_content_type:raise RuntimeError("Visible workspace/runtime context does not match active content type.")
        if self.active_content_type=="pdf" and (self.pptx_path is not None or self.pptx_metrics is not None or self.pptx_preview_state.count):raise RuntimeError("PPTX runtime leaked into PDF state.")
        if self.active_content_type=="pptx" and (self.pdf_path is not None or self.pdf_info is not None or self.pdf_preview_state.count):raise RuntimeError("PDF runtime leaked into PPTX state.")

    def choose_active_document(self):
        if self.active_content_type=="pdf":self.choose_pdf()
        else:self.choose_pptx()

    def process_active_document(self):
        if self.active_content_type=="pdf":self.process_pdf()
        else:self.pptx_workspace_state._save_as()

    def change_document_preview_page(self,delta):
        if self.active_content_type=="pdf":self.change_pdf_preview_page(delta)
        else:self.change_pptx_preview_slide(delta)

    def _set_active_document_summary(self):
        if self.active_content_type=="pdf":
            if self.pdf_path and self.pdf_info:self.pdf_file_var.set(f"{self.pdf_path.name}\n{self.translator.text('document.summary.pages',size=human_file_size(self.pdf_info.metrics.size_bytes),count=self.pdf_info.metrics.item_count)}")
            else:self.pdf_file_var.set(self.translator.text("pdf.no_file"))
        else:
            self.pptx_file_var.set(self.pptx_path.name if self.pptx_path else self.translator.text("pptx.no_file")); self._set_pptx_file_summary()

    def choose_pdf(self):
        selected=filedialog.askopenfilename(title=self.translator.text("pdf.choose"),filetypes=[("PDF (*.pdf)","*.pdf"),(self.translator.text("files.all"),"*.*")])
        if not selected:return
        self.reset_format_context("pdf")
        self.pdf_path=Path(selected); self.pdf_preview_renderer=PdfPreviewRenderer(self.processor); self._pdf_warning_approved=None; self._pdf_signature_approved=None
        try:self.pdf_info=self.pdf_processor.inspect(self.pdf_path)
        except PasswordProtectedPdfError:messagebox.showerror(self.translator.text("error.title"),self.translator.text("pdf.encrypted")); self.pdf_path=None; self.pdf_info=None; self._set_active_document_summary(); return
        except (OSError,ValueError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("pdf.error",error=error)); self.pdf_path=None; self.pdf_info=None; self._set_active_document_summary(); return
        self.document_scope_states["pdf"].reset("all"); self.document_scope_states["pdf"].normalize(self.pdf_info.metrics.item_count); self._sync_document_scope_controls("pdf"); self.pdf_preview_state.initialize(self.pdf_info.metrics.item_count); self._set_active_document_summary()
        if not self._confirm_pdf_limits():return
        self.status_var.set(self.translator.text("pdf.selected",name=self.pdf_path.name)); self.update_pdf_preview()

    def _confirm_pdf_limits(self):
        if not self.pdf_path or not self.pdf_info:return False
        assessment=assess_document("pdf",self.pdf_info.metrics); fingerprint=(self.pdf_path.resolve(),self.pdf_info.metrics.size_bytes,self.pdf_info.metrics.item_count)
        if assessment.blocked:messagebox.showerror(self.translator.text("document.limit_title"),self.translator.text("document.pdf_hard")); return False
        if assessment.requires_warning and self._pdf_warning_approved!=fingerprint:
            if not messagebox.askokcancel(self.translator.text("document.warning_title"),self.translator.text("document.pdf_warning")):return False
            self._pdf_warning_approved=fingerprint
        return True

    def _confirm_pdf_signature(self):
        if not self.pdf_path or not self.pdf_info or not self.pdf_info.signed:return True
        fingerprint=(self.pdf_path.resolve(),self.pdf_info.metrics.size_bytes)
        if self._pdf_signature_approved==fingerprint:return True
        if not messagebox.askokcancel(self.translator.text("pdf.signature_title"),self.translator.text("pdf.signature_warning")):return False
        self._pdf_signature_approved=fingerprint; return True

    def change_pdf_preview_page(self,delta):
        current=self.pdf_preview_state.move(delta)
        if current is not None:
            self.update_pdf_preview()

    def _current_document_item_is_marked(self,format_type):
        state=self.document_scope_states[format_type]
        preview=self.pdf_preview_state if format_type=="pdf" else self.pptx_preview_state
        return preview.current in state.active_scope

    def update_pdf_preview(self):
        t=self.translator.text
        if not self.pdf_path or not self.pdf_info:
            self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("pdf.preview_hint")); self.pptx_slide_status.configure(text=""); self.pptx_previous_button.configure(state="disabled"); self.pptx_next_button.configure(state="disabled"); return
        marked=MarkerApp._current_document_item_is_marked(self,"pdf")
        badge=self.badges.find(self.badge_var.get()) if marked and self.pdf_badge_enabled_var.get() else None
        logo=self._logo_path() if marked and self.logo_enabled_var.get() else None
        preview_settings=replace(self.settings(),logo_enabled=bool(logo))
        try:
            result=self.pdf_preview_renderer.render(self.pdf_path,self.pdf_preview_state.current,badge,preview_settings,logo); self.pdf_preview_state.current=result.page_number; self.pptx_preview_photo=ctk.CTkImage(result.image,size=result.image.size); self.pptx_preview_label.configure(image=self.pptx_preview_photo,text=""); self.pptx_slide_status.configure(text=t("pdf.page_status",current=result.page_number,count=result.page_count)); self.pptx_previous_button.configure(state="normal" if self.pdf_preview_state.can_previous else "disabled"); self.pptx_next_button.configure(state="normal" if self.pdf_preview_state.can_next else "disabled")
        except (OSError,ValueError):self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("pdf.preview_unavailable")); self.pptx_slide_status.configure(text="")

    def process_pdf(self):
        if not self.pdf_path or not self.pdf_info:messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("pdf.choose_first")); return
        if not self._confirm_pdf_limits() or not self._confirm_pdf_signature():return
        badge=self.badges.find(self.badge_var.get()) if self.pdf_badge_enabled_var.get() else None; logo_path=self._logo_path() if self.logo_enabled_var.get() else None
        if not badge and not logo_path:messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("pdf.overlay_required")); return
        selected=filedialog.asksaveasfilename(title=self.translator.text("pdf.save_as"),initialdir=str(self.pdf_path.parent),initialfile=f"{self.pdf_path.stem}_ai.pdf",defaultextension=".pdf",filetypes=[("PDF (*.pdf)","*.pdf")],confirmoverwrite=True)
        if not selected:return
        try:
            if Path(selected).suffix.lower()!=".pdf":raise ValueError(self.translator.text("pdf.extension_error"))
            selection=ItemSelection("selected",self.document_scope_states["pdf"].active_scope); disclosure,logo=settings_for_documents(self.settings(),label=self.badge_name_var.get() or self.badges.display_name(badge.name if badge else self.badge_var.get())); result=self.pdf_processor.process(ProcessingRequest(self.pdf_path,Path(selected),disclosure,badge_path=badge,logo=logo),selection)
        except (OSError,ValueError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("pdf.error",error=error)); return
        text=self.translator.text("pdf.saved",name=result.destination.name,count=len(result.selected_pages)); self.status_var.set(text); messagebox.showinfo(self.translator.text("complete.title"),text)

    def choose_docx(self):
        selected=filedialog.askopenfilename(title=self.translator.text("docx.choose"),filetypes=[("Word (*.docx)","*.docx"),(self.translator.text("files.all"),"*.*")])
        if not selected:return
        self.docx_path=Path(selected); self.docx_preview_renderer.clear(); self._docx_warning_approved=None
        try:self.docx_info=self.docx_processor.inspect(self.docx_path)
        except (OSError,ValueError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("docx.error",error=error)); self.docx_path=None; self.docx_info=None; self._set_active_document_summary(); return
        self._set_active_document_summary()
        if not self._confirm_docx_limits():return
        self.status_var.set(self.translator.text("docx.selected",name=self.docx_path.name)); self.update_docx_preview()

    def _confirm_docx_limits(self):
        if not self.docx_path or not self.docx_info:return False
        assessment=assess_document("docx",self.docx_info.metrics); fingerprint=(self.docx_path.resolve(),self.docx_info.metrics.size_bytes)
        if assessment.blocked:messagebox.showerror(self.translator.text("document.limit_title"),self.translator.text("document.docx_hard")); return False
        if assessment.requires_warning and self._docx_warning_approved!=fingerprint:
            if not messagebox.askokcancel(self.translator.text("document.warning_title"),self.translator.text("document.docx_warning")):return False
            self._docx_warning_approved=fingerprint
        return True

    def update_docx_preview(self):
        t=self.translator.text
        if not self.docx_path or not self.docx_info:
            self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("docx.preview_hint")); self.pptx_slide_status.configure(text="—"); return
        badge=self.badges.find(self.badge_var.get()) if self.pdf_badge_enabled_var.get() else None; logo=self._logo_path() if self.logo_enabled_var.get() else None
        if not badge and not logo:
            self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("docx.overlay_required")); return
        try:
            result=self.docx_preview_renderer.render(self.docx_path,badge,self.settings(),logo); self.pptx_preview_photo=ctk.CTkImage(result.image,size=result.image.size); self.pptx_preview_label.configure(image=self.pptx_preview_photo,text=""); self.pptx_slide_status.configure(text=t("docx.preview_approximate"))
        except (OSError,ValueError,KeyError):self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("docx.preview_unavailable")); self.pptx_slide_status.configure(text="—")

    def process_docx(self):
        if not self.docx_path or not self.docx_info:messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("docx.choose_first")); return
        if not self._confirm_docx_limits():return
        badge=self.badges.find(self.badge_var.get()) if self.pdf_badge_enabled_var.get() else None; logo_path=self._logo_path() if self.logo_enabled_var.get() else None
        if not badge and not logo_path:messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("docx.overlay_required")); return
        selected=filedialog.asksaveasfilename(title=self.translator.text("docx.save_as"),initialdir=str(self.docx_path.parent),initialfile=f"{self.docx_path.stem}_ai.docx",defaultextension=".docx",filetypes=[("Word (*.docx)","*.docx")],confirmoverwrite=True)
        if not selected:return
        try:
            destination=Path(selected)
            if destination.suffix.lower()!=".docx":raise ValueError(self.translator.text("docx.extension_error"))
            display_name=self.badge_name_var.get() or self.badges.display_name(badge.name if badge else self.badge_var.get()); language=LANGUAGES.get(self.pptx_language_var.get(),"en"); disclosure,logo=settings_for_documents(self.settings(),label=display_name,disclosure_language=language)
            result=self.docx_processor.process(ProcessingRequest(self.docx_path,destination,disclosure,badge_path=badge,logo=logo),self.docx_scope_var.get())
        except (OSError,ValueError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("docx.error",error=error)); return
        text=self.translator.text("docx.saved",name=result.destination.name); self.status_var.set(text); messagebox.showinfo(self.translator.text("complete.title"),text)

    def choose_pptx(self):
        selected=filedialog.askopenfilename(title=self.translator.text("pptx.choose"),filetypes=[("PowerPoint (*.pptx)","*.pptx"),(self.translator.text("files.all"),"*.*")])
        if selected:
            self.reset_format_context("pptx")
            self.pptx_path=Path(selected); self.pptx_preview_state.clear(); self.pptx_preview_renderer.clear(); self._pptx_warning_approved=None
            try:self.pptx_metrics=self.pptx_processor.document_metrics(self.pptx_path)
            except (OSError,ValueError,KeyError):
                self.pptx_metrics=None; self.pptx_file_var.set(self.pptx_path.name); self.update_pptx_preview(); return
            self.document_scope_states["pptx"].reset("all"); self.document_scope_states["pptx"].normalize(self.pptx_metrics.item_count); self._sync_document_scope_controls("pptx"); self.pptx_preview_state.initialize(self.pptx_metrics.item_count)
            self._set_pptx_file_summary()
            if not self._confirm_pptx_limits():
                if not assess_document("pptx",self.pptx_metrics).blocked:self._clear_pptx_selection()
                return
            self.status_var.set(self.translator.text("pptx.selected",name=self.pptx_path.name)); self.update_pptx_preview()

    def _set_pptx_file_summary(self):
        if not self.pptx_path or not self.pptx_metrics:return
        self.pptx_file_var.set(f"{self.pptx_path.name}\n{self.translator.text('document.summary.slides',size=human_file_size(self.pptx_metrics.size_bytes),count=self.pptx_metrics.item_count)}")

    def _clear_pptx_selection(self):
        self.pptx_path=None; self.pptx_metrics=None; self._pptx_warning_approved=None; self.pptx_preview_state.clear(); self.pptx_preview_photo=None; self.pptx_preview_renderer.clear(); self.pptx_file_var.set(self.translator.text("pptx.no_file")); self.update_pptx_preview()

    def _confirm_pptx_limits(self):
        if not self.pptx_path or not self.pptx_metrics:return False
        assessment=assess_document("pptx",self.pptx_metrics); fingerprint=(self.pptx_path.resolve(),self.pptx_metrics.size_bytes,self.pptx_metrics.item_count)
        if assessment.blocked:
            messagebox.showerror(self.translator.text("document.limit_title"),self.translator.text("document.pptx_hard")); return False
        if assessment.requires_warning and self._pptx_warning_approved != fingerprint:
            if not messagebox.askokcancel(self.translator.text("document.warning_title"),self.translator.text("document.pptx_warning")):return False
            self._pptx_warning_approved=fingerprint
        return True

    def change_pptx_selection_mode(self,label):
        mode=self.pptx_selection_display_to_value.get(label,"all"); kind=self.active_content_type
        MarkerApp._reset_document_scope(self,kind,mode)

    def commit_document_selection(self,_event=None):
        if self.active_content_type not in {"pptx","pdf"}:return
        MarkerApp._capture_document_scope_controls(self,self.active_content_type)
        metrics=self.pptx_metrics if self.active_content_type=="pptx" else self.pdf_info.metrics if self.pdf_info else None
        if not metrics:return
        try:
            selection=pptx_item_selection(self.pptx_selection_mode_var.get(),selected=self.pptx_selected_var.get(),ranges=self.pptx_range_var.get())
            items=selection.resolve(metrics.item_count)
        except ValueError:
            message=self.translator.text("document.scope_invalid")
            self.pptx_scope_validation_label.configure(text=message); self.status_var.set(message)
            return
        state=self.document_scope_states[self.active_content_type]
        state.active_scope=items
        preview_state=self.pptx_preview_state if self.active_content_type=="pptx" else self.pdf_preview_state
        preview_state.initialize(metrics.item_count,items[0])
        if self.active_content_type=="pptx":self.pptx_preview_renderer.clear()
        self.pptx_scope_validation_label.configure(text=""); self.status_var.set("")
        MarkerApp._rebuild_document_preview(self,self.active_content_type)

    def _update_pptx_selection_fields(self):
        for frame in (self.pptx_selected_frame,self.pptx_range_frame):frame.grid_remove()
        frame={"selected":self.pptx_selected_frame,"range":self.pptx_range_frame}.get(self.pptx_selection_mode_var.get())
        if frame:frame.grid(row=3,column=0,padx=14,pady=8,sticky="ew")

    def _update_pptx_logo_controls(self):
        self.pptx_logo_enable.grid(); self.pptx_logo_choose.grid()
        if self.logo_enabled_var.get() and self._logo_path():self.pptx_logo_settings.grid()
        else:self.pptx_logo_settings.grid_remove()

    def pdf_overlay_changed(self):
        self.pptx_badge_menu.configure(state="normal" if self.pdf_badge_enabled_var.get() else "disabled"); self.update_pptx_preview()

    def change_pptx_preview_slide(self,delta):
        current=self.pptx_preview_state.move(delta)
        if current is not None:
            self.update_pptx_preview()

    def update_pptx_preview(self):
        if not hasattr(self,"pptx_preview_label"):return
        if self.active_content_type=="pdf":self.update_pdf_preview(); return
        t=self.translator.text
        if not self.pptx_path or not self.pptx_path.is_file():
            self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("pptx.preview_hint")); self.pptx_slide_status.configure(text=""); self.pptx_previous_button.configure(state="disabled"); self.pptx_next_button.configure(state="disabled"); return
        marked=MarkerApp._current_document_item_is_marked(self,"pptx")
        badge=self.badges.find(self.badge_var.get()) if marked else None
        if marked and not badge:
            self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("pptx.preview_unavailable")); self.pptx_slide_status.configure(text=""); return
        logo=self._logo_path() if marked and self.logo_enabled_var.get() else None
        preview_settings=replace(self.settings(),logo_enabled=bool(logo))
        try:
            preview_settings=replace(preview_settings, position=self.pptx_badge_position_var.get(), size_percent=self.pptx_badge_size_var.get(), margin=self.pptx_badge_margin_var.get(), opacity=self.pptx_badge_opacity_var.get(), logo_position=self.pptx_logo_position_var.get(), logo_size_percent=self.pptx_logo_size_var.get(), logo_margin=self.pptx_logo_margin_var.get(), logo_opacity=self.pptx_logo_opacity_var.get())
            result=self.pptx_preview_renderer.render(self.pptx_path,self.pptx_preview_state.current,badge,preview_settings,logo)
            self.pptx_preview_state.current=result.slide_number; self.pptx_preview_photo=ctk.CTkImage(result.image,size=result.image.size); self.pptx_preview_label.configure(image=self.pptx_preview_photo,text=""); self.pptx_slide_status.configure(text=t("pptx.slide_status",current=result.slide_number,count=result.slide_count))
            self.pptx_previous_button.configure(state="normal" if self.pptx_preview_state.can_previous else "disabled"); self.pptx_next_button.configure(state="normal" if self.pptx_preview_state.can_next else "disabled")
        except (OSError,ValueError,KeyError):
            self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("pptx.preview_unavailable")); self.pptx_slide_status.configure(text="")

    def process_pptx_from_workspace(self, state) -> None:
        """Save from the authoritative PptxWorkspaceState boundary.

        This is intentionally separate from the legacy MarkerApp fields: the
        active workspace supplies the source path, scope and visual projection.
        """
        source = getattr(state, "path", None)
        if not source or not Path(source).is_file():
            messagebox.showwarning(self.translator.text("warning.title"), self.translator.text("pptx.choose_first")); return
        source = Path(source)
        workspace = getattr(self, "pptx_workspace_state", None)
        receipts = getattr(workspace, "receipts", None)
        if receipts:
            receipts.record({"layer": "pptx", "event": "PPTX_SAVE_DIALOG_REQUEST"})
        try:
            metrics = self.pptx_processor.document_metrics(source)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror(self.translator.text("error.title"), self.translator.text("pptx.error", error=error)); return
        assessment = assess_document("pptx", metrics)
        if assessment.blocked:
            messagebox.showerror(self.translator.text("document.limit_title"), self.translator.text("document.pptx_hard")); return
        if assessment.requires_warning and not messagebox.askokcancel(self.translator.text("document.warning_title"), self.translator.text("document.pptx_warning")):
            return
        badge = self.badges.find(state.badge.badge_id) if state.badge.enabled else None
        logo_path = Path(state.logo.path) if state.logo.enabled and state.logo.path else None
        if not badge and not logo_path:
            messagebox.showwarning(self.translator.text("warning.title"), self.translator.text("pdf.overlay_required")); return
        selected = filedialog.asksaveasfilename(title=self.translator.text("pptx.save_as"), initialdir=str(source.parent), initialfile=f"{source.stem}_ai.pptx", defaultextension=".pptx", filetypes=[("PowerPoint (*.pptx)", "*.pptx"), (self.translator.text("files.all"), "*.*")], confirmoverwrite=True)
        if not selected:
            return
        destination = Path(selected)
        if receipts:
            receipts.record({"layer": "pptx", "event": "PPTX_SAVE_DESTINATION", "selected": True})
        if destination.resolve() == source.resolve() or destination.suffix.lower() != ".pptx":
            messagebox.showerror(self.translator.text("error.title"), self.translator.text("pptx.extension_error")); return
        settings = MarkerSettings(badge_name=state.badge.badge_id, position=state.badge.position, size_percent=state.badge.size, margin=state.badge.margin, opacity=state.badge.opacity, logo_enabled=bool(logo_path), logo_path=str(logo_path or ""), logo_position=state.logo.position, logo_size_percent=state.logo.size, logo_margin=state.logo.margin, logo_opacity=state.logo.opacity, language=self.translator.language).validated()
        label = self.badges.display_name(badge.name) if badge else "No AI badge"
        disclosure, logo = settings_for_documents(settings, label=label, disclosure_language=self.translator.language)
        if receipts:
            receipts.record({"layer": "pptx", "event": "PPTX_PROCESS_START"})
        try:
            result = self.pptx_processor.process(ProcessingRequest(source, destination, disclosure, badge_path=badge, logo=logo), ItemSelection("selected", tuple(state.active_scope)))
        except (OSError, ValueError) as error:
            messagebox.showerror(self.translator.text("error.title"), self.translator.text("pptx.error", error=error)); return
        text = self.translator.text("pptx.saved", name=result.destination.name, count=len(result.selected_slides)); self.status_var.set(text); messagebox.showinfo(self.translator.text("complete.title"), text)
    def _render_update_notification(self):
        if self._available_update_version:
            self.update_notification.configure(text=self.translator.text("update.available",version=self._available_update_version)); self.update_notification.grid()
        else:self.update_notification.grid_remove()
    def _automatic_update_preference_changed(self):
        self._save()
        if self.automatic_update_var.get():self.after(0,self._automatic_update_check)
    def _automatic_update_check(self):
        if self._automatic_update_attempted or not self.automatic_update_var.get() or not should_check_automatically(self.last_update_check):return
        self._automatic_update_attempted=True; self._start_update_check(False)
    def check_for_updates(self): self._start_update_check(True)
    def _start_update_check(self,manual):
        if self._update_check_running:
            if manual:self.status_var.set(self.translator.text("update.checking"))
            return
        self._update_check_running=True
        if manual:self.status_var.set(self.translator.text("update.checking"))
        def worker():
            try:result=check_for_update(__version__); error=None
            except UpdateCheckError as caught:result=None; error=caught
            try:self.after(0,lambda:self._finish_update_check(result,error,manual))
            except (RuntimeError,TclError):pass
        threading.Thread(target=worker,name="NenolinkUpdateCheck",daemon=True).start()
    def _finish_update_check(self,result,error,manual):
        self._update_check_running=False
        if error:
            if manual:messagebox.showerror(self.translator.text("error.title"),self.translator.text("update.error"))
            return
        self.last_update_check=result.checked_at
        if result.update_available:
            self._available_update_version=result.manifest.latest_version; self._available_update_url=result.manifest.update_url
            self._render_update_notification()
            if manual:self.status_var.set(self.translator.text("update.available",version=result.manifest.latest_version))
        else:
            self._available_update_version=""; self._available_update_url=""; self._render_update_notification()
            if manual:messagebox.showinfo(self.translator.text("update.title"),self.translator.text("update.current",version=__version__))
        self._save()
    def _open_update_page(self,_event=None):
        if is_approved_update_url(self._available_update_url):webbrowser.open(self._available_update_url)
    def create_shortcut(self):
        try:create_desktop_shortcut()
        except ShortcutError:messagebox.showerror(self.translator.text("shortcut.title"),self.translator.text("shortcut.error"))
        else:messagebox.showinfo(self.translator.text("shortcut.title"),self.translator.text("shortcut.success"))
    def _show_first_run_shortcut_offer(self):
        if self.shortcut_offer_shown or not getattr(sys,"frozen",False):return
        self.shortcut_offer_shown=True; self._save()
        dialog=ctk.CTkToplevel(self); self.shortcut_offer_dialog=dialog
        dialog.title(self.translator.text("shortcut.offer_title")); dialog.resizable(False,False); dialog.transient(self)
        dialog.grid_columnconfigure(0,weight=1)
        self.shortcut_offer_title_label=ctk.CTkLabel(dialog,text=self.translator.text("shortcut.offer_title"),font=ctk.CTkFont(size=18,weight="bold")); self.shortcut_offer_title_label.grid(row=0,column=0,padx=24,pady=(22,8),sticky="w")
        self.shortcut_offer_message_label=ctk.CTkLabel(dialog,text=self.translator.text("shortcut.offer_message"),wraplength=390,justify="left"); self.shortcut_offer_message_label.grid(row=1,column=0,padx=24,pady=(0,18),sticky="w")
        actions=ctk.CTkFrame(dialog,fg_color="transparent"); actions.grid(row=2,column=0,padx=24,pady=(0,22),sticky="e")
        self.shortcut_offer_not_now_button=ctk.CTkButton(actions,text=self.translator.text("shortcut.offer_not_now"),command=self._dismiss_shortcut_offer,fg_color="transparent",border_width=1,width=110); self.shortcut_offer_not_now_button.grid(row=0,column=0,padx=(0,8))
        self.shortcut_offer_create_button=ctk.CTkButton(actions,text=self.translator.text("shortcut.offer_create"),command=self._accept_shortcut_offer,width=140); self.shortcut_offer_create_button.grid(row=0,column=1)
        dialog.protocol("WM_DELETE_WINDOW",self._dismiss_shortcut_offer); dialog.update_idletasks()
        x=self.winfo_rootx()+max(0,(self.winfo_width()-dialog.winfo_reqwidth())//2); y=self.winfo_rooty()+max(0,(self.winfo_height()-dialog.winfo_reqheight())//2)
        dialog.geometry(f"+{x}+{y}"); dialog.grab_set(); dialog.focus_force()
    def _dismiss_shortcut_offer(self):
        if self.shortcut_offer_dialog is not None:
            try:self.shortcut_offer_dialog.grab_release(); self.shortcut_offer_dialog.destroy()
            except TclError:pass
        self.shortcut_offer_dialog=None
    def _accept_shortcut_offer(self):self._dismiss_shortcut_offer(); self.create_shortcut()
    def show_tab(self,key):
        if key in {"badges","inspect"}:
            self.change_auxiliary_workspace(key)
        elif key in self._secondary_navigation_keys():
            self.tabs.set(self.tab_names[key])
    def navigate_home(self):
        if self.active_tool:
            self.dispatch_shell_event("back")
            return
        self.render_shell_state()
    def choose_inspection_file(self):
        patterns=" ".join(f"*{extension}" for extension in sorted(INSPECT_EXTENSIONS | {".pdf",".pptx"}))
        selected=filedialog.askopenfilename(title=self.translator.text("inspect.choose"),filetypes=[(self.translator.text("inspect.supported"),patterns),(self.translator.text("files.all"),"*.*")])
        if not selected:return
        self.inspection_path=Path(selected); self.inspection_result=None; self.inspection_error=""; self.inspection_unsupported=False
        if self.inspection_path.suffix.lower() in {".pdf",".pptx"}:self.inspection_unsupported=True
        else:
            try:self.inspection_result=inspect_file(self.inspection_path)
            except (OSError,ValueError) as error:self.inspection_error=str(error)
        self._render_inspection()
    def _render_inspection(self):
        if not hasattr(self,"inspect_file_var"):return
        t=self.translator.text; missing=t("inspect.not_available")
        self.inspect_file_var.set(self.inspection_path.name if self.inspection_path else t("inspect.none"))
        if self.inspection_result:
            result=self.inspection_result; self.inspect_format_var.set(f"{result.media_format} · {human_file_size(result.size)}"); self.inspect_status_var.set(t("inspect.found") if result.found else t("inspect.not_found")); self.inspect_software_var.set(result.software or missing); self.inspect_label_var.set(result.ai_label or missing); self.inspect_version_var.set(result.marker_version or missing); self.inspect_message_var.set(t("inspect.info") if result.found else t("inspect.not_found_message")+"\n"+t("inspect.no_ai_warning"))
        elif getattr(self,"inspection_unsupported",False):
            suffix=self.inspection_path.suffix.lower().lstrip(".").upper() if self.inspection_path else ""; size=human_file_size(self.inspection_path.stat().st_size) if self.inspection_path and self.inspection_path.is_file() else ""; self.inspect_format_var.set(" · ".join(value for value in (suffix,size) if value)); self.inspect_status_var.set(t("inspect.not_supported_yet")); self.inspect_software_var.set(missing); self.inspect_label_var.set(missing); self.inspect_version_var.set(missing); self.inspect_message_var.set(t("inspect.document_unsupported"))
        elif self.inspection_error:
            suffix=self.inspection_path.suffix.lower().lstrip(".").upper() if self.inspection_path else ""; size=human_file_size(self.inspection_path.stat().st_size) if self.inspection_path and self.inspection_path.is_file() else ""; self.inspect_format_var.set(" · ".join(value for value in (suffix,size) if value)); self.inspect_status_var.set(t("inspect.error")); self.inspect_software_var.set(missing); self.inspect_label_var.set(missing); self.inspect_version_var.set(missing); self.inspect_message_var.set(t("inspect.error_message",reason=self.inspection_error))
        else:
            self.inspect_format_var.set(""); self.inspect_status_var.set(t("inspect.ready")); self.inspect_software_var.set(missing); self.inspect_label_var.set(missing); self.inspect_version_var.set(missing); self.inspect_message_var.set(t("inspect.no_ai_warning"))
    def _clear_document_states(self):
        for kind in ("pptx","pdf","docx"):
            try:self.reset_format_context(kind)
            except Exception:
                if kind=="pptx":self.pptx_path=None; self.pptx_metrics=None; self.pptx_preview_state.clear()
                elif kind=="pdf":self.pdf_path=None; self.pdf_info=None; self.pdf_preview_state.clear()
                else:self.docx_path=None; self.docx_info=None
        for state in self.document_scope_states.values():state.reset()
        self.pptx_selection_mode_var.set("all"); self.pptx_selected_var.set(""); self.pptx_range_var.set("1-2"); self.pptx_file_var.set("")
        if hasattr(self,"pptx_scope_validation_label"):self.pptx_scope_validation_label.configure(text="")
    def select_badge(self):
        self.badge_display_var.set(self.badges.display_name(self.badge_var.get()))
        self.update_badge_preview(); self.update_gallery_selection()
        if self.active_content_type == "image": self.image_workspace_owner.refresh_preview()
        elif self.active_content_type == "video": self.video_workspace_owner.refresh_preview()
        elif self.active_content_type == "pdf":self.pdf_workspace_owner.refresh_preview()
        elif self.active_content_type == "pptx":
            self._project_pptx_badge_visual()
            self._update_pptx_preview()
        self._save()
    def select_badge_display(self,display_name):
        filename=self.badge_display_to_file.get(display_name)
        if filename:self.badge_var.set(filename); self.select_badge()
    def select_gallery_badge(self,filename): self.badge_var.set(filename); self.select_badge()

    def browse_custom_badges(self):
        value=filedialog.askdirectory(title=self.translator.text("dialog.custom_badges"))
        if value: self.custom_badge_var.set(value); self.badge_source_var.set("custom"); self.refresh_badges(); self._save()

    def refresh_badges(self,show_dialog=True):
        self.badges=self.badge_sources.repository(self.badge_source_var.get(),self.custom_badge_var.get()); missing=self.badge_sources.fallback_reason
        names=[p.name for p in self.badges.display_badges()]
        displays=[self.badges.display_name(name) for name in names]; self.badge_display_to_file=dict(zip(displays,names))
        if getattr(self,"badge_menu",None):self.badge_menu.configure(values=displays or [self.translator.text("badge.none")])
        if getattr(self,"pptx_badge_menu",None):self.pptx_badge_menu.configure(values=displays or [self.translator.text("badge.none")])
        if getattr(self,"pdf_badge_menu",None):self.pdf_badge_menu.configure(values=displays or [self.translator.text("badge.none")])
        self.badge_var.set(choose_badge_selection(self.badge_source_var.get(),names,self.badge_var.get()))
        if missing:text=self.translator.text("badge.custom_missing")
        elif names and self.badge_source_var.get()=="standard":text=self.translator.text("badge.loaded_standard",count=len(names))
        elif names:text=self.translator.text("badge.loaded_custom",count=len(names))
        elif self.badge_source_var.get()=="custom":text=self.translator.text("badge.custom_empty")
        else:text=self.translator.text("badge.not_found",folder=self.badges.directory)
        self.status_var.set(text)
        if show_dialog and (missing or not names):messagebox.showwarning(self.translator.text("warning.title"),text)
        self._show_badge_source_controls(); self.rebuild_badge_gallery(); self.select_badge()

    def rebuild_badge_gallery(self):
        for widget in self.gallery.winfo_children():widget.destroy()
        self.gallery_photos=[]; self.gallery_buttons={}
        for index,badge in enumerate(self.badges.display_badges()):
            try:
                with Image.open(badge) as opened:image=opened.convert("RGBA")
                image.thumbnail((125,54),Image.Resampling.LANCZOS); photo=ctk.CTkImage(light_image=image,dark_image=image,size=image.size); self.gallery_photos.append(photo)
                button=ctk.CTkButton(self.gallery,text=self.badges.display_name(badge.name),image=photo,compound="top",height=94,fg_color="transparent",border_width=1,command=lambda name=badge.name:self.select_gallery_badge(name))
                button.grid(row=index//5,column=index%5,padx=5,pady=5,sticky="nsew"); self.gallery_buttons[badge.name]=button
            except OSError:continue
        self.update_gallery_selection()

    def update_gallery_selection(self):
        for filename,button in self.gallery_buttons.items():
            selected=filename==self.badge_var.get(); button.configure(fg_color=("#1f6aa5" if selected else "transparent"),border_width=(3 if selected else 1))

    def update_badge_preview(self):
        badge=self.badges.find(self.badge_var.get())
        if not badge:self.single_badge_preview_label.configure(image=None,text=self.translator.text("badge.none")); self.badge_name_var.set(""); return
        try:
            with Image.open(badge) as opened:image=opened.convert("RGBA")
            image.thumbnail((110,54),Image.Resampling.LANCZOS); self.single_badge_photo=ctk.CTkImage(light_image=image,dark_image=image,size=image.size); self.badge_photo=self.single_badge_photo; self.single_badge_preview_label.configure(image=self.single_badge_photo,text="")
            info=self.badges.metadata(badge.name); self.badge_name_var.set(info.display_name if info else self.badges.display_name(badge.name)); self.badge_description_var.set(self.translator.text("badge.no_ai_disclaimer") if badge.name=="no-ai.png" else (info.description if info else self.translator.text("badge.custom_description")))
        except OSError as error:self.single_badge_preview_label.configure(image=None,text=str(error))

    def choose_input_folder(self):
        value=filedialog.askdirectory(title=self.translator.text("button.choose_input"))
        if value:self.input_folder_var.set(value); self.scan=None; self.changed()
    def choose_output_folder(self):
        value=filedialog.askdirectory(title=self.translator.text("button.choose_output"))
        if value:self.output_folder_var.set(value); self.output_preference_var.set("separate"); self.changed()
    def scan_input_folder(self):
        root=Path(self.input_folder_var.get()).expanduser()
        if not root.is_dir():messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("batch.invalid_input",folder=root)); return
        self.scan=scan_folder(root,self.recursive_var.get()); selected=self.scan.selected(self.settings()); out=destination_root(self.settings(),root)
        summary=self.translator.text("batch.scan_summary",images=len(self.scan.images),videos=len(self.scan.videos),unsupported=len(self.scan.unsupported),total=len(selected),output=out)
        self.scan_summary_var.set(summary+"\n"+self.translator.text("batch.oversized",count=len(self.scan.oversized))); self._save()
    def start_batch(self):
        badge=self.badges.find(self.badge_var.get())
        if not self.scan or not badge:messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("batch.scan_first")); return
        if self.scan.selected(self.settings()) and any(path.suffix.lower() in VIDEO_EXTENSIONS for path in self.scan.selected(self.settings())) and not find_ffmpeg():messagebox.showerror(self.translator.text("error.title"),self.translator.text("error.video_component_missing")); return
        self.cancel_event.clear(); self.start_batch_button.configure(state="disabled"); self.cancel_batch_button.configure(state="normal"); settings=self.settings()
        def report(path,index,total,result):self.after(0,lambda:self._batch_progress(path,index,total,result))
        def work():
            result=self.batch_processor.process(self.scan,badge,settings,cancelled=self.cancel_event.is_set,progress=report); self.after(0,lambda:self._batch_done(result))
        threading.Thread(target=work,daemon=True).start()
    def _batch_progress(self,path,index,total,result):self.progress.set(index/max(1,total)); self.progress_text_var.set(self.translator.text("batch.progress",name=path.name,completed=index,total=total,success=result.successful,skipped=result.skipped,errors=len(result.errors)))
    def _batch_done(self,result:BatchResult):
        self.start_batch_button.configure(state="normal"); self.cancel_batch_button.configure(state="disabled"); text=self.translator.text("batch.done",success=result.successful,skipped=result.skipped,errors=len(result.errors)); self.progress_text_var.set((self.translator.text("batch.cancelled")+"\n" if result.cancelled else "")+text)
        if result.errors:messagebox.showerror(self.translator.text("error.completed"),text+"\n\n"+"\n".join(result.errors[:8]))
        elif result.metadata_warnings:messagebox.showwarning(self.translator.text("warning.title"),text+"\n\n"+self.translator.text("warning.metadata_failed"))
    def cancel_batch(self):self.cancel_event.set()
    def open_guide(self):
        try:open_user_guide(localized_user_guide_path(self.translator.language))
        except (OSError,FileNotFoundError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("guide.missing",error=error))

    def settings(self):
        return MarkerSettings(badge_name=self.badge_var.get(),position=self.position_var.get(),size_percent=self.size_var.get(),margin=self.margin_var.get(),opacity=self.opacity_var.get(),language=self.translator.language,badge_source=self.badge_source_var.get(),custom_badge_folder=self.custom_badge_var.get(),input_folder=self.input_folder_var.get(),output_preference=self.output_preference_var.get(),output_folder=self.output_folder_var.get(),output_subfolder=self.output_subfolder_var.get(),include_subfolders=self.recursive_var.get(),preserve_folder_structure=self.preserve_var.get(),process_images=self.images_var.get(),process_videos=self.videos_var.get(),skip_processed=self.skip_var.get(),video_mode=self.video_mode_var.get(),video_duration=self.video_duration_var.get(),batch_filename_suffix=self.batch_suffix_var.get(),logo_enabled=self.logo_enabled_var.get(),logo_path=self.logo_path_var.get(),logo_position=self.logo_position_var.get(),logo_size_percent=self.logo_size_var.get(),logo_margin=self.logo_margin_var.get(),logo_opacity=self.logo_opacity_var.get(),automatic_update_check=self.automatic_update_var.get(),last_update_check=self.last_update_check,shortcut_offer_shown=self.shortcut_offer_shown).validated()
    def _save(self):
        try:self.config_store.save(self.settings())
        except OSError:pass
    def destroy(self):
        self.cancel_event.set(); self._save()
        if self._reset_after_id:
            try:self.after_cancel(self._reset_after_id)
            except ValueError:pass
            self._reset_after_id=None
        super().destroy()


class MarkerApp(ctk.CTk):
    """Outer shell with the production Image workspace mounted as a child.

    The shell remains the sole owner of destinations.  Image is deliberately
    a hosted module: it can render and process images, but cannot select a
    top-level destination or replace the common host.
    """

    _labels = {
        "image": "Images", "video": "Video", "pdf": "PDF",
        "pptx": "PowerPoint / Slides", "badges": "Badges", "inspect": "Inspect File",
    }

    def __init__(self) -> None:
        super().__init__()
        self._boot = _runtime_boot_logger()
        self._boot('PDF_DIAGNOSTIC ' + json.dumps({'event': 'app_runtime_ready', 'app_id': id(self)}, sort_keys=True))
        self.geometry("1280x720"); self.minsize(980, 680)
        self.shell_controller = ShellController()
        self.active_content_type = self.shell_controller.destination
        self.active_tool = None
        self.mounted_view = ""
        self.image_workspace = None
        self.video_workspace = None
        self.pdf_workspace = None
        self.pptx_workspace = None
        self.pptx_workspace_state = PptxWorkspace(self)
        self._shell_executor = ShellTransitionExecutor()
        self.shell_trace = []
        self.tool_workspace = None
        self.content_buttons: dict[str, ctk.CTkButton] = {}
        self._initialize_image_services()
        self.image_workspace_owner = ImageWorkspace(
            self, self.image_state, scrollable_frame_cls=AutoHideScrollableFrame
        )
        self.video_workspace_owner = VideoWorkspace(self, self.video_state)
        self.pdf_workspace_owner = PdfWorkspace(self, self.pdf_state)
        # One shell-level registry for all peer content workspaces.  Format
        # specific state stays inside the mounted workspace; the shell only
        # resolves and mounts the selected peer.
        self._workspace_registry = {
            "image": self.image_workspace_owner,
            "video": self.video_workspace_owner,
            "pdf": self.pdf_workspace_owner,
            "pptx": self.pptx_workspace_state,
        }
        self._build_shell_ui()
        self.render_shell_state()

    def _build_shell_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, corner_radius=0); header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Nenolink AI Marker", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=14, sticky="w")
        self.language_var = ctk.StringVar(value=Translator.language_name(self.translator.language))
        self.language_menu = ctk.CTkOptionMenu(header, values=list(LANGUAGES), variable=self.language_var, command=self.change_image_language, width=150); self.language_menu.grid(row=0, column=1, padx=8)
        self.reset_button = ctk.CTkButton(header, text="Reset", command=self._reset_button_command, width=100); self.reset_button.grid(row=0, column=2, padx=8)
        self.guide_button = ctk.CTkButton(header, text="User Guide (PDF)", command=self.open_image_guide, width=170); self.guide_button.grid(row=0, column=3, padx=(8,20))

        navigation = ctk.CTkFrame(self, corner_radius=0); navigation.grid(row=1, column=0, sticky="ew")
        self._shell_group(navigation, "MEDIA", ("image", "video"), 0)
        self._shell_group(navigation, "DOCUMENTS", ("pdf", "pptx"), 1)
        self._shell_group(navigation, "TOOLS", ("badges", "inspect"), 2)

        self.content_host = ctk.CTkFrame(self); self.content_host.grid(row=2, column=0, padx=16, pady=(8,8), sticky="nsew")
        self.content_host.grid_columnconfigure(0, weight=1); self.content_host.grid_rowconfigure(0, weight=1)
        self.placeholder_label = ctk.CTkLabel(self.content_host, font=ctk.CTkFont(size=28, weight="bold")); self.placeholder_label.grid(row=0, column=0)
        self.status_var = ctk.StringVar()
        self.status_label = ctk.CTkLabel(self, textvariable=self.status_var, text_color="gray60", anchor="e")
        self.status_label.grid(row=3, column=0, padx=20, pady=(0,8), sticky="ew")

    def _shell_group(self, parent, title: str, destinations: tuple[str, ...], column: int) -> None:
        group = ctk.CTkFrame(parent, fg_color="transparent"); group.grid(row=0, column=column, padx=(20 if column == 0 else 8, 8), pady=7, sticky="w")
        ctk.CTkLabel(group, text=title, font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        buttons = ctk.CTkFrame(group, fg_color="transparent"); buttons.grid(row=1, column=0, pady=(1,0), sticky="w")
        for index, destination in enumerate(destinations):
            button = ctk.CTkButton(buttons, text=self._labels[destination], height=28, width=0,
                command=self._shell_button_command(destination))
            button.grid(row=0, column=index, padx=(0 if index == 0 else 4, 0))
            self.content_buttons[destination] = button

    def _shell_button_command(self, destination: str):
        """Command seam used by every constructed content/tool button."""
        return lambda: self.dispatch_shell_event(destination)

    def _reset_button_command(self):
        return self.reset_shell()

    def dispatch_shell_event(self, event: str) -> None:
        if event == "pptx": self.shell_trace.append("PPTX_BUTTON")
        if event in {"image", "video", "pdf", "pptx"}:
            if event == "pptx": self.shell_trace.append("PPTX_TRANSITION")
            self.request_content_transition(event)
            return
        source = self.shell_controller.active_content_type
        if event in {"badges", "inspect"} or event == "back":
            spec = shell_transition_spec(source, self.shell_controller.active_tool, event, self._format_has_active_work(source))
            self.last_shell_spec = spec
            try:
                self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
            except RuntimeError:
                return
            # Tool transitions must remount the requested overlay.  The
            # underlying content is preserved by the executor; only the tool
            # view is replaced.
            self.render_shell_state(remount=True)
            return
        # All global shell events, including reset, use the same table-driven
        # executor.  No legacy MarkerApp runtime field is consulted or cleared
        # here; workspace lifecycle methods own those values.
        if event == "reset":
            self.reset_shell()
            return
        spec = shell_transition_spec(source, self.shell_controller.active_tool, event, self._format_has_active_work(source))
        self.last_shell_spec = spec
        try:
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
        except RuntimeError:
            return
        self.render_shell_state(remount=False)

    def request_content_transition(self, destination: str) -> bool:
        """Apply the single external content transition algorithm."""
        if destination not in self._workspace_registry:
            raise ValueError(f"Unknown content destination: {destination}")
        source = self.shell_controller.active_content_type
        active = self._format_has_active_work(source)
        self.last_shell_spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, active)
        # A tool is an overlay, not a content state. Returning to the
        # underlying destination must close only the overlay and restore the
        # existing workspace without warning, clearing or remounting it.
        if self.shell_controller.active_tool is not None and destination == source:
            spec = shell_transition_spec(source, self.shell_controller.active_tool, "back", False)
            self.last_shell_spec = spec
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
            self.render_shell_state()
            return True
        if destination == source and self.shell_controller.active_tool is None:
            self.render_shell_state()
            return True
        if active and not self._confirm_format_switch(source, destination):
            self.last_shell_spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, True, "cancel")
            return False
        spec = shell_transition_spec(source, self.shell_controller.active_tool, destination, active, "continue" if active else None)
        self.last_shell_spec = spec
        try:
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
        except RuntimeError:
            return False
        self.render_shell_state(remount=False)
        return True

    def _confirm_format_switch(self, source: str, destination: str) -> bool:
        return messagebox.askokcancel(
            self.translator.text("navigation.switch_title"),
            self.translator.text("navigation.switch_message"),
        )

    def _clear_workspace_runtime(self, format_type: str) -> None:
        workspace = self._workspace_registry[format_type]
        workspace.clear_runtime_state()
        workspace.unmount()

    def reset_shell(self) -> None:
        source = self.shell_controller.active_content_type
        active = any(self._format_has_active_work(content) for content in DESTINATIONS)
        self.last_shell_spec = shell_transition_spec(source, self.shell_controller.active_tool, "reset", active)
        if active:
            workspace = getattr(self, "pptx_workspace_state", None) if source == "pptx" else None
            if not messagebox.askokcancel(
                self.translator.text("navigation.switch_title"),
                self.translator.text("navigation.switch_message"),
            ):
                if workspace is not None:
                    workspace.receipts.record({"layer": "pptx", "event": "GLOBAL_RESET_WARNING_SHOWN", "result": "cancel"})
                self.last_shell_spec = shell_transition_spec(source, self.shell_controller.active_tool, "reset", True, "cancel")
                return
            if workspace is not None:
                workspace.receipts.record({"layer": "pptx", "event": "GLOBAL_RESET_WARNING_SHOWN", "result": "continue"})
        spec = shell_transition_spec(source, self.shell_controller.active_tool, "reset", active, "continue" if active else None)
        self.last_shell_spec = spec
        try:
            self._shell_executor.execute(spec, _ShellRuntimeAdapter(self))
        except RuntimeError:
            return
        self.render_shell_state(remount=False)
        workspace=getattr(self,"pptx_workspace_state",None)
        if workspace is not None:
            workspace.receipts.record({"layer":"pptx","event":"GLOBAL_RESET_PPTX_CLEARED","result":"ok"})

    def _format_has_active_work(self, format_type: str) -> bool:
        if format_type == "image": return self.image_workspace_owner.has_active_work()
        if format_type == "video": return self.video_workspace_owner.has_active_work()
        if format_type == "pdf":
            workspace = getattr(self, "pdf_workspace_owner", None)
            return workspace.has_active_work() if workspace is not None else self.pdf_path is not None
        if format_type == "pptx":
            workspace = getattr(self, "pptx_workspace_state", None)
            if workspace is not None:
                return workspace.has_active_work()
            return False
        return False

    def render_shell_state(self, remount: bool = True) -> None:
        self._pdf_runtime_diagnostic("render_shell_state", {
            "active_content": getattr(self.__dict__.get("shell_controller"), "active_content_type", None),
            "active_tool": getattr(self.__dict__.get("shell_controller"), "active_tool", None),
            "buttons": {k: {"id": id(v), "selected": k == (getattr(self.__dict__.get("shell_controller"), "active_tool", None) or getattr(self.__dict__.get("shell_controller"), "active_content_type", None)), "mapped": bool(v.winfo_ismapped()) if v.winfo_exists() else False} for k, v in self.__dict__.get("content_buttons", {}).items()},
        })
        destination = self.shell_controller.active_content_type
        tool = self.shell_controller.active_tool
        self.active_content_type = destination
        self.active_tool = tool
        for key, button in self.content_buttons.items():
            selected = key == (tool or destination)
            button.configure(fg_color=("#2474ad", "#1f6aa5") if selected else ("#6b6b6b", "#454545"))
        if tool:
            for workspace in (self.__dict__.get("image_workspace"), self.__dict__.get("video_workspace"), self.__dict__.get("pdf_workspace"), self.__dict__.get("pptx_workspace")):
                if workspace is not None and hasattr(workspace, "winfo_exists") and workspace.winfo_exists(): workspace.grid_remove()
            if remount:
                self._mount_tool(tool)
            self.mounted_view = placeholder_for(tool)
            return
        self._unmount_tool()
        if destination in self._workspace_registry:
            trace = self.__dict__.get("shell_trace")
            if destination == "pptx" and trace is not None: trace.append("PPTX_REGISTRY")
            workspace = self._workspace_registry[destination]
            if remount:
                workspace.mount(self.content_host)
            workspace.project()
            self._project_active_status(destination)
            self.mounted_view = destination.upper()
        else:
            self._clear_content_host()
            self.mounted_view = placeholder_for(destination)
            self.placeholder_label = ctk.CTkLabel(self.content_host, text=self.mounted_view, font=ctk.CTkFont(size=28, weight="bold"))
            self.placeholder_label.grid(row=0, column=0)

    def _pdf_runtime_diagnostic(self, event: str, extra: dict | None = None) -> None:
        """Emit observational PDF widget identity data to the boot log."""
        pdf = self.__dict__.get("pdf_workspace_owner")
        state = getattr(pdf, "state", None)
        widgets = {}
        for name in ("pdf_workspace", "pdf_workspace_root", "pdf_process_button", "pdf_badge_menu", "pdf_badge_visual", "pdf_badge_image_label"):
            widget = self.__dict__.get(name)
            if widget is not None:
                try: widgets[name] = {"id": id(widget), "mapped": bool(widget.winfo_ismapped()), "exists": bool(widget.winfo_exists())}
                except Exception: widgets[name] = {"id": id(widget)}
        controller = self.__dict__.get("shell_controller")
        badge_var = self.__dict__.get("badge_display_var")
        menu = self.__dict__.get("pdf_badge_menu")
        photo = self.__dict__.get("pdf_badge_photo")
        payload = {"event": event, "active_content": getattr(controller, "active_content_type", None), "pdf_owner_id": id(pdf) if pdf else None, "state_badge": repr(getattr(state, "badge", None)), "badge_display": badge_var.get() if badge_var is not None else None, "selector_values": list(getattr(menu, "_values", []) or []) if menu is not None else [], "badge_asset": str(photo) if photo else None, "widgets": widgets}
        if extra: payload.update(extra)
        try: self._boot("PDF_DIAGNOSTIC " + json.dumps(payload, default=str, sort_keys=True))
        except Exception: pass

    def _project_active_status(self, destination: str) -> None:
        """Single shell-owned status projection sink.

        Workspace status is derived from its authoritative state after every
        lifecycle projection.  ``status_var`` is deliberately write-only UI
        output; no transition or workspace decision reads it.
        """
        workspace = self._workspace_registry.get(destination)
        state = getattr(workspace, "state", None)
        path = getattr(state, "path", None)
        files = getattr(state, "selected_files", ())
        if path is not None:
            text = f"{getattr(path, 'name', path)}"
        elif files:
            text = f"{getattr(files[0], 'name', files[0])}"
        else:
            text = ""
        status_var = self.__dict__.get("status_var")
        if status_var is not None:
            status_var.set(text)

    # --- Image module lifecycle -------------------------------------------------

    def _initialize_image_services(self) -> None:
        self.config_store = ConfigStore()
        saved = self.config_store.load()
        self._saved_settings = saved
        self.processor = ImageProcessor()
        self.preview_renderer = ImagePreviewRenderer(self.processor)
        # Clean v1.0.3 sessions start in English; locale changes are explicit
        # global events and are projected without rebuilding workspaces.
        self.translator = Translator(locale_directory(), "en")
        self.badge_sources = BadgeSourceManager(badge_directory())
        self.badges = self.badge_sources.repository(saved.badge_source, saved.custom_badge_folder)
        self.sources: list[Path] = []
        # Compatibility projection for legacy consumers; workspace state remains authoritative.
        self.media_sources = {"image": [], "video": []}
        self.image_state = ImageWorkspaceState()
        self.video_state = VideoWorkspaceState()
        self.pdf_state = PdfWorkspaceState()
        self.preview_photo = self.preview_image = self.badge_photo = self.single_badge_photo = None
        self.welcome_photo = self.welcome_image = None
        self.badge_display_to_file = {}
        self.badge_var = ctk.StringVar(value=saved.badge_name); self.badge_display_var = ctk.StringVar()
        self.badge_enabled_var = ctk.BooleanVar(value=True)
        self.badge_name_var = ctk.StringVar(); self.badge_description_var = ctk.StringVar()
        self.position_var = ctk.StringVar(value=saved.position); self.position_display_var = ctk.StringVar()
        self.size_var = ctk.IntVar(value=saved.size_percent); self.margin_var = ctk.IntVar(value=saved.margin); self.opacity_var = ctk.IntVar(value=saved.opacity)
        self.logo_enabled_var = ctk.BooleanVar(value=saved.logo_enabled); self.logo_path_var = ctk.StringVar(value=saved.logo_path)
        self.logo_filename_var = ctk.StringVar(value=Path(saved.logo_path).name if saved.logo_path else "—")
        self.logo_position_var = ctk.StringVar(value=saved.logo_position); self.logo_position_display_var = ctk.StringVar()
        self.logo_size_var = ctk.IntVar(value=saved.logo_size_percent); self.logo_margin_var = ctk.IntVar(value=saved.logo_margin); self.logo_opacity_var = ctk.IntVar(value=saved.logo_opacity)
        self.position_display_to_value = {"Top left": "top-left", "Top right": "top-right", "Bottom left": "bottom-left", "Bottom right": "bottom-right", "Center": "center"}
        self.position_display_var.set(next((k for k,v in self.position_display_to_value.items() if v == self.position_var.get()), "Bottom right"))
        self.badge_source_var = ctk.StringVar(value=saved.badge_source); self.custom_badge_var = ctk.StringVar(value=saved.custom_badge_folder)
        self.pdf_path = None; self.pdf_info = None; self.pdf_processor = PdfProcessor(); self.pdf_preview_renderer = PdfPreviewRenderer(self.processor); self.pdf_current_page = 0; self.pdf_preview_photo = None
        self.pdf_scope_mode = "all"; self.pdf_active_scope: tuple[int, ...] = (); self.pdf_scope_input = ""
        self.pdf_badge_enabled_var = ctk.BooleanVar(value=True)
        self.pptx_path = None; self.pptx_metrics = None; self.pptx_processor = PptxProcessor(); self.pptx_preview_renderer = PptxPreviewRenderer(self.processor); self.pptx_current_slide = 0; self.pptx_preview_photo = None
        self.pptx_scope_mode = "all"; self.pptx_active_scope: tuple[int, ...] = (); self.pptx_scope_input = ""
        self.pptx_state = PptxWorkspaceState()
        # PPTX visual settings are independent from the media/PDF controls.
        self.pptx_badge_position_var=ctk.StringVar(value=saved.position); self.pptx_badge_size_var=ctk.IntVar(value=saved.size_percent); self.pptx_badge_margin_var=ctk.IntVar(value=saved.margin); self.pptx_badge_opacity_var=ctk.IntVar(value=saved.opacity)
        self.pptx_logo_position_var=ctk.StringVar(value=saved.logo_position); self.pptx_logo_size_var=ctk.IntVar(value=saved.logo_size_percent); self.pptx_logo_margin_var=ctk.IntVar(value=saved.logo_margin); self.pptx_logo_opacity_var=ctk.IntVar(value=saved.logo_opacity)

    def _clear_content_host(self) -> None:
        for child in self.content_host.winfo_children():
            child.destroy()
        self.image_workspace = self.video_workspace = self.pdf_workspace = self.pptx_workspace = self.tool_workspace = None

    def _mount_pdf_workspace(self) -> None:
        """Temporary shell entry adapter for the PDF workspace boundary."""
        self.pdf_workspace_owner.mount(self.content_host)

    def _clear_pdf_runtime_compat(self) -> None:
        """B1 compatibility cleanup; removed once PDF state owns file events."""
        self.pdf_path = self.pdf_info = None
        self.pdf_current_page = 0
        self.pdf_preview_photo = None
        self.pdf_scope_mode = "all"
        self.pdf_active_scope = ()
        self.pdf_scope_input = ""

    def _mount_pptx_workspace(self) -> None:
        """Mount the single minimal authoritative PPTX workspace."""
        self.pptx_workspace_state.mount(self.content_host)
        self.pptx_workspace = self.pptx_workspace_state.root
        if not self.pptx_workspace_state.mounted or self.pptx_workspace is None:
            raise RuntimeError("PPTX workspace failed to mount")

    def pptx_visual_changed(self, *_args) -> None:
        self._sync_pptx_visual_state()
        if getattr(self, "pptx_badge_menu", None): self.pptx_badge_menu.configure(state="normal" if self.pptx_badge_enabled_var.get() else "disabled")
        self._update_logo_controls(); self._update_pptx_preview(); self._save()

    def _project_pptx_badge_visual(self) -> None:
        """Project the common selected badge into the PPTX controls."""
        badge_id = self.pptx_state.badge.badge_id or self.badge_var.get()
        badge = self.badges.find(badge_id) if badge_id else None
        if not badge:
            self.pptx_badge_photo = None
            if getattr(self, "pptx_badge_name_label", None): self.pptx_badge_name_label.configure(image=None, text="")
            return
        with Image.open(badge) as opened: image = opened.convert("RGBA")
        image.thumbnail((WORKSPACE_LAYOUT.badge_thumbnail_width, WORKSPACE_LAYOUT.badge_thumbnail_height), Image.Resampling.LANCZOS)
        self.pptx_badge_photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        display_name = self.badges.display_name(badge.name)
        self.badge_name_var.set(display_name); self.pptx_state.badge.badge_id = badge.name
        self.badge_display_var.set(display_name)
        if getattr(self, "pptx_badge_name_label", None): self.pptx_badge_name_label.configure(image=self.pptx_badge_photo, text=display_name)

    def _sync_pptx_visual_state(self) -> None:
        if not hasattr(self, "pptx_state"): return
        self.pptx_workspace_state.state_token_reached = True
        events = ((PptxEvent.BADGE_ENABLE, self.pptx_badge_enabled_var.get()), (PptxEvent.BADGE_SELECT, self.badge_var.get()), (PptxEvent.BADGE_POSITION, self.pptx_badge_position_var.get()), (PptxEvent.BADGE_SIZE, self.pptx_badge_size_var.get()), (PptxEvent.BADGE_MARGIN, self.pptx_badge_margin_var.get()), (PptxEvent.BADGE_OPACITY, self.pptx_badge_opacity_var.get()), (PptxEvent.LOGO_ENABLE, self.logo_enabled_var.get()), (PptxEvent.LOGO_CHOOSE, self._logo_path()), (PptxEvent.LOGO_POSITION, self.pptx_logo_position_var.get()), (PptxEvent.LOGO_SIZE, self.pptx_logo_size_var.get()), (PptxEvent.LOGO_MARGIN, self.pptx_logo_margin_var.get()), (PptxEvent.LOGO_OPACITY, self.pptx_logo_opacity_var.get()))
        for event, value in events:
            apply_pptx_visual_event(self.pptx_state, event, value)

    def _pptx_visual_projection_settings(self):
        """Build renderer/output settings from authoritative PPTX state."""
        self._sync_pptx_visual_state()
        return replace(self.settings(), position=self.pptx_state.badge.position,
                       size_percent=self.pptx_state.badge.size,
                       margin=self.pptx_state.badge.margin,
                       opacity=self.pptx_state.badge.opacity,
                       logo_enabled=self.pptx_state.logo.enabled,
                       logo_path=str(self.pptx_state.logo.path or ""),
                       logo_position=self.pptx_state.logo.position,
                       logo_size_percent=self.pptx_state.logo.size,
                       logo_margin=self.pptx_state.logo.margin,
                       logo_opacity=self.pptx_state.logo.opacity)

    def choose_pptx_phase2(self) -> None:
        selected = filedialog.askopenfilename(title="Choose PowerPoint", filetypes=[("PowerPoint (*.pptx)", "*.pptx")])
        if not selected: return
        path = Path(selected)
        try:
            metrics = self.pptx_processor.document_metrics(path)
            assessment = assess_document("pptx", metrics)
            if assessment.blocked:
                messagebox.showerror("PowerPoint", f"PowerPoint exceeds the hard limit of {assessment.profile.hard_bytes // (1024 * 1024)} MB or {assessment.profile.hard_items} slides."); return
            if assessment.requires_warning and not messagebox.askokcancel("PowerPoint", "This PowerPoint exceeds the recommended size. Continue?"): return
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("PowerPoint", f"Could not read PowerPoint: {error}"); return
        self.pptx_path, self.pptx_metrics = path, metrics
        self.pptx_current_slide = 1; self.pptx_preview_photo = None; self.pptx_scope_mode = "all"; self.pptx_active_scope = tuple(range(1, metrics.item_count + 1)); self.pptx_scope_input = ""
        self.pptx_state.path=path; self.pptx_state.slide_count=metrics.item_count; self.pptx_state.current_slide=1; self.pptx_state.scope_mode="all"; self.pptx_state.active_scope=self.pptx_active_scope; self.pptx_state.scope_input=""; self._sync_pptx_visual_state()
        self.pptx_file_label.configure(text=f"{path.name}\n{human_file_size(metrics.size_bytes)} · {metrics.item_count} slides")
        self.pptx_status_label.configure(text="PowerPoint loaded and ready.")
        self.status_var.set(f"PowerPoint loaded: {path.name}")
        self._update_pptx_preview()

    def _update_pptx_scope_controls(self) -> None:
        if not hasattr(self, "pptx_scope_entry"): return
        editable = self.pptx_scope_mode in {"selected", "range"}
        self.pptx_scope_entry.configure(state="normal" if editable else "disabled")
        self.pptx_scope_update.configure(state="normal" if editable else "disabled")

    def change_pptx_scope_mode(self, label: str) -> None:
        self.pptx_scope_mode = {"All": "all", "First": "first", "Selected": "selected", "Range": "range"}.get(label, "all")
        # Scope and visuals come only from the supplied workspace state.

    def update_pptx_scope(self) -> None:
        if not self.pptx_metrics or self.pptx_scope_mode not in {"selected", "range"}: return
        text = self.pptx_scope_entry.get().strip()
        try:
            values = []
            for part in (piece.strip() for piece in text.split(",") if piece.strip()):
                if self.pptx_scope_mode == "selected":
                    # Selected accepts both individual slide numbers and ranges
                    # (for example ``2,4-6,9``).  Keep parsing local to the
                    # explicit Update action so typing never changes scope.
                    bounds = part.split("-")
                    if len(bounds) == 1:
                        values.append(int(bounds[0].strip()))
                    elif len(bounds) == 2:
                        start, end = (int(value.strip()) for value in bounds)
                        if start > end: raise ValueError
                        values.extend(range(start, end + 1))
                    else:
                        raise ValueError
                else:
                    bounds = part.split("-")
                    if len(bounds) != 2: raise ValueError
                    start, end = (int(value.strip()) for value in bounds)
                    if start > end: raise ValueError
                    values.extend(range(start, end + 1))
            values = sorted(set(values))
            if not values or any(value < 1 or value > self.pptx_metrics.item_count for value in values): raise ValueError
            self.pptx_active_scope = tuple(values); self.pptx_scope_input = text; self.pptx_current_slide = values[0]; self.pptx_scope_message.configure(text=""); self.pptx_state.scope_mode=self.pptx_scope_mode; self.pptx_state.active_scope=self.pptx_active_scope; self.pptx_state.scope_input=text; self.pptx_state.current_slide=self.pptx_current_slide; self._update_pptx_preview()
        except (TypeError, ValueError):
            self.pptx_scope_message.configure(text="Invalid slide selection. The previous scope was preserved.")

    def _update_pptx_preview(self) -> None:
        # Compatibility entry point; the active PPTX route is workspace-owned.
        workspace = getattr(self, "pptx_workspace_state", None)
        if workspace is not None and hasattr(workspace, "_render_preview"):
            workspace._render_preview()
            return
        if not getattr(self, "pptx_preview_label", None): return
        self._sync_pptx_visual_state()
        if not self.pptx_path or not self.pptx_metrics:
            self.pptx_preview_photo = None; self.pptx_preview_label.configure(image=None, text="Choose a PowerPoint file to preview a slide."); self.pptx_slide_status.configure(text="—"); self.pptx_previous_button.configure(state="disabled"); self.pptx_next_button.configure(state="disabled"); return
        try:
            marked = self.pptx_current_slide in set(self.pptx_state.active_scope)
            badge = self.badges.find(self.pptx_state.badge.badge_id) if marked and self.pptx_state.badge.enabled else None
            logo = Path(self.pptx_state.logo.path) if marked and self.pptx_state.logo.enabled and self.pptx_state.logo.path else None
            result = self.pptx_preview_renderer.render(self.pptx_path, self.pptx_current_slide, badge, self._pptx_visual_projection_settings(), logo)
            self.pptx_current_slide = result.slide_number
            self.pptx_preview_photo = ctk.CTkImage(light_image=result.image, dark_image=result.image, size=result.image.size)
            self.pptx_preview_label.configure(image=self.pptx_preview_photo, text=""); self.pptx_preview_label.image = self.pptx_preview_photo
            self.pptx_slide_status.configure(text=f"{self.pptx_current_slide} / {self.pptx_metrics.item_count}")
            self.pptx_previous_button.configure(state="normal" if self.pptx_current_slide > 1 else "disabled")
            self.pptx_next_button.configure(state="normal" if self.pptx_current_slide < self.pptx_metrics.item_count else "disabled")
        except (OSError, ValueError, KeyError) as error:
            self.pptx_preview_photo = None; self.pptx_preview_label.configure(image=None, text=f"Could not render slide: {error}"); self.pptx_slide_status.configure(text=f"{self.pptx_current_slide} / {self.pptx_metrics.item_count}")

    def change_pptx_slide(self, delta: int) -> None:
        if not self.pptx_metrics: return
        self.pptx_current_slide = max(1, min(self.pptx_metrics.item_count, self.pptx_current_slide + delta)); self._update_pptx_preview()

    def _confirm_pdf_signature(self) -> bool:
        """Confirm the non-fatal signature warning before future PDF writes."""
        if not self.pdf_info or not getattr(self.pdf_info, "signed", False):
            return True
        return messagebox.askokcancel(
            self.translator.text("pdf.signature_title"),
            self.translator.text("pdf.signature_warning"),
        )

    def _confirm_pdf_limits_phase6(self) -> bool:
        if not self.pdf_info:
            return False
        assessment = assess_document("pdf", self.pdf_info.metrics)
        if assessment.blocked:
            messagebox.showerror(self.translator.text("document.limit_title"), self.translator.text("document.pdf_hard")); return False
        if assessment.requires_warning:
            return messagebox.askokcancel(self.translator.text("document.warning_title"), self.translator.text("document.pdf_warning"))
        return True

    def _mount_image_workspace(self) -> None:
        """Temporary shell entry adapter; ImageWorkspace owns lifecycle."""
        if getattr(self, "image_workspace_owner", None) is None:
            self.image_workspace_owner = ImageWorkspace(
                self, self.image_state, scrollable_frame_cls=AutoHideScrollableFrame
            )
        self.image_workspace_owner.mount(self.content_host)

    def _mount_video_workspace(self) -> None:
        """Temporary registry entry adapter; VideoWorkspace owns the view."""
        self.video_workspace_owner.mount(self.content_host)
    def change_video_mode(self, label):
        """Batch-only video preference adapter; VideoWorkspace owns runtime mode."""
        self.video_mode_var.set(self.video_mode_display_to_value.get(label, label)); self._save()

    def _video_changed(self, *_args):
        """Batch-only visual preference callback."""
        self._save()

    def _video_slider(self, parent, variable, start, end, row, label, command=None):
        output = ctk.CTkLabel(parent, text=label); output.grid(row=row, column=0, padx=14, pady=(4, 0), sticky="w")
        ctk.CTkSlider(parent, from_=start, to=end, number_of_steps=end-start, variable=variable, command=command or self._video_changed).grid(row=row+1, column=0, padx=14, pady=(1, 3), sticky="ew")
        return output

    def _mount_tool(self, tool: str) -> None:
        mounted_tool = getattr(self, "_mounted_tool_name", None)
        if self.tool_workspace is not None and self.tool_workspace.winfo_exists():
            if mounted_tool == tool:
                self.tool_workspace.grid()
                return
            self._unmount_tool()
        self.tool_workspace = ctk.CTkFrame(self.content_host); self.tool_workspace.grid(row=0, column=0, sticky="nsew"); self.tool_workspace.grid_columnconfigure(0, weight=1); self.tool_workspace.grid_rowconfigure(1, weight=1)
        ctk.CTkButton(self.tool_workspace, text=self.translator.text("button.back"), command=lambda: self.dispatch_shell_event("back"), width=110).grid(row=0, column=0, padx=16, pady=(10, 4), sticky="w")
        if tool == "badges": self._build_badges_tool()
        else: self._build_inspect_tool()
        self._mounted_tool_name = tool

    def _unmount_tool(self) -> None:
        if self.tool_workspace is not None and self.tool_workspace.winfo_exists(): self.tool_workspace.destroy()
        self.tool_workspace = None
        self._mounted_tool_name = None

    def _unmount_image_workspace(self) -> None:
        self.image_workspace_owner.clear_runtime_state()
        self.image_workspace_owner.unmount()
        self.sources = []
        self.image_state.preview_image = None
        self.preview_renderer.clear(); self.preview_photo = self.preview_image = None

    def _update_video_duration_visibility(self) -> None:
        if not getattr(self, "video_duration_entry", None): return
        visible = self.video_mode_var.get() in {"beginning", "end"}
        (self.video_duration_label.grid if visible else self.video_duration_label.grid_remove)(); (self.video_duration_entry.grid if visible else self.video_duration_entry.grid_remove)()

    def _build_badges_tool(self) -> None:
        panel = ctk.CTkFrame(self.tool_workspace); panel.grid(row=1, column=0, padx=16, pady=6, sticky="nsew"); panel.grid_columnconfigure(0, weight=1); panel.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(panel, text=self.translator.text("badge.source_label"), font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
        self.tool_badge_source_var = ctk.StringVar(value=self.badge_source_var.get()); ctk.CTkRadioButton(panel, text=self.translator.text("badge.source_standard"), variable=self.tool_badge_source_var, value="standard", command=self._tool_refresh_badges).grid(row=1, column=0, padx=16, pady=2, sticky="w"); ctk.CTkRadioButton(panel, text=self.translator.text("badge.source_custom"), variable=self.tool_badge_source_var, value="custom", command=self._tool_refresh_badges).grid(row=2, column=0, padx=16, pady=2, sticky="w")
        row = ctk.CTkFrame(panel, fg_color="transparent"); row.grid(row=3, column=0, padx=16, pady=4, sticky="ew"); row.grid_columnconfigure(0, weight=1); self.tool_badge_folder_var = ctk.StringVar(value=self.custom_badge_var.get()); ctk.CTkEntry(row, textvariable=self.tool_badge_folder_var).grid(row=0, column=0, sticky="ew"); ctk.CTkButton(row, text=self.translator.text("button.choose_badge_folder"), command=self._tool_choose_badge_folder, width=170).grid(row=0, column=1, padx=6); ctk.CTkButton(row, text=self.translator.text("badge.refresh"), command=self._tool_refresh_badges, width=100).grid(row=0, column=2)
        self.tool_badge_gallery = ctk.CTkScrollableFrame(panel); self.tool_badge_gallery.grid(row=4, column=0, padx=16, pady=6, sticky="nsew"); self._tool_refresh_badges()

    def _tool_choose_badge_folder(self) -> None:
        value = filedialog.askdirectory(title=self.translator.text("dialog.custom_badges"));
        if value: self.tool_badge_folder_var.set(value); self.tool_badge_source_var.set("custom"); self._tool_refresh_badges()

    def _tool_refresh_badges(self) -> None:
        if not getattr(self, "tool_badge_gallery", None): return
        self.badge_source_var.set(self.tool_badge_source_var.get()); self.custom_badge_var.set(self.tool_badge_folder_var.get())
        if self.tool_badge_source_var.get() == "standard":
            self.badges = self.badge_sources.standard_repository()
            names = [path.name for path in self.badges.display_badges()]
            displays = [self.badges.display_name(name) for name in names]
            self.badge_display_to_file = dict(zip(displays, names))
            self.badge_var.set(choose_badge_selection("standard", names, self.badge_var.get()))
            self.badge_display_var.set(self.badges.display_name(self.badge_var.get()))
        else:
            self.refresh_image_badges()
        for child in self.tool_badge_gallery.winfo_children(): child.destroy()
        self.tool_badge_photos = []
        for index, path in enumerate(self.badges.display_badges()):
            card = ctk.CTkFrame(self.tool_badge_gallery, fg_color="transparent", border_width=1)
            card.grid(row=index // 4, column=index % 4, padx=5, pady=5, sticky="nsew")
            try:
                with Image.open(path) as opened:
                    image = opened.convert("RGBA")
                image.thumbnail((150, 72), Image.Resampling.LANCZOS)
                photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                self.tool_badge_photos.append(photo)
                graphic = ctk.CTkLabel(card, image=photo, text="")
                graphic.pack(padx=6, pady=(6, 2))
            except (OSError, ValueError):
                graphic = ctk.CTkLabel(card, text=self.badges.display_name(path.name))
                graphic.pack(padx=6, pady=(6, 2))
            name_label = ctk.CTkLabel(card, text=self.badges.display_name(path.name), anchor="center")
            name_label.pack(padx=6, pady=(0, 6))
            select = lambda _event=None, name=path.name: self._tool_select_badge(name)
            for widget in (card, graphic, name_label):
                widget.bind("<Button-1>", select, add="+")

    def _tool_select_badge(self, name: str) -> None:
        self.badge_var.set(name)
        self.badge_display_var.set(self.badges.display_name(name))
        self.image_workspace_owner.badge_changed()
        self._tool_refresh_badges()

    def _build_inspect_tool(self) -> None:
        panel = ctk.CTkFrame(self.tool_workspace); panel.grid(row=1, column=0, padx=16, pady=6, sticky="nsew"); panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text=self.translator.text("inspect.title"), font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        ctk.CTkButton(panel, text=self.translator.text("inspect.choose"), command=self._tool_choose_inspection).grid(row=1, column=0, padx=12, pady=6, sticky="w")
        self.tool_inspect_result = ctk.CTkLabel(panel, text=self.translator.text("inspect.none"), justify="left", anchor="w"); self.tool_inspect_result.grid(row=2, column=0, padx=12, pady=8, sticky="ew")

    def _tool_choose_inspection(self) -> None:
        selected = filedialog.askopenfilename(title=self.translator.text("inspect.choose"), filetypes=[(self.translator.text("files.all"), "*.*")]);
        if not selected: return
        path = Path(selected)
        if path.suffix.lower() in {".pdf", ".pptx"}:
            self.tool_inspect_result.configure(text=self.translator.text("inspect.document_unsupported")); return
        try:
            result = inspect_file(path); label = result.ai_label or self.translator.text("inspect.not_available"); self.tool_inspect_result.configure(text=f"{path.name}\n{self.translator.text('inspect.status')} {self.translator.text('inspect.found') if result.found else self.translator.text('inspect.not_found')}\n{self.translator.text('inspect.ai_label')} {label}")
        except (OSError, ValueError) as error: self.tool_inspect_result.configure(text=self.translator.text("inspect.error_message", reason=error))

    # --- Image module -----------------------------------------------------------

    def _build_image_workspace(self) -> None:
        """Temporary entry adapter; ImageWorkspace owns widget construction."""
        if getattr(self, "image_workspace_owner", None) is None:
            self.image_workspace_owner = ImageWorkspace(
                self, self.image_state, scrollable_frame_cls=AutoHideScrollableFrame
            )
        self.image_workspace_owner._build_ui(self.image_workspace)
    def _image_slider(self, parent, variable, start, end, row):
        label = ctk.CTkLabel(parent); label.grid(row=row, column=0, padx=14, pady=(4, 0), sticky="w")
        ctk.CTkSlider(parent, from_=start, to=end, number_of_steps=end-start, variable=variable, command=self.changed).grid(row=row+1, column=0, padx=14, pady=(1, 3), sticky="ew")
        return label

    def _load_image_welcome(self) -> None:
        try:
            with Image.open(welcome_image_path()) as opened: self.welcome_image = opened.convert("RGBA")
        except OSError:
            self.welcome_illustration.configure(text="◇")

    def _resize_image_welcome(self, event=None) -> None:
        if self.welcome_image is None: return
        width = max(240, (event.width if event else self.welcome_frame.winfo_width()) - 48); height = max(135, (event.height if event else self.welcome_frame.winfo_height()) - 210)
        ratio = min(width / self.welcome_image.width, height / self.welcome_image.height); size = (max(1, int(self.welcome_image.width * ratio)), max(1, int(self.welcome_image.height * ratio)))
        self.welcome_photo = ctk.CTkImage(light_image=self.welcome_image, dark_image=self.welcome_image, size=size); self.welcome_illustration.configure(image=self.welcome_photo, text="")

    def _show_welcome(self) -> None:
        self.preview_label.grid_remove(); self.welcome_frame.grid(row=0, column=0, padx=18, pady=14, sticky="nsew"); self._resize_image_welcome()

    def _show_preview(self) -> None:
        self.welcome_frame.grid_remove(); self.preview_label.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

    def apply_image_translations(self) -> None:
        t = self.translator.text
        self.title(f"Nenolink AI Marker {__version__}")
        self.reset_button.configure(text=t("button.reset")); self.guide_button.configure(text=t("button.user_guide"))
        self.open_button.configure(text="1. " + t("button.open_media")); self.process_button.configure(text=t("button.process"))
        self.file_label.configure(text=t("files.none") if not self.sources else t("files.selected", count=len(self.sources), name=self.sources[0].name)); self.file_size_guidance.configure(text=t("files.size_guidance"))
        self.badge_enable.configure(text=t("pdf.add_badge"))
        self.position_display_to_value = {t("position.top_left"): "top-left", t("position.top_right"): "top-right", t("position.bottom_left"): "bottom-left", t("position.bottom_right"): "bottom-right", t("position.center"): "center"}
        self.position_menu.configure(values=list(self.position_display_to_value)); self.position_display_var.set(next((label for label, value in self.position_display_to_value.items() if value == self.position_var.get()), t("position.bottom_right")))
        self.logo_position_display_to_value = dict(self.position_display_to_value); self.logo_position_menu.configure(values=list(self.logo_position_display_to_value)); self.logo_position_display_var.set(next((label for label, value in self.logo_position_display_to_value.items() if value == self.logo_position_var.get()), t("position.top_left")))
        self.position_label.configure(text="3. " + t("position")); self._update_image_slider_labels()
        self.logo_heading.configure(text=t("logo.title")); self.logo_enable.configure(text=t("logo.enable")); self.logo_choose.configure(text=t("logo.choose")); self.logo_position_label.configure(text=t("logo.position")); self.logo_images_only.configure(text=t("logo.images_only")); self._update_logo_labels(); self._update_logo_controls()
        self.welcome_title.configure(text=t("welcome.title")); self.welcome_tagline.configure(text=t("welcome.tagline")); self.welcome_description1.configure(text=t("welcome.description1")); self.welcome_description2.configure(text=t("welcome.description2"))

    def change_image_language(self, name: str) -> None:
        # One application-wide locale owner; changing locale is not a content
        # transition and must not rebuild the active workspace.
        self.translator.set_language(LANGUAGES.get(name, "en")); self.apply_image_translations(); self.refresh_image_badges()
        t = self.translator.text
        for kind, key in (("image", "content.images"), ("video", "content.video"), ("pdf", "content.pdf"), ("pptx", "content.powerpoint")):
            button = getattr(self, "content_buttons", {}).get(kind)
            if button is not None: button.configure(text=t(key))
        if getattr(self, "reset_button", None) is not None: self.reset_button.configure(text=t("button.reset"))
        if getattr(self, "guide_button", None) is not None: self.guide_button.configure(text=t("button.user_guide"))
        workspace = getattr(self, "pptx_workspace_state", None)
        if self.active_content_type == "pptx" and workspace is not None:
            workspace.apply_language(self.translator)
        self._save()

    def open_image_guide(self) -> None:
        try: open_user_guide(localized_user_guide_path(self.translator.language))
        except (OSError, FileNotFoundError) as error: messagebox.showerror(self.translator.text("error.title"), self.translator.text("guide.missing", error=error))

    def _update_image_slider_labels(self) -> None:
        t = self.translator.text; self.size_label.configure(text="4. " + t("size.value", value=self.size_var.get())); self.margin_label.configure(text="5. " + t("margin.value", value=self.margin_var.get())); self.opacity_label.configure(text="6. " + t("opacity.value", value=self.opacity_var.get()))

    def changed(self, *_args) -> None:
        """Compatibility adapter; workspace events own Image/Video runtime state."""
        if self.active_content_type == "image":
            self.image_workspace_owner.visual_changed(*_args)
        elif self.active_content_type == "video":
            self.video_workspace_owner.change_visual(*_args)
        elif self.active_content_type == "pdf":
            self.pdf_workspace_owner.refresh_preview()
        elif self.active_content_type == "pptx":
            self._update_pptx_preview()
        self._save()

    def _update_logo_labels(self) -> None:
        t = self.translator.text; self.logo_size_label.configure(text=t("logo.size", value=self.logo_size_var.get())); self.logo_margin_label.configure(text=t("logo.margin", value=self.logo_margin_var.get())); self.logo_opacity_label.configure(text=t("logo.opacity", value=self.logo_opacity_var.get()))

    def _update_logo_controls(self) -> None:
        if not getattr(self, "logo_enable", None): return
        enabled = self.logo_enabled_var.get() and bool(self._logo_path())
        for widget in (self.logo_position_menu, self.logo_size_slider, self.logo_margin_slider, self.logo_opacity_slider): widget.configure(state="normal" if enabled else "disabled")
        self.logo_filename_var.set(Path(self.logo_path_var.get()).name if self.logo_path_var.get() else "—")

    def _validate_saved_logo(self) -> None:
        if self.logo_enabled_var.get() and not self._logo_path():
            self.logo_enabled_var.set(False); self.status_var.set(self.translator.text("logo.missing")); self._save()
        self._update_logo_controls()

    def _logo_path(self) -> Path | None:
        path = Path(self.logo_path_var.get()).expanduser() if self.logo_path_var.get() else None
        return path if path and path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS else None

    def refresh_image_badges(self) -> None:
        self.badges = self.badge_sources.repository(self.badge_source_var.get(), self.custom_badge_var.get())
        names = [path.name for path in self.badges.display_badges()]
        displays = [self.badges.display_name(name) for name in names]; self.badge_display_to_file = dict(zip(displays, names))
        if self.active_content_type == "image" and getattr(self, "image_workspace_owner", None) is not None:
            self.image_workspace_owner.project()
        self.badge_var.set(choose_badge_selection(self.badge_source_var.get(), names, self.badge_var.get()))
        self.badge_display_var.set(self.badges.display_name(self.badge_var.get()))

    def _project_image_visual_state(self) -> None:
        """Project authoritative Image visuals into legacy adapters."""
        state = self.image_state
        self.badge_var.set(state.badge.badge_id); self.badge_enabled_var.set(state.badge.enabled)
        self.position_var.set(state.badge.position); self.size_var.set(state.badge.size); self.margin_var.set(state.badge.margin); self.opacity_var.set(state.badge.opacity)
        self.logo_enabled_var.set(state.logo.enabled); self.logo_path_var.set(str(state.logo.path or "")); self.logo_position_var.set(state.logo.position); self.logo_size_var.set(state.logo.size); self.logo_margin_var.set(state.logo.margin); self.logo_opacity_var.set(state.logo.opacity)

    def settings(self) -> MarkerSettings:
        return replace(self._saved_settings, badge_name=self.badge_var.get(), position=self.position_var.get(), size_percent=self.size_var.get(), margin=self.margin_var.get(), opacity=self.opacity_var.get(), language=self.translator.language, badge_source=self.badge_source_var.get(), custom_badge_folder=self.custom_badge_var.get(), logo_enabled=self.logo_enabled_var.get(), logo_path=self.logo_path_var.get(), logo_position=self.logo_position_var.get(), logo_size_percent=self.logo_size_var.get(), logo_margin=self.logo_margin_var.get(), logo_opacity=self.logo_opacity_var.get()).validated()

    def _save(self) -> None:
        try:
            self._saved_settings = self.settings(); self.config_store.save(self._saved_settings)
        except OSError: pass

    def _save_image_settings(self) -> None:
        """Persist shared preferences without letting Video own shell state."""
        self._save()


def run():
    ctk.set_appearance_mode("system"); ctk.set_default_color_theme("blue"); MarkerApp().mainloop()
