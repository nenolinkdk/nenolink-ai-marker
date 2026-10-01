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
from .batch import BatchProcessor, BatchResult, FolderScan, VIDEO_EXTENSIONS, destination_root, find_ffmpeg, hidden_subprocess_kwargs, is_above_recommended_size, scan_folder
from .config import ConfigStore
from .document_processing import ItemSelection, ProcessingRequest, settings_for_documents
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
from .pdf_processor import PasswordProtectedPdfError, PdfInfo, PdfProcessor
from .pdf_preview import PdfPreviewRenderer
from .docx_processor import DocxInfo, DocxProcessor
from .docx_preview import DocxPreviewRenderer
from .shortcut import ShortcutError, create_desktop_shortcut
from .ui_state import DocumentPreviewState, DocumentScopeState, pptx_item_selection, show_welcome
from .update_check import UpdateCheckError, check_for_update, is_approved_update_url, should_check_automatically
from .shell_controller import DESTINATIONS, ShellController, placeholder_for


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
            self.after(800, self.open_images)
        if os.environ.get("NENOLINK_VERIFY_BADGE_FOLDER_DIALOG") == "1":
            self.after(800, self.browse_custom_badges)
        if os.environ.get("NENOLINK_VERIFY_REPORT"):
            self.after(800, self._write_hotfix_verification)
        elif getattr(sys,"frozen",False) and not self.shortcut_offer_shown:
            self.after(700,self._show_first_run_shortcut_offer)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(1,weight=1)
        header=ctk.CTkFrame(self,corner_radius=0); header.grid(row=0,column=0,sticky="ew"); header.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(header,text="Nenolink AI Marker",font=ctk.CTkFont(size=24,weight="bold")).grid(row=0,column=0,padx=20,pady=14)
        self.update_notification=ctk.CTkLabel(header,text="",text_color="#d62828",font=ctk.CTkFont(weight="bold"),cursor="hand2")
        self.update_notification.grid(row=0,column=1,padx=8); self.update_notification.bind("<Button-1>",self._open_update_page); self.update_notification.grid_remove()
        self.language_menu=ctk.CTkOptionMenu(header,variable=self.language_var,values=list(LANGUAGES),command=self.change_language,width=150); self.language_menu.grid(row=0,column=2,padx=8)
        self.reset_button=ctk.CTkButton(header,text="",command=self.reset_application,width=100); self.reset_button.grid(row=0,column=3,padx=8)
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
        self._single_ui(); self._batch_ui(); self._settings_ui(); self._inspect_ui()
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

    def _single_ui(self) -> None:
        tab=self.single_tab; tab.grid_columnconfigure(1,weight=1); tab.grid_rowconfigure(0,weight=1)
        left=AutoHideScrollableFrame(tab,width=310,fg_color=("gray86","gray17")); self.single_controls=left; left.grid(row=0,column=0,padx=(4,8),pady=4,sticky="nsew"); left.grid_columnconfigure(0,weight=1)
        self.open_button=ctk.CTkButton(left,text="",command=self.open_images); self.open_button.grid(row=0,column=0,padx=14,pady=(10,4),sticky="ew")
        self.file_label=ctk.CTkLabel(left,text="",wraplength=270,justify="left"); self.file_label.grid(row=1,column=0,padx=14,pady=3,sticky="w")
        self.file_size_guidance=ctk.CTkLabel(left,text="",wraplength=270,justify="left",text_color="gray60"); self.file_size_guidance.grid(row=2,column=0,padx=14,pady=(0,2),sticky="w")
        self.single_badge_label=ctk.CTkLabel(left,text="",font=ctk.CTkFont(weight="bold")); self.single_badge_label.grid(row=3,column=0,padx=14,pady=(4,1),sticky="w")
        self.badge_menu=ctk.CTkOptionMenu(left,variable=self.badge_display_var,values=["—"],command=self.select_badge_display); self.badge_menu.grid(row=4,column=0,padx=14,pady=2,sticky="ew")
        badge_preview=ctk.CTkFrame(left); badge_preview.grid(row=5,column=0,padx=14,pady=4,sticky="ew"); badge_preview.grid_columnconfigure(1,weight=1)
        self.single_badge_preview_label=ctk.CTkLabel(badge_preview,text="",width=90,height=44); self.single_badge_preview_label.grid(row=0,column=0,padx=5,pady=5)
        self.single_badge_name_label=ctk.CTkLabel(badge_preview,textvariable=self.badge_name_var,font=ctk.CTkFont(weight="bold"),anchor="w",wraplength=150); self.single_badge_name_label.grid(row=0,column=1,padx=(3,5),pady=5,sticky="ew")
        self.position_label=ctk.CTkLabel(left,text=""); self.position_label.grid(row=6,column=0,padx=16,pady=(8,2),sticky="w")
        self.position_menu=ctk.CTkOptionMenu(left,variable=self.position_display_var,values=["—"],command=self.change_position_display); self.position_menu.grid(row=7,column=0,padx=16,pady=4,sticky="ew")
        self.size_label=self._slider(left,self.size_var,1,100,8); self.margin_label=self._slider(left,self.margin_var,0,250,10); self.opacity_label=self._slider(left,self.opacity_var,0,100,12)
        self.logo_controls=ctk.CTkFrame(left); self.logo_controls.grid(row=14,column=0,padx=14,pady=(5,3),sticky="ew"); self.logo_controls.grid_columnconfigure(1,weight=1)
        self.logo_heading=ctk.CTkLabel(self.logo_controls,text="",font=ctk.CTkFont(weight="bold")); self.logo_heading.grid(row=0,column=0,columnspan=2,padx=8,pady=(6,2),sticky="w")
        self.logo_enable=ctk.CTkCheckBox(self.logo_controls,text="",variable=self.logo_enabled_var,command=self.logo_changed); self.logo_enable.grid(row=1,column=0,columnspan=2,padx=8,pady=3,sticky="w")
        self.logo_choose=ctk.CTkButton(self.logo_controls,text="",command=self.choose_logo,height=28); self.logo_choose.grid(row=2,column=0,padx=8,pady=3,sticky="w")
        self.logo_filename=ctk.CTkLabel(self.logo_controls,textvariable=self.logo_filename_var,anchor="w",wraplength=150); self.logo_filename.grid(row=2,column=1,padx=(2,8),pady=3,sticky="ew")
        self.logo_position_label=ctk.CTkLabel(self.logo_controls,text=""); self.logo_position_label.grid(row=3,column=0,padx=8,pady=2,sticky="w")
        self.logo_position_menu=ctk.CTkOptionMenu(self.logo_controls,variable=self.logo_position_display_var,values=["—"],command=self.change_logo_position,height=28); self.logo_position_menu.grid(row=3,column=1,padx=8,pady=2,sticky="ew")
        self.logo_size_label=ctk.CTkLabel(self.logo_controls,text=""); self.logo_size_label.grid(row=4,column=0,columnspan=2,padx=8,sticky="w")
        self.logo_size_slider=ctk.CTkSlider(self.logo_controls,from_=1,to=100,number_of_steps=99,variable=self.logo_size_var,command=self.logo_changed); self.logo_size_slider.grid(row=5,column=0,columnspan=2,padx=8,pady=(0,2),sticky="ew")
        self.logo_margin_label=ctk.CTkLabel(self.logo_controls,text=""); self.logo_margin_label.grid(row=6,column=0,columnspan=2,padx=8,sticky="w")
        self.logo_margin_slider=ctk.CTkSlider(self.logo_controls,from_=0,to=250,number_of_steps=250,variable=self.logo_margin_var,command=self.logo_changed); self.logo_margin_slider.grid(row=7,column=0,columnspan=2,padx=8,pady=(0,2),sticky="ew")
        self.logo_opacity_label=ctk.CTkLabel(self.logo_controls,text=""); self.logo_opacity_label.grid(row=8,column=0,columnspan=2,padx=8,sticky="w")
        self.logo_opacity_slider=ctk.CTkSlider(self.logo_controls,from_=0,to=100,number_of_steps=100,variable=self.logo_opacity_var,command=self.logo_changed); self.logo_opacity_slider.grid(row=9,column=0,columnspan=2,padx=8,pady=(0,3),sticky="ew")
        self.logo_images_only=ctk.CTkLabel(self.logo_controls,text="",text_color="gray60"); self.logo_images_only.grid(row=10,column=0,columnspan=2,padx=8,pady=(0,6),sticky="w")
        self.video_controls=ctk.CTkFrame(left,fg_color="transparent"); self.video_controls.grid(row=16,column=0,padx=14,pady=(2,0),sticky="ew"); self.video_controls.grid_columnconfigure(1,weight=1)
        self.video_settings_heading=ctk.CTkLabel(self.video_controls,text="",font=ctk.CTkFont(weight="bold")); self.video_settings_heading.grid(row=0,column=0,columnspan=3,pady=(2,0),sticky="w")
        self.video_mode_label=ctk.CTkLabel(self.video_controls,text=""); self.video_mode_label.grid(row=1,column=0,columnspan=3,sticky="w")
        self.video_mode_menu=ctk.CTkOptionMenu(self.video_controls,variable=self.video_mode_display_var,values=["—"],command=self.change_video_mode); self.video_mode_menu.grid(row=2,column=0,columnspan=3,pady=(1,3),sticky="ew")
        self.video_duration_label=ctk.CTkLabel(self.video_controls,text=""); self.video_duration_label.grid(row=3,column=0,pady=2,sticky="w")
        self.video_duration_entry=ctk.CTkEntry(self.video_controls,textvariable=self.video_duration_var,width=58); self.video_duration_entry.grid(row=3,column=1,padx=(8,4),pady=2,sticky="e"); self.video_duration_entry.bind("<FocusOut>",self.changed)
        self.video_seconds_label=ctk.CTkLabel(self.video_controls,text=""); self.video_seconds_label.grid(row=3,column=2,pady=2,sticky="w")
        self.process_button=ctk.CTkButton(left,text="",command=self.save_images); self.process_button.grid(row=17,column=0,padx=14,pady=(6,10),sticky="ew")
        self.video_controls.grid_remove()
        right=ctk.CTkFrame(tab); right.grid(row=0,column=1,padx=(8,4),pady=4,sticky="nsew"); right.grid_columnconfigure(0,weight=1); right.grid_rowconfigure(0,weight=1)
        self.preview_label=ctk.CTkLabel(right,text="")
        self.welcome_frame=ctk.CTkFrame(right,fg_color="transparent"); self.welcome_frame.grid(row=0,column=0,padx=18,pady=14,sticky="nsew"); self.welcome_frame.grid_columnconfigure(0,weight=1); self.welcome_frame.grid_rowconfigure(4,weight=1)
        self.welcome_title=ctk.CTkLabel(self.welcome_frame,text="",font=ctk.CTkFont(size=28,weight="bold")); self.welcome_title.grid(row=0,column=0,padx=12,pady=(12,4))
        self.welcome_tagline=ctk.CTkLabel(self.welcome_frame,text="",font=ctk.CTkFont(size=18,weight="bold"),text_color=("#2469a0","#65b6ef")); self.welcome_tagline.grid(row=1,column=0,padx=12,pady=(0,10))
        self.welcome_description1=ctk.CTkLabel(self.welcome_frame,text="",wraplength=720,justify="center"); self.welcome_description1.grid(row=2,column=0,padx=18,pady=2)
        self.welcome_description2=ctk.CTkLabel(self.welcome_frame,text="",wraplength=720,justify="center"); self.welcome_description2.grid(row=3,column=0,padx=18,pady=(2,10))
        self.welcome_illustration=ctk.CTkLabel(self.welcome_frame,text="",anchor="center"); self.welcome_illustration.grid(row=4,column=0,padx=12,pady=(4,12),sticky="nsew")
        self._load_welcome_image(self._boot)
        self.welcome_frame.bind("<Configure>",self._resize_welcome)

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
        self.single_badge_label.configure(text="2. "+t("badge")); self.badge_source_heading.configure(text=t("badge.source_label")); self.standard_badge_radio.configure(text=t("badge.source_standard")); self.custom_badge_radio.configure(text=t("badge.source_custom")); self.custom_folder_label.configure(text=t("badge.custom_path")+":"); self.custom_entry.configure(placeholder_text=t("badge.custom_path"))
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

    def change_language(self,name): self.translator.set_language(LANGUAGES.get(name,"en")); self.apply_translations(); self._save()
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
        """Authoritative transition controller for the four content states."""
        try:
            if destination not in {"image","video","pdf","pptx"}:return False
            source=self.active_content_type
            if self.active_tool is None and source==destination:return True
            if self.active_tool is None and self._format_has_active_work(source):
                if not self._confirm_format_switch(source,destination):
                    self._render_authoritative_state(); return False
            if self.active_tool is None:self.destroy_runtime_context(source)
            self.active_tool=None
            self.active_content_type=destination
            self.initialize_clean_context(destination)
            self._render_authoritative_state()
            return True
        finally:MarkerApp._ensure_global_controls_enabled(self)

    def _destroy_context_widgets(self, content_type):
        """Remove every format-owned widget before another format can render."""
        if not hasattr(self,"single_tab"):
            return
        tabs={"image":(self.single_tab,self.batch_tab), "video":(self.single_tab,self.batch_tab),
              "pdf":(self.pdf_tab,), "pptx":(self.pptx_tab,)}
        for tab in tabs.get(content_type, ()):
            for child in tab.winfo_children(): child.destroy()
        if content_type in {"image","video"}:
            for name in ("single_controls","preview_label","welcome_frame","video_controls","open_button","badge_menu"):
                setattr(self,name,None)
        elif content_type in {"pdf","pptx"}:
            setattr(self, f"{content_type}_context_widgets", None)
            for name in self._document_widget_names: setattr(self,name,None)

    def _create_context_widgets(self, content_type):
        if not hasattr(self,"single_tab"):
            return
        if content_type in {"image","video"}:
            self._single_ui(); self._batch_ui()
        else:
            tab=self.pdf_tab if content_type=="pdf" else self.pptx_tab
            context=self._document_context_ui(tab)
            setattr(self, f"{content_type}_context_widgets", context)
            self._bind_document_context_widgets(content_type)

    def destroy_runtime_context(self,content_type):
        self.reset_format_context(content_type)
        MarkerApp._destroy_context_widgets(self,content_type)
        if self.active_runtime_context_type==content_type:self.active_runtime_context_type=None

    def initialize_clean_context(self,content_type):
        # A destination is recreated, rather than resurrected from a hidden tab.
        MarkerApp._destroy_context_widgets(self,content_type)
        self.reset_format_context(content_type)
        self.active_runtime_context_type=content_type
        MarkerApp._create_context_widgets(self,content_type)

    def _render_authoritative_state(self):
        """Project authoritative state into widgets; widgets never own it."""
        if self.active_tool:
            MarkerApp._set_format_navigation(self,None); self.tools_navigation.set(self.translator.text("tab.badges" if self.active_tool=="badges" else "tab.inspect")); self._configure_secondary_navigation(self.active_tool)
            if self.active_tool=="inspect":self._render_inspection()
            return
        self.tools_navigation.set(""); MarkerApp._set_format_navigation(self,self.active_content_type)
        self._configure_secondary_navigation("single")
        if self.active_content_type in {"image","video"}:
            if self.video_controls is not None:
                self.video_controls.grid() if self.active_content_type=="video" else self.video_controls.grid_remove()
            self._update_logo_controls(); self.update_preview()
        elif self.active_content_type == "pdf":
            self._mount_pdf_workspace()
        else:
            self._clear_content_host(); self.placeholder_label = ctk.CTkLabel(self.content_host, text="PPTX TEST", font=ctk.CTkFont(size=28, weight="bold")); self.placeholder_label.grid(row=0, column=0)
        self.visible_workspace_type=self.active_content_type

    def _format_has_active_work(self,format_type):
        if format_type in {"image","video"}:return bool(self.sources or self.media_sources.get(format_type) or self.scan)
        if format_type=="pdf":return self.pdf_path is not None
        if format_type=="pptx":return self.pptx_path is not None
        return False

    def _set_format_navigation(self,format_type):
        for kind, button in getattr(self,"content_buttons",{}).items():
            selected=kind==format_type
            button.configure(fg_color=("#2474ad","#1f6aa5") if selected else ("#6b6b6b","#454545"))

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
        if self.active_tool is None and self._format_has_active_work(self.active_content_type) and not self._confirm_format_switch(self.active_content_type,target):
            self._render_authoritative_state(); return False
        if self.active_tool is None:self.destroy_runtime_context(self.active_content_type)
        self.active_tool=target
        if target=="inspect":self.inspection_path=None; self.inspection_result=None; self.inspection_error=""; self.inspection_unsupported=False
        self._render_authoritative_state(); return True

    def reset_format_context(self,format_type,preserve_visual_settings=True,*,keep_file=False,scope="all"):
        """Reset file/navigation state without touching shared badge/logo styling."""
        if format_type in {"image","video"}:
            self.media_sources[format_type]=[]
            if self.active_content_type==format_type:self.sources=[]
            self.preview_photo=None; self.preview_image=None
            renderer=getattr(self,"preview_renderer",None)
            if renderer is not None:renderer.clear()
            if hasattr(self,"status_var"):self.status_var.set("")
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
        else:self.process_pptx()

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
            result=self.pptx_preview_renderer.render(self.pptx_path,self.pptx_preview_state.current,badge,preview_settings,logo)
            self.pptx_preview_state.current=result.slide_number; self.pptx_preview_photo=ctk.CTkImage(result.image,size=result.image.size); self.pptx_preview_label.configure(image=self.pptx_preview_photo,text=""); self.pptx_slide_status.configure(text=t("pptx.slide_status",current=result.slide_number,count=result.slide_count))
            self.pptx_previous_button.configure(state="normal" if self.pptx_preview_state.can_previous else "disabled"); self.pptx_next_button.configure(state="normal" if self.pptx_preview_state.can_next else "disabled")
        except (OSError,ValueError,KeyError):
            self.pptx_preview_photo=None; self.pptx_preview_label.configure(image=None,text=t("pptx.preview_unavailable")); self.pptx_slide_status.configure(text="")

    def process_pptx(self):
        if not self.pptx_path or not self.pptx_path.is_file():messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("pptx.choose_first")); return
        try:self.pptx_metrics=self.pptx_processor.document_metrics(self.pptx_path); self._set_pptx_file_summary()
        except (OSError,ValueError,KeyError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("pptx.error",error=error)); return
        if not self._confirm_pptx_limits():return
        badge=self.badges.find(self.badge_var.get())
        if not badge:messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("badge.none")); return
        suggested=self.pptx_path.with_name(f"{self.pptx_path.stem}_ai.pptx")
        selected=filedialog.asksaveasfilename(title=self.translator.text("pptx.save_as"),initialdir=str(self.pptx_path.parent),initialfile=suggested.name,defaultextension=".pptx",filetypes=[("PowerPoint (*.pptx)","*.pptx"),(self.translator.text("files.all"),"*.*")],confirmoverwrite=True)
        if not selected:return
        try:
            destination=Path(selected)
            if destination.suffix.lower() != ".pptx":raise ValueError(self.translator.text("pptx.extension_error"))
            selection=ItemSelection("selected",self.document_scope_states["pptx"].active_scope)
            display_name=self.badge_name_var.get() or self.badges.display_name(badge.name); language=LANGUAGES.get(self.pptx_language_var.get(),"en")
            disclosure,logo=settings_for_documents(self.settings(),label=display_name,disclosure_language=language)
            result=self.pptx_processor.process(ProcessingRequest(self.pptx_path,destination,disclosure,badge_path=badge,logo=logo),selection)
        except (OSError,ValueError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("pptx.error",error=error)); return
        text=self.translator.text("pptx.saved",name=result.destination.name,count=len(result.selected_slides)); self.status_var.set(text); messagebox.showinfo(self.translator.text("complete.title"),text)
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
            self.active_tool=None; self.initialize_clean_context(self.active_content_type)
        self._render_authoritative_state()
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
    def reset_application(self):
        """Destroy all runtime state and recreate the canonical fresh start."""
        custom_folder=self.custom_badge_var.get()
        MarkerApp._destroy_all_runtime_contexts(self)
        MarkerApp._create_fresh_runtime_state(self)
        self.custom_badge_var.set(custom_folder)
        self.refresh_badges(False); self.apply_translations(); self._render_authoritative_state()
        self.status_var.set(self.translator.text("status.reset")); self._save()
        MarkerApp._ensure_global_controls_enabled(self)

    def _destroy_all_runtime_contexts(self):
        dialog=getattr(self,"_format_switch_dialog",None)
        if dialog is not None:
            try:dialog.destroy()
            except (TclError,AttributeError):pass
        self._format_switch_dialog=None
        after_id=getattr(self,"_reset_after_id",None)
        if after_id:
            try:self.after_cancel(after_id)
            except (TclError,AttributeError):pass
        self._reset_after_id=None; self.cancel_event.clear()
        # Reset is a hard lifecycle boundary, including hidden format trees.
        for content_type in ("image","video","pdf","pptx"):
            MarkerApp._destroy_context_widgets(self,content_type)
        for renderer_name in ("preview_renderer","pdf_preview_renderer","pptx_preview_renderer"):
            renderer=getattr(self,renderer_name,None)
            if renderer is not None:
                try:renderer.clear()
                except (AttributeError,TclError,RuntimeError):pass

    def _create_fresh_runtime_state(self):
        """Create state equivalent to a new application process."""
        self.active_tool=None; self.active_content_type="image"; self.active_runtime_context_type="image"; self.visible_workspace_type="image"; self.active_media_mode="single"; self.media_sources={"image":[],"video":[]}; self.sources=[]; self.scan=None
        self.inspection_path=None; self.inspection_result=None; self.inspection_error=""; self.inspection_unsupported=False
        self.pdf_path=None; self.pdf_info=None; self.pptx_path=None; self.pptx_metrics=None
        self._pdf_warning_approved=None; self._pdf_signature_approved=None; self._pptx_warning_approved=None
        self.pdf_preview_state.clear(); self.pptx_preview_state.clear(); self.pptx_preview_photo=None
        self.preview_photo=None; self.preview_image=None
        for state in self.document_scope_states.values():state.reset()
        defaults=MarkerSettings()
        for name,value in (("badge_source_var","standard"),("badge_var",defaults.badge_name),("position_var",defaults.position),("size_var",defaults.size_percent),("margin_var",defaults.margin),("opacity_var",defaults.opacity),("batch_suffix_var",defaults.batch_filename_suffix),("video_mode_var",defaults.video_mode),("video_duration_var",defaults.video_duration),("logo_enabled_var",False),("logo_position_var",defaults.logo_position),("logo_size_var",defaults.logo_size_percent),("logo_margin_var",defaults.logo_margin),("logo_opacity_var",defaults.logo_opacity),("pdf_badge_enabled_var",True),("pptx_selection_mode_var","all"),("pptx_selected_var",""),("pptx_range_var","1-2")):
            variable=getattr(self,name,None)
            if variable is not None:
                try:variable.set(value)
                except (TclError,AttributeError):pass
        for name,value in (("status_var",""),("scan_summary_var",""),("progress_text_var",""),("pdf_file_var",""),("pptx_file_var","")):
            variable=getattr(self,name,None)
            if variable is not None:
                try:variable.set(value)
                except (TclError,AttributeError):pass
        progress=getattr(self,"progress",None)
        if progress is not None:
            try:progress.set(0)
            except (TclError,AttributeError):pass
        MarkerApp._create_context_widgets(self,"image")
        self._render_authoritative_state()
        try:self.render_start_view()
        except (TclError,AttributeError):pass

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
    def changed(self,*_):
        try:self.video_duration_var.set(max(1,int(self.video_duration_var.get())))
        except (ValueError,TypeError):self.video_duration_var.set(5)
        t=self.translator.text
        if getattr(self,"size_label",None):
            self.size_label.configure(text="4. "+t("size.value",value=self.size_var.get())); self.margin_label.configure(text="5. "+t("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text="6. "+t("opacity.value",value=self.opacity_var.get()))
        if getattr(self,"pptx_size_label",None):
            self.pptx_size_label.configure(text=t("size.value",value=self.size_var.get())); self.pptx_margin_label.configure(text=t("margin.value",value=self.margin_var.get())); self.pptx_opacity_label.configure(text=t("opacity.value",value=self.opacity_var.get())); self.pptx_logo_size_label.configure(text=t("logo.size",value=self.logo_size_var.get())); self.pptx_logo_margin_label.configure(text=t("logo.margin",value=self.logo_margin_var.get())); self.pptx_logo_opacity_label.configure(text=t("logo.opacity",value=self.logo_opacity_var.get()))
        self._update_logo_labels(); self._update_batch_logo_value()
        if self.active_content_type in {"image","video"}:self.update_preview()
        elif self.active_content_type in {"pdf","pptx"}:self.update_pptx_preview()
        self._save()
    def change_video_mode(self,label):
        self.video_mode_var.set(self.video_mode_display_to_value[label]); self._update_video_duration_controls(); self.changed()
    def _update_video_duration_controls(self):
        t=self.translator.text; self.video_duration_label.configure(text=t("video.duration")); self.video_seconds_label.configure(text=t("video.seconds")); self.batch_video_duration_label.configure(text=f"{t('video.duration')} ({t('video.seconds')})")
        visible=self.video_mode_var.get() in {"beginning","end"}
        for widget in (self.video_duration_label,self.video_duration_entry,self.video_seconds_label):
            widget.grid() if visible else widget.grid_remove()
        self.batch_video_duration_label.grid() if visible else self.batch_video_duration_label.grid_remove()
        self.batch_video_duration_entry.grid() if visible else self.batch_video_duration_entry.grid_remove()
        self.single_controls.after_idle(self.single_controls.update_scrollbar_visibility)
    def change_position_display(self,label): self.position_var.set(self.position_display_to_value[label]); self.changed()
    def change_logo_position(self,label): self.logo_position_var.set(self.logo_position_display_to_value[label]); self.logo_changed()
    def _logo_path(self):
        path=Path(self.logo_path_var.get()).expanduser() if self.logo_path_var.get() else None
        return path if path and path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS else None
    def _validate_saved_logo(self):
        if self.logo_enabled_var.get() and not self._logo_path():
            self.logo_enabled_var.set(False); self.status_var.set(self.translator.text("logo.missing")); self._save()
        self._update_logo_controls(); self._update_batch_logo_value()
    def choose_logo(self):
        selected=filedialog.askopenfilename(title=self.translator.text("logo.choose"),filetypes=[(self.translator.text("logo.supported"),"*.png *.jpg *.jpeg *.webp"),(self.translator.text("files.all"),"*.*")])
        if not selected:return
        path=Path(selected)
        try:
            with Image.open(path) as opened:opened.verify()
        except (OSError,Image.UnidentifiedImageError):
            messagebox.showerror(self.translator.text("error.title"),self.translator.text("logo.invalid")); return
        self.logo_path_var.set(str(path)); self.logo_enabled_var.set(True); self.logo_changed()
    def logo_changed(self,*_):
        if self.logo_enabled_var.get() and not self._logo_path():
            self.logo_enabled_var.set(False); self.status_var.set(self.translator.text("logo.missing"))
        self._update_logo_controls(); self._update_pptx_logo_controls(); self.changed()
    def _update_logo_labels(self):
        t=self.translator.text; self.logo_size_label.configure(text=t("logo.size",value=self.logo_size_var.get())); self.logo_margin_label.configure(text=t("logo.margin",value=self.logo_margin_var.get())); self.logo_opacity_label.configure(text=t("logo.opacity",value=self.logo_opacity_var.get()))
    def _update_logo_controls(self):
        if not getattr(self,"logo_enable",None):return
        is_video=self.active_content_type=="video" or bool(self.sources and self.sources[0].suffix.lower() in VIDEO_EXTENSIONS)
        enabled=self.logo_enabled_var.get() and not is_video
        state="normal" if enabled else "disabled"
        for widget in (self.logo_position_menu,self.logo_size_slider,self.logo_margin_slider,self.logo_opacity_slider):widget.configure(state=state)
        self.logo_enable.configure(state="disabled" if is_video else "normal")
        self.logo_choose.configure(state="disabled" if is_video else "normal")
        self.logo_filename_var.set(Path(self.logo_path_var.get()).name if self.logo_path_var.get() else "—")
    def _update_batch_logo_value(self):
        if not hasattr(self,"batch_logo_value"):return
        path=self._logo_path(); text=path.name if self.logo_enabled_var.get() and path else self.translator.text("logo.disabled")
        self.batch_logo_value.configure(text=f"{text} · {self.translator.text('logo.images_only')}")
    def change_badge_source(self): self._show_badge_source_controls(); self.refresh_badges(); self._save()
    def _show_badge_source_controls(self):
        if self.badge_source_var.get()=="custom":self.custom_controls.grid()
        else:self.custom_controls.grid_remove()
    def select_badge(self):
        self.badge_display_var.set(self.badges.display_name(self.badge_var.get()))
        self.update_badge_preview(); self.update_gallery_selection()
        if self.active_content_type in {"image","video"}:self.update_preview()
        elif self.active_content_type in {"pdf","pptx"}:self.update_pptx_preview()
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

    def open_images(self):
        video=self.active_content_type=="video"; extensions=VIDEO_EXTENSIONS if video else SUPPORTED_EXTENSIONS; pattern=" ".join(f"*{extension}" for extension in sorted(extensions))
        selected=filedialog.askopenfilenames(title=self.translator.text("dialog.open_media"),filetypes=[(self.translator.text("files.supported_media"),pattern),(self.translator.text("files.all"),"*.*")])
        if selected:
            candidates=[Path(p) for p in selected if Path(p).suffix.lower() in extensions]
            if any(is_above_recommended_size(p) for p in candidates) and not messagebox.askokcancel(self.translator.text("warning.large_title"),self.translator.text("warning.large_file")):return
            self.reset_format_context(self.active_content_type)
            self.sources=candidates; self.media_sources[self.active_content_type]=list(candidates); self.file_label.configure(text=self.translator.text("files.selected",count=len(self.sources),name=self.sources[0].name) if self.sources else self.translator.text("files.none_supported")); self.process_button.configure(text=self.translator.text("button.process_video") if video else self.translator.text("button.process")); self.video_controls.grid() if video else self.video_controls.grid_remove(); self._update_logo_controls(); self.update_preview()

    def update_preview(self):
        badge=self.badges.find(self.badge_var.get())
        if show_welcome(self.sources):self.preview_photo=None; self.preview_image=None; self._show_welcome(); return
        self._show_preview()
        if not badge:self.preview_label.configure(image=None,text=self.translator.text("badge.none")); return
        if self.sources[0].suffix.lower() in VIDEO_EXTENSIONS:
            self.preview_photo=None; self.preview_image=None; self.preview_label.configure(image=None,text=self.translator.text("preview.video_selected",name=self.sources[0].name)); self.status_var.set(self.translator.text("preview.video_selected",name=self.sources[0].name)); return
        try:
            settings=self.settings(); logo=self._logo_path() if settings.logo_enabled else None
            image=self.preview_renderer.render(self.sources[0],badge,settings,logo); self.preview_image=image.copy(); self.preview_photo=ctk.CTkImage(light_image=self.preview_image,dark_image=self.preview_image,size=self.preview_image.size); self.preview_label.configure(image=self.preview_photo,text=""); self.preview_label.image=self.preview_photo; self.status_var.set(self.translator.text("preview.showing",name=self.sources[0].name))
        except (OSError,ValueError) as error:self.status_var.set(self.translator.text("error.preview",error=error))

    def clear_images(self):
        self.sources=[]
        if self.active_content_type in self.media_sources:self.media_sources[self.active_content_type]=[]
        self.preview_renderer.clear(); self.file_label.configure(text=self.translator.text("files.none")); self._update_logo_controls(); self.update_preview()

    def save_images(self):
        badge=self.badges.find(self.badge_var.get())
        if not self.sources or not badge:messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("warning.nothing_to_save")); return
        saved=[]; failures=[]; metadata_warnings=[]
        display_var=getattr(self,"badge_name_var",None)
        metadata=marker_metadata(self.badge_var.get(),display_var.get() if display_var else None)
        for source in self.sources:
            suggested=source.with_name(f"{source.stem}_ai{source.suffix}")
            is_video=source.suffix.lower() in VIDEO_EXTENSIONS
            formats=" ".join(f"*{extension}" for extension in sorted(VIDEO_EXTENSIONS)) if is_video else f"*{source.suffix}"
            selected=filedialog.asksaveasfilename(title=self.translator.text("dialog.save_video_as" if is_video else "dialog.save_as"),initialdir=str(source.parent),initialfile=suggested.name,defaultextension=source.suffix,filetypes=[(self.translator.text("files.supported_videos" if is_video else "files.supported"),formats),(self.translator.text("files.all"),"*.*")],confirmoverwrite=True)
            if not selected:continue
            try:
                target=Path(selected)
                if is_video:
                    if target.suffix.lower() not in VIDEO_EXTENSIONS:raise ValueError(self.translator.text("error.unsupported_video_output",extension=target.suffix or "—"))
                    if not find_ffmpeg():raise ValueError(self.translator.text("error.video_component_missing"))
                    metadata_written=self.batch_processor.process_video(source,badge,target,self.settings(),metadata)
                else:
                    settings=self.settings(); logo=self._logo_path() if getattr(settings,"logo_enabled",False) else None
                    metadata_written=self.processor.save(self.processor.process(source,badge,settings,logo),target,metadata)
                saved.append(target)
                if not metadata_written:metadata_warnings.append(source.name)
            except (OSError,ValueError) as error:failures.append(f"{source.name}: {error}")
        only_video=bool(saved) and all(path.suffix.lower() in VIDEO_EXTENSIONS for path in self.sources)
        summary=self.translator.text("video.saved_name",name=saved[-1].name) if only_video and not failures else self.translator.text("process.summary",saved=len(saved),total=len(self.sources)); self.status_var.set(summary)
        warning=("\n\n"+self.translator.text("warning.metadata_failed")) if metadata_warnings else ""
        (messagebox.showerror if failures else messagebox.showinfo)(self.translator.text("error.completed") if failures else self.translator.text("complete.title"),summary+("\n\n"+"\n".join(failures[:8]) if failures else "")+warning)

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

    def _write_hotfix_verification(self):
        """Exercise the real packaged widgets for release verification only."""
        report_path=Path(os.environ["NENOLINK_VERIFY_REPORT"])
        progress_path=report_path.with_suffix(".progress")
        def checkpoint(stage):progress_path.write_text(stage,encoding="utf-8")
        checkpoint("startup")
        release_regressions={"inspect_then_image":False,"selected_image_inspect_back":False,"inspect_reset_then_image":False,"selected_video_inspect_back":False}
        initial_badge_settings={"language":self.translator.language,"source":self.badge_source_var.get(),"folder":self.custom_badge_var.get(),"selection":self.badge_var.get(),"batch_suffix":self.batch_suffix_var.get(),"video_mode":self.video_mode_var.get(),"video_duration":self.video_duration_var.get(),"logo_enabled":self.logo_enabled_var.get(),"logo_path":self.logo_path_var.get(),"logo_position":self.logo_position_var.get(),"logo_size":self.logo_size_var.get(),"logo_margin":self.logo_margin_var.get(),"logo_opacity":self.logo_opacity_var.get(),"status":self.status_var.get(),"count":len(self.badges.display_badges()),"custom_controls_visible":self.custom_controls.winfo_manager()=="grid"}
        tab_switching={}
        for key,frame in (("single",self.single_tab),("batch",self.batch_tab),("badges",self.settings_tab),("inspect",self.inspect_tab)):
            self.show_tab(key); self.update(); time.sleep(.15); self.update()
            tab_switching[key]={"selected":self.tabs.get()==self.tab_names[key],"visible":bool(frame.winfo_ismapped()),"other_visible":any(bool(other.winfo_ismapped()) for other in (self.single_tab,self.batch_tab,self.settings_tab,self.inspect_tab) if other is not frame)}
        self.sources=[Path(os.environ.get("NENOLINK_VERIFY_IMAGE","preserved-image.png"))]
        self.badge_var.set("ai-translation.png"); self.position_var.set("top-left"); self.size_var.set(33); self.margin_var.set(27); self.opacity_var.set(81)
        self.input_folder_var.set(r"C:\verification\batch-input"); self.batch_suffix_var.set("_published"); self.badge_source_var.set("standard")
        self.show_tab("badges"); self.update(); self.badges_back_button.invoke(); self.update(); time.sleep(.15); self.update()
        badges_back_preserved=self.tabs.get()==self.tab_names["single"] and self.badge_var.get()=="ai-translation.png" and len(self.sources)==1 and self.position_var.get()=="top-left" and self.size_var.get()==33 and self.margin_var.get()==27 and self.opacity_var.get()==81
        self.show_tab("batch"); self.update(); self.batch_back_button.invoke(); self.update(); time.sleep(.15); self.update()
        batch_back_preserved=self.tabs.get()==self.tab_names["single"] and self.input_folder_var.get()==r"C:\verification\batch-input" and self.batch_suffix_var.get()=="_published" and self.badge_var.get()=="ai-translation.png" and len(self.sources)==1
        self.show_tab("single")
        welcome_before_image=self.welcome_frame.winfo_manager()=="grid" and self.preview_label.winfo_manager()==""
        welcome_illustration=bool(self.welcome_image and self.welcome_photo)
        self.change_language("English"); self.update()
        english={"title":self.title(),"tabs":list(self.tab_names.values()),"guide":self.guide_button.cget("text"),"back":self.badges_back_button.cget("text"),"choose":self.open_button.cget("text"),"process":self.process_button.cget("text"),"position":self.position_label.cget("text"),"welcome_title":self.welcome_title.cget("text"),"welcome_tagline":self.welcome_tagline.cget("text"),"welcome_description1":self.welcome_description1.cget("text"),"welcome_description2":self.welcome_description2.cget("text")}
        self.change_language("Dansk"); self.update(); danish={"guide":self.guide_button.cget("text"),"back":self.badges_back_button.cget("text"),"choose":self.open_button.cget("text"),"tabs":list(self.tab_names.values()),"welcome_title":self.welcome_title.cget("text"),"welcome_tagline":self.welcome_tagline.cget("text"),"welcome_description1":self.welcome_description1.cget("text"),"welcome_description2":self.welcome_description2.cget("text")}
        self.change_language("Deutsch"); self.update(); german={"guide":self.guide_button.cget("text"),"choose":self.open_button.cget("text"),"welcome_title":self.welcome_title.cget("text"),"welcome_tagline":self.welcome_tagline.cget("text"),"welcome_description1":self.welcome_description1.cget("text"),"welcome_description2":self.welcome_description2.cget("text")}
        self.change_language("Français"); self.update(); french={"guide":self.guide_button.cget("text"),"choose":self.open_button.cget("text")}
        self.change_language("English"); self.badge_source_var.set("standard"); self.refresh_badges(False); badge_names=[p.name for p in self.badges.display_badges()]
        selected=[]
        for name in ("ai-assisted.png","ai-generated.png","ai-translation.png"):
            self.badge_var.set(name); self.select_badge(); self.update(); selected.append({"file":name,"display":self.badge_name_var.get(),"preview":bool(self.badge_photo)})
        sample=os.environ.get("NENOLINK_VERIFY_IMAGE")
        if sample:self.sources=[Path(sample)]; self.update_preview(); self.update()
        selected_badge_written=False
        image_metadata_verification=None
        if sample:
            sample_path=Path(sample); sample_hash=hashlib.sha256(sample_path.read_bytes()).hexdigest()
            translation=self.processor.process(sample_path,self.badges.find("ai-translation.png"),self.settings())
            assisted=self.processor.process(Path(sample),self.badges.find("ai-assisted.png"),self.settings())
            selected_badge_written=translation.tobytes()!=assisted.tobytes() and self.badge_var.get()=="ai-translation.png"
            metadata_root=report_path.with_name("packaged-metadata-verification")
            if metadata_root.exists():shutil.rmtree(metadata_root)
            metadata_root.mkdir(parents=True)
            localization=self.processor.process(sample_path,self.badges.find("ai-localization.png"),self.settings())
            no_ai=self.processor.process(sample_path,self.badges.find("no-ai.png"),self.settings())
            metadata=marker_metadata("ai-localization.png","AI Localization")
            jpeg_output=metadata_root/"sample_ai.jpg"; png_output=metadata_root/"sample_ai.png"; webp_output=metadata_root/"sample_ai.webp"; no_ai_output=metadata_root/"sample_no_ai.png"
            jpeg_written=self.processor.save(localization,jpeg_output,metadata)
            png_written=self.processor.save(localization,png_output,metadata)
            webp_written=self.processor.save(localization,webp_output,metadata)
            no_ai_written=self.processor.save(no_ai,no_ai_output,marker_metadata("no-ai.png","No AI")); no_ai_inspected=inspect_file(no_ai_output)
            with Image.open(jpeg_output) as checked:jpeg_exif=checked.getexif(); jpeg_values={"software":jpeg_exif.get(305),"description":jpeg_exif.get(270)}
            with Image.open(png_output) as checked:png_values={key:checked.info.get(key) for key in ("Software","AI Label","Marker Version","NenolinkAIMarker")}
            with Image.open(webp_output) as checked:webp_exif=checked.getexif(); webp_values={"software":webp_exif.get(305),"description":webp_exif.get(270)}
            inspected={path.suffix.lower().lstrip("."):inspect_file(path) for path in (jpeg_output,png_output,webp_output)}
            ordinary=inspect_file(sample_path)
            self.inspection_path=jpeg_output; self.inspection_result=inspected["jpg"]; self._render_inspection(); self.show_tab("inspect"); self.update(); self.inspect_back_button.invoke(); self.update()
            inspect_back_preserved=self.inspection_path==jpeg_output and self.inspection_result==inspected["jpg"] and self.tabs.get()==self.tab_names["single"]
            processed_after_inspect=self.processor.process(sample_path,self.badges.find("ai-assisted.png"),self.settings())
            release_regressions["inspect_then_image"]=processed_after_inspect.size==localization.size
            release_regressions["selected_image_inspect_back"]=self.sources==[sample_path] and processed_after_inspect.size==localization.size
            image_metadata_verification={"source_sha256_before":sample_hash,"source_sha256_after":hashlib.sha256(sample_path.read_bytes()).hexdigest(),"jpeg":{"path":str(jpeg_output),"written":jpeg_written,"values":jpeg_values,"inspected":inspected["jpg"].found,"label":inspected["jpg"].ai_label,"version":inspected["jpg"].marker_version},"png":{"path":str(png_output),"written":png_written,"values":png_values,"inspected":inspected["png"].found,"label":inspected["png"].ai_label},"webp":{"path":str(webp_output),"written":webp_written,"values":webp_values,"inspected":inspected["webp"].found},"no_ai":{"path":str(no_ai_output),"written":no_ai_written,"inspected":no_ai_inspected.found,"label":no_ai_inspected.ai_label,"version":no_ai_inspected.marker_version,"packaged_badge":bool(self.badges.find("no-ai.png"))},"ordinary_not_found":not ordinary.found,"inspect_back_preserved":inspect_back_preserved}
        checkpoint("image metadata")
        self.select_gallery_badge("ai-software.png"); gallery_selection_persisted=self.badge_var.get()=="ai-software.png" and self.badge_display_var.get()=="AI Software"
        logo_verification=None
        logo_sample=os.environ.get("NENOLINK_VERIFY_LOGO")
        if sample and logo_sample:
            logo_path=Path(logo_sample); logo_root=report_path.with_name("packaged-logo-verification")
            if logo_root.exists():shutil.rmtree(logo_root)
            logo_root.mkdir(parents=True)
            logo_settings=MarkerSettings(badge_name="ai-assisted.png",position="bottom-right",size_percent=20,margin=12,opacity=90,logo_enabled=True,logo_path=str(logo_path),logo_position="top-left",logo_size_percent=18,logo_margin=9,logo_opacity=75)
            self.sources=[Path(sample)]; self.badge_var.set(logo_settings.badge_name); self.position_var.set(logo_settings.position); self.size_var.set(logo_settings.size_percent); self.margin_var.set(logo_settings.margin); self.opacity_var.set(logo_settings.opacity)
            self.logo_path_var.set(str(logo_path)); self.logo_enabled_var.set(True); self.logo_position_var.set(logo_settings.logo_position); self.logo_size_var.set(logo_settings.logo_size_percent); self.logo_margin_var.set(logo_settings.logo_margin); self.logo_opacity_var.set(logo_settings.logo_opacity)
            self.update_preview(); self.update(); preview_both=self.preview_image.tobytes() if self.preview_image else b""
            self.logo_enabled_var.set(False); self.update_preview(); preview_badge_only=self.preview_image.tobytes() if self.preview_image else b""
            self.logo_enabled_var.set(True); self.logo_position_var.set("bottom-left"); self.update_preview(); preview_moved=self.preview_image.tobytes() if self.preview_image else b""
            self.logo_position_var.set(logo_settings.logo_position); self.update_preview()
            preview_output=logo_root/"live-preview.png"
            if self.preview_image:self.preview_image.save(preview_output)
            logo_output=logo_root/"single_ai.png"
            logo_metadata=marker_metadata(logo_settings.badge_name,"AI Assisted")
            logo_written=self.processor.save(self.processor.process(Path(sample),self.badges.find(logo_settings.badge_name),logo_settings,logo_path),logo_output,logo_metadata)
            inspected_logo=inspect_file(logo_output)
            batch_input=logo_root/"batch-input"; batch_output=logo_root/"batch-output"; batch_input.mkdir(); batch_output.mkdir()
            shutil.copy2(sample,batch_input/"brand01.png"); shutil.copy2(sample,batch_input/"brand02.png")
            logo_settings.output_preference="separate"; logo_settings.output_folder=str(batch_output); logo_settings.process_images=True; logo_settings.process_videos=False
            logo_batch=self.batch_processor.process(scan_folder(batch_input),self.badges.find(logo_settings.badge_name),logo_settings)
            output_bytes=logo_output.read_bytes()
            logo_verification={"output":str(logo_output),"output_exists":logo_output.is_file(),"metadata_written":logo_written,"ai_label":inspected_logo.ai_label,"logo_path_absent_from_metadata":str(logo_path).encode("utf-8") not in output_bytes,"source_sha256_before":hashlib.sha256(Path(sample).read_bytes()).hexdigest(),"source_sha256_after":hashlib.sha256(Path(sample).read_bytes()).hexdigest(),"live_preview":{"rendered":bool(preview_both),"path":str(preview_output),"logo_toggle_changes":preview_both!=preview_badge_only,"logo_position_changes":preview_both!=preview_moved,"size":self.preview_image.size if self.preview_image else None},"settings":{"badge_position":logo_settings.position,"logo_position":logo_settings.logo_position,"logo_size":logo_settings.logo_size_percent,"logo_margin":logo_settings.logo_margin,"logo_opacity":logo_settings.logo_opacity},"batch_successful":logo_batch.successful,"batch_outputs":sorted(path.name for path in batch_output.glob("*.png"))}
        checkpoint("own logo")
        custom_verification=None
        custom_folder=os.environ.get("NENOLINK_VERIFY_CUSTOM_BADGES")
        if custom_folder:
            if logo_sample:self.logo_path_var.set(str(logo_sample)); self.logo_enabled_var.set(True)
            self.custom_badge_var.set(custom_folder); self.badge_source_var.set("custom"); self.refresh_badges(False); self.update()
            custom_paths=self.badges.display_badges(); custom_names=[path.name for path in custom_paths]
            custom_displays=[self.badges.display_name(path.name) for path in custom_paths]
            if custom_paths:
                chosen=custom_paths[-1]; self.select_gallery_badge(chosen.name); self.update()
                if sample:self.sources=[Path(sample)]; self.update_preview(); self.update()
                output=report_path.with_name("verified-custom-output.png")
                processed=self.processor.process(Path(sample),chosen,self.settings(),self._logo_path()) if sample else None
                if processed is not None:self.processor.save(processed,output,marker_metadata(chosen.name,self.badges.display_name(chosen.name)))
                custom_metadata=None
                if output.is_file():
                    with Image.open(output) as checked:custom_metadata={key:checked.info.get(key) for key in ("Software","AI Label","Marker Version","NenolinkAIMarker")}
                selected_custom=self.badge_var.get(); retained_custom=self.custom_badge_var.get(); retained_sources=list(self.sources); self.show_tab("badges"); self.update(); self.badges_back_button.invoke(); self.update(); time.sleep(.15); self.update()
                custom_back_preserved=self.tabs.get()==self.tab_names["single"] and self.badge_source_var.get()=="custom" and self.badge_var.get()==selected_custom and self.custom_badge_var.get()==retained_custom and self.sources==retained_sources
                custom_verification={"files":custom_names,"displays":custom_displays,"selected":self.badge_var.get(),"selector_values":list(self.badge_menu.cget("values")),"gallery_badges":len(self.gallery_buttons),"preview":bool(self.preview_photo),"own_logo_enabled":self.logo_enabled_var.get(),"output_saved":output.is_file(),"metadata":custom_metadata,"logo_path_absent_from_metadata":not output.is_file() or str(logo_sample or "").encode("utf-8") not in output.read_bytes(),"status":self.status_var.get(),"source_controls_visible":self.custom_controls.winfo_manager()=="grid","back_preserved":custom_back_preserved}
        checkpoint("custom badges")
        guide_paths={code:localized_user_guide_path(code) for code in ("da","en","fr")}
        guide_language=os.environ.get("NENOLINK_VERIFY_GUIDE_LANGUAGE","en").lower()
        guide=localized_user_guide_path(guide_language); guide_opened=False
        if os.environ.get("NENOLINK_VERIFY_OPEN_GUIDE") == "1":
            try:open_user_guide(guide); guide_opened=True
            except OSError:guide_opened=False
        prior_tab=self.tabs.get(); self.show_tab("badges"); self.update_idletasks(); self.update()
        prior_offer=self.shortcut_offer_shown; self.shortcut_offer_shown=False; self._show_first_run_shortcut_offer(); self.update_idletasks()
        first_run_offer={"visible":bool(self.shortcut_offer_dialog and self.shortcut_offer_dialog.winfo_exists()),"title":self.shortcut_offer_title_label.cget("text"),"message":self.shortcut_offer_message_label.cget("text"),"create":self.shortcut_offer_create_button.cget("text"),"not_now":self.shortcut_offer_not_now_button.cget("text"),"persisted":self.settings().shortcut_offer_shown}
        self._dismiss_shortcut_offer(); self.shortcut_offer_shown=prior_offer or True
        packaged_ui_evidence={"footer_text":self.footer_copyright_label.cget("text"),"footer_visible":bool(self.footer_copyright_label.winfo_ismapped()),"footer_update_text":self.footer_update_link.cget("text"),"footer_update_visible":bool(self.footer_update_link.winfo_ismapped()),"footer_update_cursor":self.footer_update_link.cget("cursor"),"footer_update_action":callable(self._footer_update_callback) and callable(self.check_for_updates),"badges_update_button_present":hasattr(self,"check_updates_button"),"shortcut_text":self.desktop_shortcut_button.cget("text"),"shortcut_visible":bool(self.desktop_shortcut_button.winfo_ismapped()),"shortcut_module":create_desktop_shortcut.__module__,"shortcut_callable":callable(create_desktop_shortcut),"first_run_offer":first_run_offer,"update_notification_present":bool(self.update_notification.winfo_exists()),"update_notification_cursor":self.update_notification.cget("cursor"),"approved_update_handler":callable(self._open_update_page)}
        prior_workspace=self.active_content_type; self.active_content_type="pptx"; MarkerApp._render_authoritative_state(self); self.update_idletasks()
        packaged_ui_evidence["pptx_workspace"]={"visible":bool(self.pptx_controls.winfo_ismapped()),"selection_modes":sorted(self.pptx_selection_display_to_value.values()),"badge_count":len(self.pptx_badge_menu.cget("values")),"logo_visible":bool(self.pptx_logo_enable.winfo_ismapped()),"metadata_supported":self.pptx_processor.capabilities.supports_metadata,"process_callable":callable(self.process_pptx)}
        self.active_content_type=prior_workspace; MarkerApp._render_authoritative_state(self); self.update_idletasks()
        no_ai_root=report_path.with_name("packaged-no-ai-verification"); no_ai_root.mkdir(parents=True,exist_ok=True)
        no_ai_source=no_ai_root/"source.png"; no_ai_output=no_ai_root/"source_ai.png"; Image.new("RGB",(640,360),"white").save(no_ai_source)
        no_ai_source_hash=hashlib.sha256(no_ai_source.read_bytes()).hexdigest(); no_ai_badge=self.badges.find("no-ai.png")
        no_ai_marked=self.processor.process(no_ai_source,no_ai_badge,MarkerSettings(badge_name="no-ai.png")); no_ai_written=self.processor.save(no_ai_marked,no_ai_output,marker_metadata("no-ai.png","No AI")); no_ai_inspected=inspect_file(no_ai_output)
        no_ai_verification={"packaged_badge":bool(no_ai_badge and no_ai_badge.is_file()),"written":no_ai_written,"inspected":no_ai_inspected.found,"label":no_ai_inspected.ai_label,"version":no_ai_inspected.marker_version,"source_unchanged":no_ai_source_hash==hashlib.sha256(no_ai_source.read_bytes()).hexdigest(),"visible_overlay":no_ai_marked.tobytes()!=Image.new("RGBA",no_ai_marked.size,"white").tobytes()}
        payload={"version":__version__,"packaged_ui_evidence":packaged_ui_evidence,"no_ai_verification":no_ai_verification,"english":english,"danish":danish,"german":german,"french":french,"initial_badge_settings":initial_badge_settings,"welcome_before_image":welcome_before_image,"welcome_illustration":welcome_illustration,"welcome_hidden_after_image":(not sample or self.welcome_frame.winfo_manager()==""),"badges_found":len(badge_names),"badge_selector_visible":self.badge_menu.winfo_manager()=="grid","badge_selector_values":list(self.badge_menu.cget("values")),"gallery_badges":len(self.gallery_buttons),"gallery_selection_persisted":gallery_selection_persisted,"badges_tab_is_distinct":self.badge_source_frame.master is self.settings_tab,"selected_badges":selected,"image_preview":bool(self.preview_photo),"selected_badge_written":selected_badge_written,"image_metadata_verification":image_metadata_verification,"logo_verification":logo_verification,"custom_verification":custom_verification,"friendly_status":("_MEI" not in self.status_var.get() and "assets" not in self.status_var.get()),"process_button_state":self.process_button.cget("state"),"guide_language":guide_language,"guide_filename":guide.name,"guide_paths":{code:path.name for code,path in guide_paths.items()},"guide_exists":guide.is_file(),"guide_opened":guide_opened,"translation_keys_visible":any("." in str(value) and " " not in str(value) for group in (english,danish,german,french) for value in group.values() if isinstance(value,str))}
        ffmpeg_path=find_ffmpeg(); payload["ffmpeg_found"]=bool(ffmpeg_path); payload["ffmpeg_path"]=ffmpeg_path
        video_source=os.environ.get("NENOLINK_VERIFY_VIDEO")
        if video_source and ffmpeg_path:
            checkpoint("video start")
            video_source_path=Path(video_source); video_root=report_path.with_name("packaged-video-verification")
            self.sources=[video_source_path]; self.video_controls.grid(); self.video_mode_var.set("end"); self._update_video_duration_controls()
            layout={"sizes":{},"languages":{}}
            for geometry in ("1280x720","1366x768","1920x1080"):
                self.show_tab("single"); self.geometry(geometry); self.single_controls._parent_canvas.yview_moveto(0); self.update_idletasks(); self.update(); time.sleep(.15); self.update(); self.single_controls.update_scrollbar_visibility()
                before=self.single_controls._parent_canvas.yview(); self.single_controls._parent_canvas.yview_moveto(1); self.update_idletasks()
                self.update()
                canvas_bottom=self.single_controls._parent_canvas.winfo_rooty()+self.single_controls._parent_canvas.winfo_height()
                button_bottom=self.process_button.winfo_rooty()+self.process_button.winfo_height()
                layout["sizes"][geometry]={"scrollbar_needed":self.single_controls.scrollbar_needed,"process_reachable":button_bottom<=canvas_bottom,"scroll_range":before!=self.single_controls._parent_canvas.yview()}
            for language in ("English","Dansk","Deutsch","Français"):
                self.change_language(language); self.update_idletasks()
                layout["languages"][language]={"process_visible":bool(self.process_button.winfo_ismapped()),"video_mode_visible":bool(self.video_mode_menu.winfo_ismapped()),"duration_visible":bool(self.video_duration_entry.winfo_ismapped())}
            self.video_mode_var.set("permanent"); self._update_video_duration_controls(); self.update_idletasks(); layout["permanent_hides_duration"]=not bool(self.video_duration_entry.winfo_ismapped())
            self.video_mode_var.set("end"); self._update_video_duration_controls(); payload["layout_verification"]=layout
            if video_root.exists():shutil.rmtree(video_root)
            video_root.mkdir(parents=True,exist_ok=True)
            standard=self.badge_sources.repository("standard")
            settings_a=MarkerSettings(badge_name="ai-localization.png",position="top-left",size_percent=20,margin=40,opacity=100,video_mode="permanent")
            settings_b=MarkerSettings(badge_name="ai-generated.png",position="bottom-right",size_percent=30,margin=60,opacity=50,video_mode="beginning",video_duration=5)
            settings_c=MarkerSettings(badge_name="ai-generated.png",position="top-right",size_percent=25,margin=30,opacity=75,video_mode="end",video_duration=5)
            settings_d=MarkerSettings(badge_name="ai-assisted.png",position="bottom-left",size_percent=18,margin=25,opacity=85,video_mode="end",video_duration=10)
            output_a=video_root/f"{video_source_path.stem}_ai.mp4"; output_b=video_root/f"{video_source_path.stem}_beginning.mp4"; output_c=video_root/f"{video_source_path.stem}_end5.mp4"; output_d=video_root/f"{video_source_path.stem}_end10.mp4"
            self.batch_processor.process_video(video_source_path,standard.find(settings_a.badge_name),output_a,settings_a)
            checkpoint("video permanent")
            self.batch_processor.process_video(video_source_path,standard.find(settings_b.badge_name),output_b,settings_b)
            checkpoint("video beginning")
            self.batch_processor.process_video(video_source_path,standard.find(settings_c.badge_name),output_c,settings_c)
            checkpoint("video end5")
            self.batch_processor.process_video(video_source_path,standard.find(settings_d.badge_name),output_d,settings_d)
            checkpoint("video end10")
            mov_output=video_root/f"{video_source_path.stem}_ai.mov"
            self.batch_processor.process_video(video_source_path,standard.find(settings_c.badge_name),mov_output,settings_c)
            checkpoint("video mov")
            batch_input=video_root/"batch-input"; batch_output=video_root/"batch-output"; batch_input.mkdir(exist_ok=True)
            shutil.copy2(video_source_path,batch_input/"clip01.mp4"); shutil.copy2(video_source_path,batch_input/"clip02.mp4")
            batch_settings=MarkerSettings(badge_name="ai-generated.png",position="top-right",size_percent=25,margin=30,opacity=75,process_images=False,process_videos=True,output_preference="separate",output_folder=str(batch_output),batch_filename_suffix="_ai",video_mode="end",video_duration=5)
            batch_result=self.batch_processor.process(scan_folder(batch_input),standard.find(batch_settings.badge_name),batch_settings)
            checkpoint("video batch")
            inspected_mp4=inspect_file(output_c); inspected_mov=inspect_file(mov_output); ordinary_video_hash=hashlib.sha256(video_source_path.read_bytes()).hexdigest(); ordinary_video=inspect_file(video_source_path)
            self.sources=[video_source_path]; self.inspection_path=output_c; self.inspection_result=inspected_mp4; self._render_inspection(); self.show_tab("inspect"); self.update(); self.inspect_back_button.invoke(); self.update()
            regression_video=video_root/"inspect-back-regression.mp4"; self.batch_processor.process_video(video_source_path,standard.find(settings_c.badge_name),regression_video,settings_c)
            release_regressions["selected_video_inspect_back"]=self.sources==[video_source_path] and regression_video.is_file()
            version=subprocess.run([ffmpeg_path,"-version"],capture_output=True,text=True,**hidden_subprocess_kwargs()).stdout.splitlines()[0]
            payload["video_verification"]={"ffmpeg_version":version,"suggested_name":f"{video_source_path.stem}_ai{video_source_path.suffix}","outputs":{"permanent":str(output_a),"beginning5":str(output_b),"end5":str(output_c),"end10":str(output_d),"mov":str(mov_output)},"all_outputs_exist":all(path.is_file() for path in (output_a,output_b,output_c,output_d,mov_output)),"mp4_inspection":{"found":inspected_mp4.found,"software":inspected_mp4.software,"label":inspected_mp4.ai_label,"version":inspected_mp4.marker_version},"mov_inspection":{"found":inspected_mov.found,"software":inspected_mov.software,"label":inspected_mov.ai_label,"version":inspected_mov.marker_version},"ordinary_not_found":not ordinary_video.found,"source_sha256_before":ordinary_video_hash,"source_sha256_after":hashlib.sha256(video_source_path.read_bytes()).hexdigest(),"settings":[{"badge":s.badge_name,"mode":s.video_mode,"duration":s.video_duration,"position":s.position,"size":s.size_percent,"margin":s.margin,"opacity":s.opacity} for s in (settings_a,settings_b,settings_c,settings_d)],"batch_mode":batch_settings.video_mode,"batch_duration":batch_settings.video_duration,"batch_badge":batch_settings.badge_name,"batch_successful":batch_result.successful,"batch_metadata_warnings":batch_result.metadata_warnings,"batch_outputs":sorted(path.name for path in batch_output.glob("*.mp4"))}
        payload["tab_switching"]=tab_switching
        payload["back_navigation"]={"badges_preserved":badges_back_preserved,"batch_preserved":batch_back_preserved,"english_label":english["back"],"danish_label":danish["back"]}
        if os.environ.get("NENOLINK_VERIFY_RESET_LANGUAGE")=="da":self.change_language("Dansk")
        if logo_sample:self.logo_path_var.set(str(logo_sample)); self.logo_enabled_var.set(True)
        retained_custom_folder=self.custom_badge_var.get(); self.reset_application(); self.update(); time.sleep(.2); self.update()
        payload["reset_verification"]={"source":self.badge_source_var.get(),"selection":self.badge_var.get(),"folder_retained":self.custom_badge_var.get()==retained_custom_folder,"position":self.position_var.get(),"size":self.size_var.get(),"margin":self.margin_var.get(),"opacity":self.opacity_var.get(),"logo_enabled":self.logo_enabled_var.get(),"logo_path_retained":self.logo_path_var.get()==str(logo_sample or ""),"logo_position":self.logo_position_var.get(),"logo_size":self.logo_size_var.get(),"logo_margin":self.logo_margin_var.get(),"logo_opacity":self.logo_opacity_var.get(),"video_mode":self.video_mode_var.get(),"video_duration":self.video_duration_var.get(),"batch_suffix":self.batch_suffix_var.get(),"sources":len(self.sources),"scan_cleared":self.scan is None,"inspection_cleared":self.inspection_path is None and self.inspection_result is None and not self.inspection_error,"single_selected":self.tabs.get()==self.tab_names["single"],"welcome":self.welcome_frame.winfo_manager()=="grid","welcome_mapped":bool(self.welcome_frame.winfo_ismapped()),"welcome_title":self.welcome_title.cget("text"),"welcome_illustration":bool(self.welcome_photo and self.welcome_illustration.winfo_ismapped()),"preview_hidden":not bool(self.preview_label.winfo_ismapped()),"status":self.status_var.get()}
        if sample:
            after_reset=self.processor.process(Path(sample),self.badges.find("ai-assisted.png"),self.settings())
            release_regressions["inspect_reset_then_image"]=bool(after_reset.width and after_reset.height)
        payload["release_regressions"]=release_regressions
        report_path.write_text(json.dumps(payload,indent=2),encoding="utf-8"); checkpoint("complete"); self.destroy()

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
        self.geometry("1280x720"); self.minsize(980, 680)
        self.shell_controller = ShellController()
        self.active_content_type = self.shell_controller.destination
        self.active_tool = None
        self.mounted_view = ""
        self._boot = lambda _message: None
        self.image_workspace = None
        self.video_workspace = None
        self.pdf_workspace = None
        self.pptx_workspace = None
        self.tool_workspace = None
        self.content_buttons: dict[str, ctk.CTkButton] = {}
        self._initialize_image_services()
        self._build_shell_ui()
        self.render_shell_state()

    def _build_shell_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, corner_radius=0); header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Nenolink AI Marker", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=20, pady=14, sticky="w")
        self.language_var = ctk.StringVar(value=Translator.language_name(self.translator.language))
        self.language_menu = ctk.CTkOptionMenu(header, values=list(LANGUAGES), variable=self.language_var, command=self.change_image_language, width=150); self.language_menu.grid(row=0, column=1, padx=8)
        self.reset_button = ctk.CTkButton(header, text="Reset", command=self.reset_shell, width=100); self.reset_button.grid(row=0, column=2, padx=8)
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
                command=lambda event=destination: self.dispatch_shell_event(event))
            button.grid(row=0, column=index, padx=(0 if index == 0 else 4, 0))
            self.content_buttons[destination] = button

    def dispatch_shell_event(self, event: str) -> None:
        source = self.shell_controller.active_content_type
        if event in {"badges", "inspect"} or event == "back":
            self.shell_controller.dispatch(event)
            self.render_shell_state()
            return
        if source == "image" and event != "image" and event != "reset" and self._image_has_active_work():
            if not messagebox.askokcancel(self.translator.text("navigation.switch_title"), self.translator.text("navigation.switch_message")):
                return
        if source == "video" and event != "video" and event != "reset" and self._video_has_active_work():
            if not messagebox.askokcancel(self.translator.text("navigation.switch_title"), self.translator.text("navigation.switch_message")):
                return
        if source == "pdf" and event not in {"pdf", "reset"} and getattr(self, "pdf_path", None) is not None:
            if not messagebox.askokcancel(self.translator.text("navigation.switch_title"), self.translator.text("navigation.switch_message")):
                return
        if source == "pptx" and event not in {"pptx", "reset"} and self._format_has_active_work("pptx"):
            if not messagebox.askokcancel(self.translator.text("navigation.switch_title"), self.translator.text("navigation.switch_message")):
                return
        if source == "image" and event != "image":
            self._unmount_image_workspace()
        if source == "video" and event != "video":
            self._unmount_video_workspace()
        if source == "pdf" and event != "pdf":
            self.pdf_path = self.pdf_info = None; self.pdf_current_page = 0; self.pdf_preview_photo = None; self.pdf_scope_mode = "all"; self.pdf_active_scope = (); self.pdf_scope_input = ""
        if source == "pptx" and event != "pptx":
            self.pptx_path = self.pptx_metrics = None; self.pptx_current_slide = 0; self.pptx_preview_photo = None; self.pptx_scope_mode = "all"; self.pptx_active_scope = (); self.pptx_scope_input = ""
        self.shell_controller.dispatch(event)
        self.render_shell_state()

    def reset_shell(self) -> None:
        if self.shell_controller.active_content_type == "video":
            self._unmount_video_workspace()
        elif self.shell_controller.active_content_type == "pdf":
            self.pdf_path = self.pdf_info = None; self.pdf_current_page = 0; self.pdf_preview_photo = None; self.pdf_scope_mode = "all"; self.pdf_active_scope = (); self.pdf_scope_input = ""
        elif self.shell_controller.active_content_type == "pptx":
            self.pptx_path = self.pptx_metrics = None; self.pptx_current_slide = 0; self.pptx_preview_photo = None; self.pptx_scope_mode = "all"; self.pptx_active_scope = (); self.pptx_scope_input = ""
        else:
            self._unmount_image_workspace()
        self.shell_controller.dispatch("reset")
        self.render_shell_state()

    def _format_has_active_work(self, format_type: str) -> bool:
        if format_type == "image": return self._image_has_active_work()
        if format_type == "video": return self._video_has_active_work()
        if format_type == "pdf": return self.pdf_path is not None
        if format_type == "pptx": return self.pptx_path is not None
        return False

    def render_shell_state(self) -> None:
        destination = self.shell_controller.active_content_type
        tool = self.shell_controller.active_tool
        self.active_content_type = destination
        self.active_tool = tool
        for key, button in self.content_buttons.items():
            selected = key == (tool or destination)
            button.configure(fg_color=("#2474ad", "#1f6aa5") if selected else ("#6b6b6b", "#454545"))
        if tool:
            if self.image_workspace is not None: self.image_workspace.grid_remove()
            if self.video_workspace is not None: self.video_workspace.grid_remove()
            self._mount_tool(tool)
            self.mounted_view = placeholder_for(tool)
            return
        self._unmount_tool()
        if destination == "image":
            self._mount_image_workspace()
            self.mounted_view = "IMAGE"
        elif destination == "video":
            self._mount_video_workspace()
            self.mounted_view = "VIDEO"
        elif destination == "pdf":
            self._mount_pdf_workspace()
            self.mounted_view = "PDF"
        elif destination == "pptx":
            self._mount_pptx_workspace()
            self.mounted_view = "PPTX"
        else:
            self._clear_content_host()
            self.mounted_view = placeholder_for(destination)
            self.placeholder_label = ctk.CTkLabel(self.content_host, text=self.mounted_view, font=ctk.CTkFont(size=28, weight="bold"))
            self.placeholder_label.grid(row=0, column=0)

    # --- Image module lifecycle -------------------------------------------------

    def _initialize_image_services(self) -> None:
        self.config_store = ConfigStore()
        saved = self.config_store.load()
        self._saved_settings = saved
        self.processor = ImageProcessor()
        self.preview_renderer = ImagePreviewRenderer(self.processor)
        self.translator = Translator(locale_directory(), saved.language)
        self.badge_sources = BadgeSourceManager(badge_directory())
        self.badges = self.badge_sources.repository(saved.badge_source, saved.custom_badge_folder)
        self.sources: list[Path] = []
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

    def _clear_content_host(self) -> None:
        for child in self.content_host.winfo_children():
            child.destroy()
        self.image_workspace = self.video_workspace = self.pdf_workspace = self.pptx_workspace = self.tool_workspace = None

    def _mount_pdf_workspace(self) -> None:
        """Phase PDF-1 shell only; no processor or legacy document runtime."""
        if self.pdf_workspace is not None and self.pdf_workspace.winfo_exists():
            self.pdf_workspace.grid(); return
        self._clear_content_host()
        t = self.translator.text
        self.pdf_workspace = ctk.CTkFrame(self.content_host, fg_color="transparent")
        self.pdf_workspace.grid(row=0, column=0, padx=24, pady=24, sticky="nsew")
        self.pdf_workspace.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.pdf_workspace, text="PDF", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, pady=(8, 4), sticky="w")
        self.pdf_choose_button = ctk.CTkButton(self.pdf_workspace, text=t("pdf.choose"), command=self.choose_pdf_phase2); self.pdf_choose_button.grid(row=1, column=0, pady=(4, 8), sticky="w")
        self.pdf_file_label = ctk.CTkLabel(self.pdf_workspace, text=t("pdf.no_file"), text_color="gray60", anchor="w"); self.pdf_file_label.grid(row=2, column=0, pady=4, sticky="w")
        self.pdf_badge_enable = ctk.CTkCheckBox(self.pdf_workspace, text=t("pdf.add_badge"), variable=self.pdf_badge_enabled_var, command=self.pdf_visual_changed); self.pdf_badge_enable.grid(row=3, column=0, pady=(8, 2), sticky="w")
        self.pdf_badge_menu = ctk.CTkOptionMenu(self.pdf_workspace, variable=self.badge_display_var, values=["—"], command=self.select_badge_display); self.pdf_badge_menu.grid(row=4, column=0, pady=2, sticky="w")
        self.pdf_logo_enable = ctk.CTkCheckBox(self.pdf_workspace, text=t("logo.enable"), variable=self.logo_enabled_var, command=self.pdf_visual_changed); self.pdf_logo_enable.grid(row=5, column=0, pady=(4, 2), sticky="w")
        self.pdf_logo_choose = ctk.CTkButton(self.pdf_workspace, text=t("logo.choose"), command=self.choose_logo, width=150); self.pdf_logo_choose.grid(row=6, column=0, pady=2, sticky="w")
        self.pdf_position_menu = ctk.CTkOptionMenu(self.pdf_workspace, variable=self.position_display_var, values=list(getattr(self, "position_display_to_value", {}).keys()) or ["Bottom right"], command=self.change_position_display); self.pdf_position_menu.grid(row=13, column=0, pady=2, sticky="w")
        self.pdf_size_slider = ctk.CTkSlider(self.pdf_workspace, from_=1, to=100, number_of_steps=99, variable=self.size_var, command=self.pdf_visual_changed); self.pdf_size_slider.grid(row=14, column=0, pady=2, sticky="ew")
        self.pdf_margin_slider = ctk.CTkSlider(self.pdf_workspace, from_=0, to=250, number_of_steps=250, variable=self.margin_var, command=self.pdf_visual_changed); self.pdf_margin_slider.grid(row=15, column=0, pady=2, sticky="ew")
        self.pdf_opacity_slider = ctk.CTkSlider(self.pdf_workspace, from_=0, to=100, number_of_steps=100, variable=self.opacity_var, command=self.pdf_visual_changed); self.pdf_opacity_slider.grid(row=16, column=0, pady=2, sticky="ew")
        self.pdf_logo_position_menu = ctk.CTkOptionMenu(self.pdf_workspace, variable=self.logo_position_display_var, values=list(self.position_display_to_value), command=self.change_logo_position); self.pdf_logo_position_menu.grid(row=17, column=0, pady=2, sticky="w")
        self.pdf_logo_size_slider = ctk.CTkSlider(self.pdf_workspace, from_=1, to=100, number_of_steps=99, variable=self.logo_size_var, command=self.pdf_visual_changed); self.pdf_logo_size_slider.grid(row=18, column=0, pady=2, sticky="ew")
        self.pdf_logo_margin_slider = ctk.CTkSlider(self.pdf_workspace, from_=0, to=250, number_of_steps=250, variable=self.logo_margin_var, command=self.pdf_visual_changed); self.pdf_logo_margin_slider.grid(row=19, column=0, pady=2, sticky="ew")
        self.pdf_logo_opacity_slider = ctk.CTkSlider(self.pdf_workspace, from_=0, to=100, number_of_steps=100, variable=self.logo_opacity_var, command=self.pdf_visual_changed); self.pdf_logo_opacity_slider.grid(row=20, column=0, pady=2, sticky="ew")
        self.pdf_preview_label = ctk.CTkLabel(self.pdf_workspace, text="", fg_color=("gray92", "gray13"), width=680, height=240); self.pdf_preview_label.grid(row=7, column=0, pady=(12, 4), sticky="ew")
        nav = ctk.CTkFrame(self.pdf_workspace, fg_color="transparent"); nav.grid(row=8, column=0, pady=4)
        self.pdf_previous_button = ctk.CTkButton(nav, text="◀", width=42, command=lambda: self.change_pdf_page(-1)); self.pdf_previous_button.grid(row=0, column=0, padx=4)
        self.pdf_page_status = ctk.CTkLabel(nav, text="—", width=120); self.pdf_page_status.grid(row=0, column=1, padx=4)
        self.pdf_next_button = ctk.CTkButton(nav, text="▶", width=42, command=lambda: self.change_pdf_page(1)); self.pdf_next_button.grid(row=0, column=2, padx=4)
        self.pdf_scope_menu = ctk.CTkOptionMenu(self.pdf_workspace, values=["All", "First", "Selected", "Range"], command=self.change_pdf_scope_mode); self.pdf_scope_menu.grid(row=9, column=0, pady=(12, 2), sticky="w")
        self.pdf_scope_entry = ctk.CTkEntry(self.pdf_workspace, placeholder_text="2,4,7 or 5-7,10-12"); self.pdf_scope_entry.grid(row=10, column=0, pady=2, sticky="w")
        self.pdf_scope_update = ctk.CTkButton(self.pdf_workspace, text=t("document.scope_update"), command=self.update_pdf_scope, width=100); self.pdf_scope_update.grid(row=11, column=0, pady=(2, 4), sticky="w")
        self.pdf_scope_message = ctk.CTkLabel(self.pdf_workspace, text="", text_color="#b42318", anchor="w"); self.pdf_scope_message.grid(row=12, column=0, sticky="w")
        self.pdf_process_button = ctk.CTkButton(self.pdf_workspace, text=t("pdf.process"), command=self.process_pdf_phase6, width=180); self.pdf_process_button.grid(row=21, column=0, pady=(8, 4), sticky="w")
        self.refresh_image_badges()
        self._update_pdf_scope_controls()

    def _mount_pptx_workspace(self) -> None:
        """Phase 1 shell: a clean peer workspace with no document runtime."""
        if self.pptx_workspace is not None and self.pptx_workspace.winfo_exists():
            self.pptx_workspace.grid(); return
        self._clear_content_host()
        self.pptx_workspace = ctk.CTkFrame(self.content_host, fg_color="transparent")
        self.pptx_workspace.grid(row=0, column=0, padx=24, pady=24, sticky="nsew")
        self.pptx_workspace.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.pptx_workspace, text="PowerPoint", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, pady=(8, 4), sticky="w")
        self.pptx_choose_button = ctk.CTkButton(self.pptx_workspace, text="Choose PowerPoint", command=self.choose_pptx_phase2, width=180); self.pptx_choose_button.grid(row=1, column=0, pady=(4, 8), sticky="w")
        self.pptx_file_label = ctk.CTkLabel(self.pptx_workspace, text="No PowerPoint selected", text_color="gray60", anchor="w", justify="left"); self.pptx_file_label.grid(row=2, column=0, pady=4, sticky="w")
        self.pptx_status_label = ctk.CTkLabel(self.pptx_workspace, text="PowerPoint workspace ready.", text_color="gray60", anchor="w"); self.pptx_status_label.grid(row=3, column=0, pady=4, sticky="w")
        self.pptx_preview_label = ctk.CTkLabel(self.pptx_workspace, text="", fg_color=("gray92", "gray13"), width=680, height=240); self.pptx_preview_label.grid(row=4, column=0, pady=(12, 4), sticky="ew")
        nav = ctk.CTkFrame(self.pptx_workspace, fg_color="transparent"); nav.grid(row=5, column=0, pady=4)
        self.pptx_previous_button = ctk.CTkButton(nav, text="◀", width=42, command=lambda: self.change_pptx_slide(-1)); self.pptx_previous_button.grid(row=0, column=0, padx=4)
        self.pptx_slide_status = ctk.CTkLabel(nav, text="—", width=120); self.pptx_slide_status.grid(row=0, column=1, padx=4)
        self.pptx_next_button = ctk.CTkButton(nav, text="▶", width=42, command=lambda: self.change_pptx_slide(1)); self.pptx_next_button.grid(row=0, column=2, padx=4)
        self.pptx_scope_menu = ctk.CTkOptionMenu(self.pptx_workspace, values=["All", "First", "Selected", "Range"], command=self.change_pptx_scope_mode); self.pptx_scope_menu.grid(row=6, column=0, pady=(10, 2), sticky="w")
        self.pptx_scope_entry = ctk.CTkEntry(self.pptx_workspace, placeholder_text="3,7 or 2-4,7-9"); self.pptx_scope_entry.grid(row=7, column=0, pady=2, sticky="w")
        self.pptx_scope_update = ctk.CTkButton(self.pptx_workspace, text="Update", command=self.update_pptx_scope, width=100); self.pptx_scope_update.grid(row=8, column=0, pady=2, sticky="w")
        self.pptx_scope_message = ctk.CTkLabel(self.pptx_workspace, text="", text_color="#b42318", anchor="w"); self.pptx_scope_message.grid(row=9, column=0, sticky="w")
        self.pptx_badge_enabled_var = ctk.BooleanVar(value=True)
        self.pptx_badge_enable = ctk.CTkCheckBox(self.pptx_workspace, text=self.translator.text("pdf.add_badge"), variable=self.pptx_badge_enabled_var, command=self.pptx_visual_changed); self.pptx_badge_enable.grid(row=10, column=0, pady=(6, 2), sticky="w")
        self.pptx_badge_menu = ctk.CTkOptionMenu(self.pptx_workspace, variable=self.badge_display_var, values=["—"], command=self.select_badge_display); self.pptx_badge_menu.grid(row=11, column=0, pady=2, sticky="w")
        self.pptx_logo_enable = ctk.CTkCheckBox(self.pptx_workspace, text=self.translator.text("logo.enable"), variable=self.logo_enabled_var, command=self.pptx_visual_changed); self.pptx_logo_enable.grid(row=12, column=0, pady=(4, 2), sticky="w")
        self.pptx_logo_choose = ctk.CTkButton(self.pptx_workspace, text=self.translator.text("logo.choose"), command=self.choose_logo, width=150); self.pptx_logo_choose.grid(row=13, column=0, pady=2, sticky="w")
        self.pptx_position_menu = ctk.CTkOptionMenu(self.pptx_workspace, variable=self.position_display_var, values=list(self.position_display_to_value), command=self.change_position_display); self.pptx_position_menu.grid(row=14, column=0, pady=2, sticky="w")
        self.pptx_size_slider = ctk.CTkSlider(self.pptx_workspace, from_=1, to=100, number_of_steps=99, variable=self.size_var, command=self.pptx_visual_changed); self.pptx_size_slider.grid(row=15, column=0, pady=2, sticky="ew")
        self.pptx_margin_slider = ctk.CTkSlider(self.pptx_workspace, from_=0, to=250, number_of_steps=250, variable=self.margin_var, command=self.pptx_visual_changed); self.pptx_margin_slider.grid(row=16, column=0, pady=2, sticky="ew")
        self.pptx_opacity_slider = ctk.CTkSlider(self.pptx_workspace, from_=0, to=100, number_of_steps=100, variable=self.opacity_var, command=self.pptx_visual_changed); self.pptx_opacity_slider.grid(row=17, column=0, pady=2, sticky="ew")
        self.pptx_logo_position_menu = ctk.CTkOptionMenu(self.pptx_workspace, variable=self.logo_position_display_var, values=list(self.position_display_to_value), command=self.change_logo_position); self.pptx_logo_position_menu.grid(row=18, column=0, pady=2, sticky="w")
        self.refresh_image_badges()
        self._update_pptx_scope_controls()
        self._update_pptx_preview()

    def pptx_visual_changed(self, *_args) -> None:
        if getattr(self, "pptx_badge_menu", None): self.pptx_badge_menu.configure(state="normal" if self.pptx_badge_enabled_var.get() else "disabled")
        self._update_logo_controls(); self._update_pptx_preview(); self._save()

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
        if self.pptx_scope_mode == "all" and self.pptx_metrics:
            self.pptx_active_scope = tuple(range(1, self.pptx_metrics.item_count + 1)); self.pptx_current_slide = 1; self._update_pptx_preview()
        elif self.pptx_scope_mode == "first" and self.pptx_metrics:
            self.pptx_active_scope = (1,); self.pptx_current_slide = 1; self._update_pptx_preview()
        self._update_pptx_scope_controls()

    def update_pptx_scope(self) -> None:
        if not self.pptx_metrics or self.pptx_scope_mode not in {"selected", "range"}: return
        text = self.pptx_scope_entry.get().strip()
        try:
            values = []
            for part in (piece.strip() for piece in text.split(",") if piece.strip()):
                if self.pptx_scope_mode == "selected":
                    if "-" in part: raise ValueError
                    values.append(int(part))
                else:
                    bounds = part.split("-")
                    if len(bounds) != 2: raise ValueError
                    start, end = (int(value.strip()) for value in bounds)
                    if start > end: raise ValueError
                    values.extend(range(start, end + 1))
            values = sorted(set(values))
            if not values or any(value < 1 or value > self.pptx_metrics.item_count for value in values): raise ValueError
            self.pptx_active_scope = tuple(values); self.pptx_scope_input = text; self.pptx_current_slide = values[0]; self.pptx_scope_message.configure(text=""); self._update_pptx_preview()
        except (TypeError, ValueError):
            self.pptx_scope_message.configure(text="Invalid slide selection. The previous scope was preserved.")

    def _update_pptx_preview(self) -> None:
        if not getattr(self, "pptx_preview_label", None): return
        if not self.pptx_path or not self.pptx_metrics:
            self.pptx_preview_photo = None; self.pptx_preview_label.configure(image=None, text="Choose a PowerPoint file to preview a slide."); self.pptx_slide_status.configure(text="—"); self.pptx_previous_button.configure(state="disabled"); self.pptx_next_button.configure(state="disabled"); return
        try:
            marked = self.pptx_current_slide in set(self.pptx_active_scope)
            badge = self.badges.find(self.badge_var.get()) if marked and self.pptx_badge_enabled_var.get() else None
            logo = self._logo_path() if marked and self.logo_enabled_var.get() else None
            result = self.pptx_preview_renderer.render(self.pptx_path, self.pptx_current_slide, badge, self.settings(), logo)
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

    def pdf_visual_changed(self, *_args) -> None:
        """Rerender only the current page; PDF scope and navigation stay intact."""
        if getattr(self, "pdf_badge_menu", None):
            self.pdf_badge_menu.configure(state="normal" if self.pdf_badge_enabled_var.get() else "disabled")
        self._update_logo_controls()
        self.render_pdf_preview()

    def choose_pdf_phase2(self) -> None:
        selected = filedialog.askopenfilename(title="Choose PDF", filetypes=[("PDF (*.pdf)", "*.pdf")])
        if not selected: return
        path = Path(selected)
        try:
            info = self.pdf_processor.inspect(path)
        except PasswordProtectedPdfError:
            messagebox.showerror("PDF", "Encrypted or password-protected PDFs are not supported."); return
        except (OSError, ValueError, AttributeError) as error:
            messagebox.showerror("PDF", f"Could not read PDF: {error}"); return
        self.pdf_path, self.pdf_info = path, info
        self.pdf_current_page = 1; self.pdf_preview_photo = None; self.pdf_scope_mode = "all"; self.pdf_active_scope = tuple(range(1, info.metrics.item_count + 1)); self.pdf_scope_input = ""
        size = human_file_size(info.metrics.size_bytes)
        signed = "\nWarning: existing digital signatures may be invalidated when modified." if info.signed else ""
        self.pdf_file_label.configure(text=f"{path.name}\n{size} · {info.metrics.item_count} pages{signed}")
        self.status_var.set(f"PDF loaded: {path.name}")
        self.render_pdf_preview()

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

    def process_pdf_phase6(self) -> None:
        """Save a new PDF using the already validated PDF-owned scope."""
        if not self.pdf_path or not self.pdf_info:
            messagebox.showwarning(self.translator.text("warning.title"), self.translator.text("pdf.choose_first")); return
        if not self._confirm_pdf_limits_phase6() or not self._confirm_pdf_signature(): return
        badge = self.badges.find(self.badge_var.get()) if self.pdf_badge_enabled_var.get() else None
        label = self.badges.display_name(self.badge_var.get()) if badge else ""
        disclosure, logo = settings_for_documents(self.settings(), label=label, disclosure_language=self.translator.language)
        if not badge and not logo.enabled:
            messagebox.showwarning(self.translator.text("warning.title"), self.translator.text("pdf.overlay_required")); return
        selected = filedialog.asksaveasfilename(title=self.translator.text("pdf.save_as"), initialdir=str(self.pdf_path.parent), initialfile=f"{self.pdf_path.stem}_ai.pdf", defaultextension=".pdf", filetypes=[("PDF (*.pdf)", "*.pdf")], confirmoverwrite=True)
        if not selected: return
        destination = Path(selected)
        if destination.resolve() == self.pdf_path.resolve():
            messagebox.showerror(self.translator.text("error.title"), self.translator.text("pdf.extension_error")); return
        try:
            result = self.pdf_processor.process(ProcessingRequest(self.pdf_path, destination, disclosure, badge_path=badge, logo=logo, metadata=marker_metadata(disclosure.badge_name, disclosure.label)), ItemSelection("selected", tuple(self.pdf_active_scope)))
        except (OSError, ValueError) as error:
            messagebox.showerror(self.translator.text("error.title"), self.translator.text("pdf.error", error=error)); return
        self.status_var.set(self.translator.text("pdf.saved", name=result.destination.name, count=len(result.selected_pages)))

    def _update_pdf_scope_controls(self) -> None:
        if not getattr(self, "pdf_scope_menu", None): return
        editable = self.pdf_scope_mode in {"selected", "range"}
        self.pdf_scope_entry.configure(state="normal" if editable else "disabled")
        self.pdf_scope_update.configure(state="normal" if editable else "disabled")

    def change_pdf_scope_mode(self, label: str) -> None:
        self.pdf_scope_mode = {"All": "all", "First": "first", "Selected": "selected", "Range": "range"}.get(label, "all")
        if self.pdf_scope_mode == "all" and self.pdf_info: self.pdf_active_scope = tuple(range(1, self.pdf_info.metrics.item_count + 1)); self.pdf_current_page = 1; self.render_pdf_preview()
        elif self.pdf_scope_mode == "first" and self.pdf_info: self.pdf_active_scope = (1,); self.pdf_current_page = 1; self.render_pdf_preview()
        self._update_pdf_scope_controls()

    def update_pdf_scope(self) -> None:
        if not self.pdf_info or self.pdf_scope_mode not in {"selected", "range"}: return
        text = self.pdf_scope_entry.get().strip()
        try:
            values = []
            parts = [part.strip() for part in text.split(",") if part.strip()]
            if not parts: raise ValueError("Enter at least one page.")
            for part in parts:
                if self.pdf_scope_mode == "selected":
                    if "-" in part: raise ValueError("Selected pages must use comma-separated numbers.")
                    values.append(int(part))
                else:
                    bounds = part.split("-")
                    if len(bounds) != 2: raise ValueError("Ranges must use start-end syntax.")
                    start, end = (int(value.strip()) for value in bounds)
                    if start > end: raise ValueError("Range start must not exceed end.")
                    values.extend(range(start, end + 1))
            values = sorted(set(values))
            if any(value < 1 or value > self.pdf_info.metrics.item_count for value in values): raise ValueError("Page is outside the PDF.")
            self.pdf_active_scope = tuple(values); self.pdf_scope_input = text; self.pdf_scope_message.configure(text="")
            self.pdf_current_page = values[0]; self.render_pdf_preview()
        except (TypeError, ValueError):
            self.pdf_scope_message.configure(text="Invalid page selection. The previous scope was preserved.")

    def render_pdf_preview(self) -> None:
        if not self.pdf_path or not self.pdf_info or not getattr(self, "pdf_preview_label", None): return
        try:
            scope = getattr(self, "pdf_active_scope", tuple(range(1, self.pdf_info.metrics.item_count + 1)))
            marked = self.pdf_current_page in set(scope)
            badge_enabled = self.pdf_badge_enabled_var.get() if hasattr(self, "pdf_badge_enabled_var") else True
            logo_enabled = self.logo_enabled_var.get() if hasattr(self, "logo_enabled_var") else False
            badge = self.badges.find(self.badge_var.get()) if marked and hasattr(self, "badges") and hasattr(self, "badge_var") and badge_enabled else None
            logo = self._logo_path() if marked and logo_enabled and hasattr(self, "_logo_path") else None
            try:
                result = self.pdf_preview_renderer.render(self.pdf_path, self.pdf_current_page, badge, self.settings(), logo)
            except TypeError:
                result = self.pdf_preview_renderer.render(self.pdf_path, self.pdf_current_page, badge, self.settings())
            self.pdf_current_page = result.page_number
            self.pdf_preview_photo = ctk.CTkImage(light_image=result.image, dark_image=result.image, size=result.image.size)
            self.pdf_preview_label.configure(image=self.pdf_preview_photo, text="")
            self.pdf_page_status.configure(text=f"{self.pdf_current_page} / {self.pdf_info.metrics.item_count}")
            self.pdf_previous_button.configure(state="normal" if self.pdf_current_page > 1 else "disabled")
            self.pdf_next_button.configure(state="normal" if self.pdf_current_page < self.pdf_info.metrics.item_count else "disabled")
        except (OSError, ValueError) as error:
            self.pdf_preview_label.configure(image=None, text=f"Could not render PDF page: {error}")

    def change_pdf_page(self, delta: int) -> None:
        if not self.pdf_info: return
        self.pdf_current_page = max(1, min(self.pdf_info.metrics.item_count, self.pdf_current_page + delta))
        self.render_pdf_preview()

    def _mount_image_workspace(self) -> None:
        if self.image_workspace is not None and self.image_workspace.winfo_exists():
            self.image_workspace.grid()
            return
        self._clear_content_host()
        self.image_workspace = ctk.CTkFrame(self.content_host, fg_color="transparent")
        self.image_workspace.grid(row=0, column=0, sticky="nsew")
        self.image_workspace.grid_columnconfigure(0, weight=1); self.image_workspace.grid_rowconfigure(0, weight=1)
        self._build_image_workspace()
        self.refresh_image_badges()
        self.apply_image_translations()
        self._validate_saved_logo()
        self._show_welcome()

    def _mount_video_workspace(self) -> None:
        if self.video_workspace is not None and self.video_workspace.winfo_exists():
            self.video_workspace.grid(); return
        self._clear_content_host()
        self.video_workspace = ctk.CTkFrame(self.content_host, fg_color="transparent")
        self.video_workspace.grid(row=0, column=0, sticky="nsew"); self.video_workspace.grid_columnconfigure(1, weight=1); self.video_workspace.grid_rowconfigure(0, weight=1)
        left = AutoHideScrollableFrame(self.video_workspace, width=320, fg_color=("gray86", "gray17")); left.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="nsew"); left.grid_columnconfigure(0, weight=1)
        self.video_open_button = ctk.CTkButton(left, command=self.open_video); self.video_open_button.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="ew")
        self.video_file_label = ctk.CTkLabel(left, anchor="w", justify="left", wraplength=280); self.video_file_label.grid(row=1, column=0, padx=14, pady=3, sticky="ew")
        self.video_mode_label = ctk.CTkLabel(left); self.video_mode_label.grid(row=2, column=0, padx=14, pady=(8, 1), sticky="w")
        self.video_mode_var = ctk.StringVar(value="permanent"); self.video_mode_display_var = ctk.StringVar()
        self.video_mode_display_to_value = {"Permanent": "permanent", "Beginning": "beginning", "End": "end"}
        self.video_mode_menu = ctk.CTkOptionMenu(left, variable=self.video_mode_display_var, values=list(self.video_mode_display_to_value), command=self.change_video_mode); self.video_mode_menu.grid(row=3, column=0, padx=14, pady=2, sticky="ew")
        self.video_duration_label = ctk.CTkLabel(left); self.video_duration_label.grid(row=4, column=0, padx=14, pady=(4, 1), sticky="w")
        self.video_duration_var = ctk.IntVar(value=5); self.video_duration_entry = ctk.CTkEntry(left, textvariable=self.video_duration_var); self.video_duration_entry.grid(row=5, column=0, padx=14, pady=2, sticky="ew")
        self.video_position_label = ctk.CTkLabel(left); self.video_position_label.grid(row=6, column=0, padx=14, pady=(6, 1), sticky="w")
        self.video_position_var = ctk.StringVar(value="bottom-right"); self.video_position_display_var = ctk.StringVar(value="Bottom right")
        self.video_position_display_to_value = {"Top left":"top-left", "Top right":"top-right", "Bottom left":"bottom-left", "Bottom right":"bottom-right", "Center":"center"}
        self.video_position_menu = ctk.CTkOptionMenu(left, variable=self.video_position_display_var, values=list(self.video_position_display_to_value), command=self.change_video_position); self.video_position_menu.grid(row=7, column=0, padx=14, pady=2, sticky="ew")
        self.video_badge_label = ctk.CTkLabel(left); self.video_badge_label.grid(row=8, column=0, padx=14, pady=(6, 1), sticky="w")
        self.video_badge_var = ctk.StringVar(value=self.badge_display_var.get()); self.video_badge_menu = ctk.CTkOptionMenu(left, variable=self.video_badge_var, values=["—"], command=self.change_video_badge); self.video_badge_menu.grid(row=9, column=0, padx=14, pady=2, sticky="ew")
        self.video_size_var = ctk.IntVar(value=20); self.video_margin_var = ctk.IntVar(value=20); self.video_opacity_var = ctk.IntVar(value=100)
        self.video_size_label = self._video_slider(left, self.video_size_var, 1, 100, 10, "Size"); self.video_margin_label = self._video_slider(left, self.video_margin_var, 0, 250, 12, "Margin"); self.video_opacity_label = self._video_slider(left, self.video_opacity_var, 0, 100, 14, "Opacity")
        self.video_process_button = ctk.CTkButton(left, command=self.save_video); self.video_process_button.grid(row=16, column=0, padx=14, pady=(4, 10), sticky="ew")
        right = ctk.CTkFrame(self.video_workspace); right.grid(row=0, column=1, padx=(8, 4), pady=4, sticky="nsew"); right.grid_columnconfigure(0, weight=1); right.grid_rowconfigure(0, weight=1)
        self.video_preview_label = ctk.CTkLabel(right, text=self.translator.text("preview.video_selected", name="")); self.video_preview_label.grid(row=0, column=0, padx=20, pady=20)
        self._refresh_video_labels(); self._refresh_video_badges()

    def _video_slider(self, parent, variable, start, end, row, label):
        output = ctk.CTkLabel(parent, text=label); output.grid(row=row, column=0, padx=14, pady=(4, 0), sticky="w")
        ctk.CTkSlider(parent, from_=start, to=end, number_of_steps=end-start, variable=variable, command=self._video_changed).grid(row=row+1, column=0, padx=14, pady=(1, 3), sticky="ew")
        return output

    def _mount_tool(self, tool: str) -> None:
        if self.tool_workspace is not None and self.tool_workspace.winfo_exists():
            self.tool_workspace.grid(); return
        self.tool_workspace = ctk.CTkFrame(self.content_host); self.tool_workspace.grid(row=0, column=0, sticky="nsew"); self.tool_workspace.grid_columnconfigure(0, weight=1); self.tool_workspace.grid_rowconfigure(1, weight=1)
        ctk.CTkButton(self.tool_workspace, text=self.translator.text("button.back"), command=lambda: self.dispatch_shell_event("back"), width=110).grid(row=0, column=0, padx=16, pady=(10, 4), sticky="w")
        if tool == "badges": self._build_badges_tool()
        else: self._build_inspect_tool()

    def _unmount_tool(self) -> None:
        if self.tool_workspace is not None and self.tool_workspace.winfo_exists(): self.tool_workspace.destroy()
        self.tool_workspace = None

    def _unmount_image_workspace(self) -> None:
        self.sources = []
        self.preview_renderer.clear(); self.preview_photo = self.preview_image = None
        self._clear_content_host()

    def _image_has_active_work(self) -> bool:
        return bool(self.sources)

    def _video_has_active_work(self) -> bool:
        return bool(getattr(self, "video_sources", []))

    def _unmount_video_workspace(self) -> None:
        self.video_sources = []
        self._clear_content_host()

    def _refresh_video_labels(self) -> None:
        if not getattr(self, "video_open_button", None): return
        t = self.translator.text
        self.video_open_button.configure(text="1. " + t("button.open_media")); self.video_badge_label.configure(text="2. " + t("badge")); self.video_position_label.configure(text="3. " + t("position")); self.video_process_button.configure(text=t("button.process_video")); self.video_mode_label.configure(text=t("video.badge")); self.video_duration_label.configure(text=t("video.duration"))
        self.video_mode_display_to_value = {t("video.mode.permanent"): "permanent", t("video.mode.beginning"): "beginning", t("video.mode.end"): "end"}; self.video_mode_menu.configure(values=list(self.video_mode_display_to_value)); self.video_mode_display_var.set(next((label for label, value in self.video_mode_display_to_value.items() if value == self.video_mode_var.get()), list(self.video_mode_display_to_value)[0]))
        self.video_position_display_to_value = {t("position.top_left"): "top-left", t("position.top_right"): "top-right", t("position.bottom_left"): "bottom-left", t("position.bottom_right"): "bottom-right", t("position.center"): "center"}; self.video_position_menu.configure(values=list(self.video_position_display_to_value)); self.video_position_display_var.set(next((label for label, value in self.video_position_display_to_value.items() if value == self.video_position_var.get()), t("position.bottom_right")))
        self._update_video_duration_visibility()

    def _refresh_video_badges(self) -> None:
        if not getattr(self, "video_badge_menu", None): return
        displays = [self.badges.display_name(path.name) for path in self.badges.display_badges()]; self.video_badge_menu.configure(values=displays or [self.translator.text("badge.none")]); self.video_badge_var.set(self.badges.display_name(self.badge_var.get()) if self.badges.find(self.badge_var.get()) else (displays[0] if displays else "—"))

    def _update_video_duration_visibility(self) -> None:
        if not getattr(self, "video_duration_entry", None): return
        visible = self.video_mode_var.get() in {"beginning", "end"}
        (self.video_duration_label.grid if visible else self.video_duration_label.grid_remove)(); (self.video_duration_entry.grid if visible else self.video_duration_entry.grid_remove)()

    def change_video_mode(self, label: str) -> None:
        self.video_mode_var.set(self.video_mode_display_to_value[label]); self._update_video_duration_visibility(); self._save_image_settings()

    def change_video_position(self, label: str) -> None:
        self.video_position_var.set(self.video_position_display_to_value[label]); self._save_image_settings()

    def change_video_badge(self, label: str) -> None:
        self.video_badge_var.set(label); self._save_image_settings()

    def _video_changed(self, *_args) -> None:
        self._save_image_settings()

    def open_video(self) -> None:
        selected = filedialog.askopenfilename(title=self.translator.text("dialog.open_media"), filetypes=[(self.translator.text("files.supported_videos"), "*.mp4 *.mov *.mkv *.avi *.webm"), (self.translator.text("files.all"), "*.*")])
        if selected:
            self.video_sources = [Path(selected)]; self.video_file_label.configure(text=self.video_sources[0].name); self.video_preview_label.configure(text=self.translator.text("preview.video_selected", name=self.video_sources[0].name)); self._save_image_settings()

    def save_video(self) -> None:
        if not self._video_has_active_work(): messagebox.showwarning(self.translator.text("warning.title"), self.translator.text("warning.nothing_to_save")); return
        badge_name = next((name for name in self.badge_display_to_file if name == self.video_badge_var.get()), self.badge_var.get()); badge = self.badges.find(badge_name)
        if not badge: messagebox.showwarning(self.translator.text("warning.title"), self.translator.text("warning.nothing_to_save")); return
        source = self.video_sources[0]; suggested = source.with_name(f"{source.stem}_ai{source.suffix}"); target = filedialog.asksaveasfilename(title=self.translator.text("dialog.save_video_as"), initialdir=str(source.parent), initialfile=suggested.name, defaultextension=source.suffix, filetypes=[(self.translator.text("files.supported_videos"), "*.mp4 *.mov *.mkv *.avi *.webm"), (self.translator.text("files.all"), "*.*")], confirmoverwrite=True)
        if not target: return
        settings = MarkerSettings(badge_name=badge.name, position=self.video_position_var.get(), size_percent=self.video_size_var.get(), margin=self.video_margin_var.get(), opacity=self.video_opacity_var.get(), video_mode=self.video_mode_var.get(), video_duration=self.video_duration_var.get())
        try:
            if not find_ffmpeg(): raise ValueError(self.translator.text("error.video_component_missing"))
            self.batch_processor = BatchProcessor(self.processor); self.batch_processor.process_video(source, badge, Path(target), settings, marker_metadata(badge.name, self.badges.display_name(badge.name))); self.status_var.set(self.translator.text("video.saved_name", name=Path(target).name))
        except (OSError, ValueError) as error: messagebox.showerror(self.translator.text("error.title"), str(error))

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
        self.badge_source_var.set(self.tool_badge_source_var.get()); self.custom_badge_var.set(self.tool_badge_folder_var.get()); self.refresh_image_badges()
        for child in self.tool_badge_gallery.winfo_children(): child.destroy()
        for index, path in enumerate(self.badges.display_badges()):
            button = ctk.CTkButton(self.tool_badge_gallery, text=self.badges.display_name(path.name), command=lambda name=path.name: self._tool_select_badge(name)); button.grid(row=index // 4, column=index % 4, padx=5, pady=5)

    def _tool_select_badge(self, name: str) -> None:
        self.badge_var.set(name); self.select_image_badge(); self._tool_refresh_badges()

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
        workspace = self.image_workspace
        workspace.grid_columnconfigure(1, weight=1); workspace.grid_rowconfigure(0, weight=1)
        left = AutoHideScrollableFrame(workspace, width=320, fg_color=("gray86", "gray17")); self.image_controls = left
        left.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="nsew"); left.grid_columnconfigure(0, weight=1)
        self.open_button = ctk.CTkButton(left, command=self.open_images); self.open_button.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="ew")
        self.file_label = ctk.CTkLabel(left, anchor="w", justify="left", wraplength=280); self.file_label.grid(row=1, column=0, padx=14, pady=3, sticky="ew")
        self.file_size_guidance = ctk.CTkLabel(left, anchor="w", justify="left", wraplength=280, text_color="gray60"); self.file_size_guidance.grid(row=2, column=0, padx=14, pady=(0, 4), sticky="ew")

        badge_section = ctk.CTkFrame(left); badge_section.grid(row=3, column=0, padx=14, pady=(4, 4), sticky="ew"); badge_section.grid_columnconfigure(0, weight=1)
        self.badge_enable = ctk.CTkCheckBox(badge_section, variable=self.badge_enabled_var, command=self.badge_enabled_changed); self.badge_enable.grid(row=0, column=0, padx=8, pady=(7, 3), sticky="w")
        self.single_badge_label = ctk.CTkLabel(badge_section, font=ctk.CTkFont(weight="bold")); self.single_badge_label.grid(row=1, column=0, padx=8, pady=(2, 1), sticky="w")
        self.badge_menu = ctk.CTkOptionMenu(badge_section, variable=self.badge_display_var, values=["—"], command=self.select_badge_display); self.badge_menu.grid(row=2, column=0, padx=8, pady=2, sticky="ew")
        badge_preview = ctk.CTkFrame(badge_section); badge_preview.grid(row=3, column=0, padx=8, pady=(3, 7), sticky="ew"); badge_preview.grid_columnconfigure(1, weight=1)
        self.single_badge_preview_label = ctk.CTkLabel(badge_preview, width=90, height=44); self.single_badge_preview_label.grid(row=0, column=0, padx=5, pady=5)
        self.single_badge_name_label = ctk.CTkLabel(badge_preview, textvariable=self.badge_name_var, font=ctk.CTkFont(weight="bold"), anchor="w", wraplength=155); self.single_badge_name_label.grid(row=0, column=1, padx=(3, 5), pady=5, sticky="ew")

        self.position_label = ctk.CTkLabel(left); self.position_label.grid(row=4, column=0, padx=14, pady=(5, 1), sticky="w")
        self.position_menu = ctk.CTkOptionMenu(left, variable=self.position_display_var, values=["—"], command=self.change_position_display); self.position_menu.grid(row=5, column=0, padx=14, pady=2, sticky="ew")
        self.size_label = self._image_slider(left, self.size_var, 1, 100, 6)
        self.margin_label = self._image_slider(left, self.margin_var, 0, 250, 8)
        self.opacity_label = self._image_slider(left, self.opacity_var, 0, 100, 10)

        self.logo_controls = ctk.CTkFrame(left); self.logo_controls.grid(row=12, column=0, padx=14, pady=(5, 8), sticky="ew"); self.logo_controls.grid_columnconfigure(1, weight=1)
        self.logo_heading = ctk.CTkLabel(self.logo_controls, font=ctk.CTkFont(weight="bold")); self.logo_heading.grid(row=0, column=0, columnspan=2, padx=8, pady=(6, 2), sticky="w")
        self.logo_enable = ctk.CTkCheckBox(self.logo_controls, variable=self.logo_enabled_var, command=self.logo_changed); self.logo_enable.grid(row=1, column=0, columnspan=2, padx=8, pady=3, sticky="w")
        self.logo_choose = ctk.CTkButton(self.logo_controls, command=self.choose_logo, height=28); self.logo_choose.grid(row=2, column=0, padx=8, pady=3, sticky="w")
        self.logo_filename = ctk.CTkLabel(self.logo_controls, textvariable=self.logo_filename_var, anchor="w", wraplength=155); self.logo_filename.grid(row=2, column=1, padx=(2, 8), pady=3, sticky="ew")
        self.logo_position_label = ctk.CTkLabel(self.logo_controls); self.logo_position_label.grid(row=3, column=0, padx=8, pady=2, sticky="w")
        self.logo_position_menu = ctk.CTkOptionMenu(self.logo_controls, variable=self.logo_position_display_var, values=["—"], command=self.change_logo_position, height=28); self.logo_position_menu.grid(row=3, column=1, padx=8, pady=2, sticky="ew")
        self.logo_size_label = ctk.CTkLabel(self.logo_controls); self.logo_size_label.grid(row=4, column=0, columnspan=2, padx=8, sticky="w")
        self.logo_size_slider = ctk.CTkSlider(self.logo_controls, from_=1, to=100, number_of_steps=99, variable=self.logo_size_var, command=self.logo_changed); self.logo_size_slider.grid(row=5, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        self.logo_margin_label = ctk.CTkLabel(self.logo_controls); self.logo_margin_label.grid(row=6, column=0, columnspan=2, padx=8, sticky="w")
        self.logo_margin_slider = ctk.CTkSlider(self.logo_controls, from_=0, to=250, number_of_steps=250, variable=self.logo_margin_var, command=self.logo_changed); self.logo_margin_slider.grid(row=7, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        self.logo_opacity_label = ctk.CTkLabel(self.logo_controls); self.logo_opacity_label.grid(row=8, column=0, columnspan=2, padx=8, sticky="w")
        self.logo_opacity_slider = ctk.CTkSlider(self.logo_controls, from_=0, to=100, number_of_steps=100, variable=self.logo_opacity_var, command=self.logo_changed); self.logo_opacity_slider.grid(row=9, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        self.logo_images_only = ctk.CTkLabel(self.logo_controls, text_color="gray60"); self.logo_images_only.grid(row=10, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w")
        self.process_button = ctk.CTkButton(left, command=self.save_images); self.process_button.grid(row=13, column=0, padx=14, pady=(2, 10), sticky="ew")

        right = ctk.CTkFrame(workspace); right.grid(row=0, column=1, padx=(8, 4), pady=4, sticky="nsew"); right.grid_columnconfigure(0, weight=1); right.grid_rowconfigure(0, weight=1)
        self.preview_label = ctk.CTkLabel(right)
        self.welcome_frame = ctk.CTkFrame(right, fg_color="transparent"); self.welcome_frame.grid(row=0, column=0, padx=18, pady=14, sticky="nsew"); self.welcome_frame.grid_columnconfigure(0, weight=1); self.welcome_frame.grid_rowconfigure(4, weight=1)
        self.welcome_title = ctk.CTkLabel(self.welcome_frame, font=ctk.CTkFont(size=28, weight="bold")); self.welcome_title.grid(row=0, column=0, padx=12, pady=(12, 4))
        self.welcome_tagline = ctk.CTkLabel(self.welcome_frame, font=ctk.CTkFont(size=18, weight="bold"), text_color=("#2469a0", "#65b6ef")); self.welcome_tagline.grid(row=1, column=0, padx=12, pady=(0, 10))
        self.welcome_description1 = ctk.CTkLabel(self.welcome_frame, wraplength=720, justify="center"); self.welcome_description1.grid(row=2, column=0, padx=18, pady=2)
        self.welcome_description2 = ctk.CTkLabel(self.welcome_frame, wraplength=720, justify="center"); self.welcome_description2.grid(row=3, column=0, padx=18, pady=(2, 10))
        self.welcome_illustration = ctk.CTkLabel(self.welcome_frame, anchor="center"); self.welcome_illustration.grid(row=4, column=0, padx=12, pady=(4, 12), sticky="nsew")
        self._load_image_welcome(); self.welcome_frame.bind("<Configure>", self._resize_image_welcome)

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
        self.badge_enable.configure(text=t("pdf.add_badge")); self.single_badge_label.configure(text="2. " + t("badge"))
        self.position_display_to_value = {t("position.top_left"): "top-left", t("position.top_right"): "top-right", t("position.bottom_left"): "bottom-left", t("position.bottom_right"): "bottom-right", t("position.center"): "center"}
        self.position_menu.configure(values=list(self.position_display_to_value)); self.position_display_var.set(next((label for label, value in self.position_display_to_value.items() if value == self.position_var.get()), t("position.bottom_right")))
        self.logo_position_display_to_value = dict(self.position_display_to_value); self.logo_position_menu.configure(values=list(self.logo_position_display_to_value)); self.logo_position_display_var.set(next((label for label, value in self.logo_position_display_to_value.items() if value == self.logo_position_var.get()), t("position.top_left")))
        self.position_label.configure(text="3. " + t("position")); self._update_image_slider_labels()
        self.logo_heading.configure(text=t("logo.title")); self.logo_enable.configure(text=t("logo.enable")); self.logo_choose.configure(text=t("logo.choose")); self.logo_position_label.configure(text=t("logo.position")); self.logo_images_only.configure(text=t("logo.images_only")); self._update_logo_labels(); self._update_logo_controls(); self._update_badge_controls()
        self.welcome_title.configure(text=t("welcome.title")); self.welcome_tagline.configure(text=t("welcome.tagline")); self.welcome_description1.configure(text=t("welcome.description1")); self.welcome_description2.configure(text=t("welcome.description2"))

    def change_image_language(self, name: str) -> None:
        self.translator.set_language(LANGUAGES.get(name, "en")); self.apply_image_translations(); self.refresh_image_badges(); self._save()

    def open_image_guide(self) -> None:
        try: open_user_guide(localized_user_guide_path(self.translator.language))
        except (OSError, FileNotFoundError) as error: messagebox.showerror(self.translator.text("error.title"), self.translator.text("guide.missing", error=error))

    def _update_image_slider_labels(self) -> None:
        t = self.translator.text; self.size_label.configure(text="4. " + t("size.value", value=self.size_var.get())); self.margin_label.configure(text="5. " + t("margin.value", value=self.margin_var.get())); self.opacity_label.configure(text="6. " + t("opacity.value", value=self.opacity_var.get()))

    def changed(self, *_args) -> None:
        self._update_image_slider_labels(); self._update_logo_labels()
        if self.active_content_type == "pdf": self.render_pdf_preview()
        elif self.active_content_type == "pptx": self._update_pptx_preview()
        else: self.update_preview()
        self._save()

    def badge_enabled_changed(self) -> None:
        self._update_badge_controls(); self.update_preview(); self._save()

    def _update_badge_controls(self) -> None:
        enabled = self.badge_enabled_var.get()
        self.badge_menu.configure(state="normal" if enabled else "disabled")
        self.single_badge_preview_label.configure(text="" if enabled else "—", image=self.single_badge_photo if enabled else None)

    def change_position_display(self, label: str) -> None:
        self.position_var.set(self.position_display_to_value[label]); self.changed()

    def change_logo_position(self, label: str) -> None:
        self.logo_position_var.set(self.logo_position_display_to_value[label]); self.logo_changed()

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

    def choose_logo(self) -> None:
        selected = filedialog.askopenfilename(title=self.translator.text("logo.choose"), filetypes=[(self.translator.text("logo.supported"), "*.png *.jpg *.jpeg *.webp"), (self.translator.text("files.all"), "*.*")])
        if not selected: return
        path = Path(selected)
        try:
            with Image.open(path) as opened: opened.verify()
        except (OSError, Image.UnidentifiedImageError):
            messagebox.showerror(self.translator.text("error.title"), self.translator.text("logo.invalid")); return
        self.logo_path_var.set(str(path)); self.logo_enabled_var.set(True); self.logo_changed()

    def logo_changed(self, *_args) -> None:
        if self.logo_enabled_var.get() and not self._logo_path(): self.logo_enabled_var.set(False); self.status_var.set(self.translator.text("logo.missing"))
        self._update_logo_controls(); self.changed()

    def refresh_image_badges(self) -> None:
        self.badges = self.badge_sources.repository(self.badge_source_var.get(), self.custom_badge_var.get())
        names = [path.name for path in self.badges.display_badges()]
        displays = [self.badges.display_name(name) for name in names]; self.badge_display_to_file = dict(zip(displays, names))
        if getattr(self, "badge_menu", None): self.badge_menu.configure(values=displays or [self.translator.text("badge.none")])
        self.badge_var.set(choose_badge_selection(self.badge_source_var.get(), names, self.badge_var.get()))
        self.badge_display_var.set(self.badges.display_name(self.badge_var.get()))
        if getattr(self, "single_badge_preview_label", None): self.update_image_badge_preview()

    def update_image_badge_preview(self) -> None:
        badge = self.badges.find(self.badge_var.get())
        if not badge: self.single_badge_preview_label.configure(image=None, text=self.translator.text("badge.none")); return
        with Image.open(badge) as opened: image = opened.convert("RGBA")
        image.thumbnail((110, 54), Image.Resampling.LANCZOS); self.single_badge_photo = ctk.CTkImage(light_image=image, dark_image=image, size=image.size); self.badge_photo = self.single_badge_photo
        self.single_badge_preview_label.configure(image=self.single_badge_photo, text="")
        info = self.badges.metadata(badge.name); self.badge_name_var.set(info.display_name if info else self.badges.display_name(badge.name))

    def select_badge_display(self, display_name: str) -> None:
        filename = self.badge_display_to_file.get(display_name)
        if filename: self.badge_var.set(filename); self.select_image_badge()

    def select_image_badge(self) -> None:
        self.badge_display_var.set(self.badges.display_name(self.badge_var.get()));
        if getattr(self, "single_badge_preview_label", None): self.update_image_badge_preview()
        if self.active_content_type == "image": self.update_preview()
        elif self.active_content_type == "pdf": self.render_pdf_preview()
        elif self.active_content_type == "pptx": self._update_pptx_preview()
        self._save()

    def open_images(self) -> None:
        selected = filedialog.askopenfilenames(title=self.translator.text("dialog.open_media"), filetypes=[(self.translator.text("files.supported_media"), " ".join(f"*{extension}" for extension in sorted(SUPPORTED_EXTENSIONS))), (self.translator.text("files.all"), "*.*")])
        if not selected: return
        candidates = [Path(path) for path in selected if Path(path).suffix.lower() in SUPPORTED_EXTENSIONS]
        if any(is_above_recommended_size(path) for path in candidates) and not messagebox.askokcancel(self.translator.text("warning.large_title"), self.translator.text("warning.large_file")): return
        self.sources = candidates
        if candidates:
            self.file_label.configure(text=f"{candidates[0].name} · {human_file_size(candidates[0].stat().st_size)}")
        else:
            self.file_label.configure(text=self.translator.text("files.none_supported"))
        self.update_preview()

    def update_preview(self) -> None:
        if not self.sources:
            self.preview_photo = self.preview_image = None; self._show_welcome(); return
        badge = self.badges.find(self.badge_var.get()) if self.badge_enabled_var.get() else None
        logo = self._logo_path() if self.logo_enabled_var.get() else None
        self._show_preview()
        try:
            image = self.preview_renderer.render(self.sources[0], badge, self.settings(), logo)
            self.preview_image = image.copy(); self.preview_photo = ctk.CTkImage(light_image=self.preview_image, dark_image=self.preview_image, size=self.preview_image.size)
            self.preview_label.configure(image=self.preview_photo, text=""); self.preview_label.image = self.preview_photo
        except (OSError, ValueError) as error:
            self.preview_label.configure(image=None, text=self.translator.text("error.preview", error=error))

    def save_images(self) -> None:
        badge = self.badges.find(self.badge_var.get()) if self.badge_enabled_var.get() else None
        logo = self._logo_path() if self.logo_enabled_var.get() else None
        if not self.sources or (badge is None and logo is None):
            messagebox.showwarning(self.translator.text("warning.title"), self.translator.text("warning.nothing_to_save")); return
        saved, failures, metadata_warnings = [], [], []
        metadata = marker_metadata(self.badge_var.get(), self.badge_name_var.get()) if badge else None
        for source in self.sources:
            suggested = source.with_name(f"{source.stem}_ai{source.suffix}")
            selected = filedialog.asksaveasfilename(title=self.translator.text("dialog.save_as"), initialdir=str(source.parent), initialfile=suggested.name, defaultextension=source.suffix, filetypes=[(self.translator.text("files.supported"), f"*{source.suffix}"), (self.translator.text("files.all"), "*.*")], confirmoverwrite=True)
            if not selected: continue
            try:
                written = self.processor.save(self.processor.process(source, badge, self.settings(), logo), Path(selected), metadata)
                saved.append(Path(selected))
                if metadata and not written: metadata_warnings.append(source.name)
            except (OSError, ValueError) as error:
                failures.append(f"{source.name}: {error}")
        summary = self.translator.text("process.summary", saved=len(saved), total=len(self.sources)); self.status_var.set(summary)
        warning = "\n\n" + self.translator.text("warning.metadata_failed") if metadata_warnings else ""
        (messagebox.showerror if failures else messagebox.showinfo)(self.translator.text("error.completed") if failures else self.translator.text("complete.title"), summary + ("\n\n" + "\n".join(failures[:8]) if failures else "") + warning)

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
