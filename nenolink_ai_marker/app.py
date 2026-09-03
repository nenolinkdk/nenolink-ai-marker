from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import subprocess
from tkinter import TclError, filedialog, messagebox
import customtkinter as ctk
from PIL import Image

from . import __version__
from .badges import BadgeSourceManager, choose_badge_selection
from .batch import BatchProcessor, BatchResult, FolderScan, VIDEO_EXTENSIONS, destination_root, find_ffmpeg, hidden_subprocess_kwargs, is_above_recommended_size, scan_folder
from .config import ConfigStore
from .guide import open_user_guide
from .i18n import LANGUAGES, Translator
from .inspection import INSPECT_EXTENSIONS, InspectionResult, human_file_size, inspect_file
from .metadata import marker_metadata
from .models import MarkerSettings
from .paths import badge_directory, locale_directory, localized_user_guide_path, welcome_image_path
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS
from .ui_state import show_welcome


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


class MarkerApp(ctk.CTk):
    def __init__(self) -> None:
        boot_log=os.environ.get("NENOLINK_BOOT_LOG")
        def boot(message):
            if boot_log:
                with open(boot_log,"a",encoding="utf-8") as stream:stream.write(message+"\n")
        self._boot=boot
        boot("MarkerApp init started")
        if getattr(sys, "frozen", False):
            bundle=Path(sys._MEIPASS)  # type: ignore[attr-defined]
            override=os.environ.get("NENOLINK_RUNTIME_ROOT")
            local=Path(override) if override else Path(os.environ.get("LOCALAPPDATA",Path.home()/"AppData"/"Local"))/"Nenolink"/"AI Marker"/"tk-runtime-8.6.13"
            tcl=local/"tcl8.6"; tk=local/"tk8.6"
            if not (tcl/"init.tcl").is_file():shutil.copytree(bundle/"_tcl_data",tcl,dirs_exist_ok=True)
            if not (tk/"tk.tcl").is_file():shutil.copytree(bundle/"_tk_data",tk,dirs_exist_ok=True)
            os.environ["TCL_LIBRARY"]=str(tcl); os.environ["TK_LIBRARY"]=str(tk)
        boot(f"Tk paths ready: {os.environ.get('TCL_LIBRARY')}")
        super().__init__(); boot("CTk initialized")
        self.geometry("1280x720"); self.minsize(980, 680)
        self.processor = ImageProcessor(); self.batch_processor = BatchProcessor(self.processor)
        self.config_store = ConfigStore(); saved = self.config_store.load()
        self.translator = Translator(locale_directory(), saved.language)
        self.badge_sources = BadgeSourceManager(badge_directory())
        self.badges = self.badge_sources.repository(saved.badge_source, saved.custom_badge_folder)
        self.sources: list[Path] = []; self.scan: FolderScan | None = None
        self.inspection_path: Path | None = None; self.inspection_result: InspectionResult | None = None; self.inspection_error = ""
        self._reset_after_id = None
        self.cancel_event = threading.Event(); self.preview_photo = None; self.badge_photo = None; self.single_badge_photo = None; self.welcome_photo = None; self.welcome_image = None
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
        self.status_var=ctk.StringVar(); self.badge_name_var=ctk.StringVar(); self.badge_description_var=ctk.StringVar(); self.badge_display_var=ctk.StringVar()
        self.scan_summary_var=ctk.StringVar(); self.progress_text_var=ctk.StringVar()
        self.inspect_file_var=ctk.StringVar(); self.inspect_format_var=ctk.StringVar(); self.inspect_status_var=ctk.StringVar(); self.inspect_software_var=ctk.StringVar(); self.inspect_label_var=ctk.StringVar(); self.inspect_version_var=ctk.StringVar(); self.inspect_message_var=ctk.StringVar()
        self._build_ui(); boot("UI built"); self.apply_translations(); self.refresh_badges(False); boot("resources loaded"); self.protocol("WM_DELETE_WINDOW", self.destroy)
        if os.environ.get("NENOLINK_VERIFY_FILE_DIALOG") == "1":
            self.after(800, self.open_images)
        if os.environ.get("NENOLINK_VERIFY_BADGE_FOLDER_DIALOG") == "1":
            self.after(800, self.browse_custom_badges)
        if os.environ.get("NENOLINK_VERIFY_REPORT"):
            self.after(800, self._write_hotfix_verification)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0,weight=1); self.grid_rowconfigure(1,weight=1)
        header=ctk.CTkFrame(self,corner_radius=0); header.grid(row=0,column=0,sticky="ew"); header.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(header,text="Nenolink AI Marker",font=ctk.CTkFont(size=24,weight="bold")).grid(row=0,column=0,padx=20,pady=14)
        self.language_menu=ctk.CTkOptionMenu(header,variable=self.language_var,values=list(LANGUAGES),command=self.change_language,width=150); self.language_menu.grid(row=0,column=2,padx=8)
        self.reset_button=ctk.CTkButton(header,text="",command=self.reset_application,width=100); self.reset_button.grid(row=0,column=3,padx=8)
        self.guide_button=ctk.CTkButton(header,text="",command=self.open_guide,width=170); self.guide_button.grid(row=0,column=4,padx=(8,20))
        self.tabs=ctk.CTkTabview(self); self.tabs.grid(row=1,column=0,padx=16,pady=12,sticky="nsew")
        self.tab_names={"single":self.translator.text("tab.single"),"batch":self.translator.text("tab.batch"),"badges":self.translator.text("tab.badges"),"inspect":self.translator.text("tab.inspect")}
        self.single_tab=self.tabs.add(self.tab_names["single"]); self.batch_tab=self.tabs.add(self.tab_names["batch"]); self.settings_tab=self.tabs.add(self.tab_names["badges"]); self.inspect_tab=self.tabs.add(self.tab_names["inspect"])
        self._single_ui(); self._batch_ui(); self._settings_ui(); self._inspect_ui()
        footer=ctk.CTkFrame(self,corner_radius=0,fg_color="transparent"); footer.grid(row=2,column=0,padx=20,pady=(0,8),sticky="ew"); footer.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(footer,text="(c) Copyright Henrik Nielsen - nenolink.com",text_color="gray60").grid(row=0,column=0,sticky="w")
        self.status_label=ctk.CTkLabel(footer,textvariable=self.status_var,text_color="gray60",anchor="e"); self.status_label.grid(row=0,column=1,padx=(20,0),sticky="ew")

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
        self.video_controls=ctk.CTkFrame(left,fg_color="transparent"); self.video_controls.grid(row=14,column=0,padx=14,pady=(2,0),sticky="ew"); self.video_controls.grid_columnconfigure(1,weight=1)
        self.video_settings_heading=ctk.CTkLabel(self.video_controls,text="",font=ctk.CTkFont(weight="bold")); self.video_settings_heading.grid(row=0,column=0,columnspan=3,pady=(2,0),sticky="w")
        self.video_mode_label=ctk.CTkLabel(self.video_controls,text=""); self.video_mode_label.grid(row=1,column=0,columnspan=3,sticky="w")
        self.video_mode_menu=ctk.CTkOptionMenu(self.video_controls,variable=self.video_mode_display_var,values=["—"],command=self.change_video_mode); self.video_mode_menu.grid(row=2,column=0,columnspan=3,pady=(1,3),sticky="ew")
        self.video_duration_label=ctk.CTkLabel(self.video_controls,text=""); self.video_duration_label.grid(row=3,column=0,pady=2,sticky="w")
        self.video_duration_entry=ctk.CTkEntry(self.video_controls,textvariable=self.video_duration_var,width=58); self.video_duration_entry.grid(row=3,column=1,padx=(8,4),pady=2,sticky="e"); self.video_duration_entry.bind("<FocusOut>",self.changed)
        self.video_seconds_label=ctk.CTkLabel(self.video_controls,text=""); self.video_seconds_label.grid(row=3,column=2,pady=2,sticky="w")
        self.process_button=ctk.CTkButton(left,text="",command=self.save_images); self.process_button.grid(row=15,column=0,padx=14,pady=(6,10),sticky="ew")
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
        self.preview_photo=None; self.preview_label.configure(image=None,text=""); self.preview_label.grid_remove()
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
        source=ctk.CTkFrame(tab); self.badge_source_frame=source; source.grid(row=0,column=0,padx=16,pady=(14,6),sticky="ew"); source.grid_columnconfigure(0,weight=1)
        self.badges_back_button=ctk.CTkButton(tab,text="",command=self.navigate_home,width=110); self.badges_back_button.grid(row=0,column=1,padx=(0,16),pady=(14,6),sticky="ne")
        self.badge_source_heading=ctk.CTkLabel(source,text="",font=ctk.CTkFont(weight="bold")); self.badge_source_heading.grid(row=0,column=0,padx=12,pady=(10,4),sticky="w")
        self.standard_badge_radio=ctk.CTkRadioButton(source,text="",variable=self.badge_source_var,value="standard",command=self.change_badge_source); self.standard_badge_radio.grid(row=1,column=0,padx=16,pady=4,sticky="w")
        self.custom_badge_radio=ctk.CTkRadioButton(source,text="",variable=self.badge_source_var,value="custom",command=self.change_badge_source); self.custom_badge_radio.grid(row=2,column=0,padx=16,pady=4,sticky="w")
        self.custom_controls=ctk.CTkFrame(source,fg_color="transparent"); self.custom_controls.grid(row=3,column=0,padx=16,pady=(4,10),sticky="ew"); self.custom_controls.grid_columnconfigure(0,weight=1)
        self.custom_folder_label=ctk.CTkLabel(self.custom_controls,text=""); self.custom_folder_label.grid(row=0,column=0,columnspan=2,sticky="w")
        self.custom_entry=ctk.CTkEntry(self.custom_controls,textvariable=self.custom_badge_var); self.custom_entry.grid(row=1,column=0,padx=(0,8),pady=4,sticky="ew")
        self.choose_badge_folder_button=ctk.CTkButton(self.custom_controls,text="",command=self.browse_custom_badges); self.choose_badge_folder_button.grid(row=1,column=1,padx=4,pady=4)
        self.refresh_button=ctk.CTkButton(self.custom_controls,text="",command=self.refresh_badges); self.refresh_button.grid(row=1,column=2,padx=(4,0),pady=4)
        self.badge_help=ctk.CTkLabel(tab,text="",justify="left",anchor="w",wraplength=1050); self.badge_help.grid(row=1,column=0,columnspan=2,padx=20,pady=4,sticky="ew")
        self.badge_gallery_title=ctk.CTkLabel(tab,text="",font=ctk.CTkFont(size=18,weight="bold")); self.badge_gallery_title.grid(row=2,column=0,columnspan=2,padx=16,pady=(10,2),sticky="w")
        self.gallery=ctk.CTkScrollableFrame(tab); self.gallery.grid(row=3,column=0,columnspan=2,padx=16,pady=(4,14),sticky="nsew")
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
        t=self.translator.text; self.title(f"Nenolink AI Marker {__version__} - {t('app.window')}"); self.guide_button.configure(text=t("button.user_guide")); self.reset_button.configure(text=t("button.reset")); self.batch_back_button.configure(text=t("button.back")); self.badges_back_button.configure(text=t("button.back")); self.inspect_back_button.configure(text=t("button.back"))
        current_key=next((key for key,name in self.tab_names.items() if name==self.tabs.get()),"single")
        for key,translation_key in (("single","tab.single"),("batch","tab.batch"),("badges","tab.badges"),("inspect","tab.inspect")):
            new=t(translation_key); old=self.tab_names[key]
            if old != new:self.tabs.rename(old,new); self.tab_names[key]=new
        self.tabs.set(self.tab_names[current_key])
        self.open_button.configure(text="1. "+t("button.open_media")); self.process_button.configure(text=t("button.process_video") if self.sources and self.sources[0].suffix.lower() in VIDEO_EXTENSIONS else t("button.process")); self.file_label.configure(text=t("files.none") if not self.sources else t("files.selected",count=len(self.sources),name=self.sources[0].name))
        self.file_size_guidance.configure(text=t("files.size_guidance")); self.batch_size_guidance.configure(text=t("files.size_guidance_short"))
        self.video_mode_display_to_value={t("video.mode.permanent"):"permanent",t("video.mode.beginning"):"beginning",t("video.mode.end"):"end"}
        video_values=list(self.video_mode_display_to_value); self.video_mode_menu.configure(values=video_values); self.batch_video_mode_menu.configure(values=video_values)
        self.video_mode_display_var.set(next((label for label,value in self.video_mode_display_to_value.items() if value==self.video_mode_var.get()),t("video.mode.permanent")))
        self.video_settings_heading.configure(text=t("video.settings")); self.batch_video_settings_heading.configure(text=t("video.settings")); self.video_mode_label.configure(text=t("video.badge")); self.batch_video_mode_label.configure(text=t("video.badge")); self._update_video_duration_controls()
        self.position_label.configure(text="3. "+t("position")); self.size_label.configure(text="4. "+t("size.value",value=self.size_var.get())); self.margin_label.configure(text="5. "+t("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text="6. "+t("opacity.value",value=self.opacity_var.get()))
        self.single_badge_label.configure(text="2. "+t("badge")); self.badge_source_heading.configure(text=t("badge.source_label")); self.standard_badge_radio.configure(text=t("badge.source_standard")); self.custom_badge_radio.configure(text=t("badge.source_custom")); self.custom_folder_label.configure(text=t("badge.custom_path")+":"); self.custom_entry.configure(placeholder_text=t("badge.custom_path"))
        self.position_display_to_value={t("position.top_left"):"top-left",t("position.top_right"):"top-right",t("position.bottom_left"):"bottom-left",t("position.bottom_right"):"bottom-right",t("position.center"):"center"}; self.position_menu.configure(values=list(self.position_display_to_value)); self.position_display_var.set(next((label for label,value in self.position_display_to_value.items() if value==self.position_var.get()),t("position.bottom_right")))
        self.choose_badge_folder_button.configure(text=t("button.choose_badge_folder")); self.refresh_button.configure(text=t("badge.refresh")); self.badge_gallery_title.configure(text=t("badge.gallery")); self.badge_help.configure(text=t("badge.help")); self._show_badge_source_controls()
        self.batch_title.configure(text=t("tab.batch")); self.input_label.configure(text=t("batch.input")); self.batch_output_heading.configure(text=t("batch.output")); self.batch_badge_heading.configure(text=t("badge")); self.batch_options_heading.configure(text=t("batch.options")); self.batch_progress_heading.configure(text=t("batch.progress_heading")); self.choose_input_button.configure(text=t("button.choose_input")); self.choose_output_button.configure(text=t("button.choose_output")); self.output_subfolder_radio.configure(text=t("batch.output_subfolder")); self.output_separate_radio.configure(text=t("batch.output_separate")); self.batch_suffix_label.configure(text=t("batch.filename_suffix"))
        self.welcome_title.configure(text=t("welcome.title")); self.welcome_tagline.configure(text=t("welcome.tagline")); self.welcome_description1.configure(text=t("welcome.description1")); self.welcome_description2.configure(text=t("welcome.description2"))
        for key,check in self.batch_checks: check.configure(text=t(key))
        self.scan_button.configure(text=t("button.scan_folder")); self.start_batch_button.configure(text=t("button.start_batch")); self.cancel_batch_button.configure(text=t("button.cancel_batch"))
        self.inspect_title.configure(text=t("inspect.title")); self.inspect_intro.configure(text=t("inspect.intro")); self.inspect_choose_button.configure(text=t("inspect.choose")); self.inspect_selected_heading.configure(text=t("inspect.selected")); self.inspect_file_label.configure(text=t("inspect.file")); self.inspect_format_label.configure(text=t("inspect.format_size")); self.inspect_metadata_heading.configure(text=t("inspect.metadata")); self.inspect_status_label.configure(text=t("inspect.status")); self.inspect_software_label.configure(text=t("inspect.software")); self.inspect_ai_label.configure(text=t("inspect.ai_label")); self.inspect_marker_version_label.configure(text=t("inspect.marker_version")); self._render_inspection()

    def change_language(self,name): self.translator.set_language(LANGUAGES.get(name,"en")); self.apply_translations(); self._save()
    def show_tab(self,key): self.tabs.set(self.tab_names[key])
    def navigate_home(self): self.show_tab("single")
    def choose_inspection_file(self):
        patterns=" ".join(f"*{extension}" for extension in sorted(INSPECT_EXTENSIONS))
        selected=filedialog.askopenfilename(title=self.translator.text("inspect.choose"),filetypes=[(self.translator.text("inspect.supported"),patterns),(self.translator.text("files.all"),"*.*")])
        if not selected:return
        self.inspection_path=Path(selected); self.inspection_result=None; self.inspection_error=""
        try:self.inspection_result=inspect_file(self.inspection_path)
        except (OSError,ValueError) as error:self.inspection_error=str(error)
        self._render_inspection()
    def _render_inspection(self):
        if not hasattr(self,"inspect_file_var"):return
        t=self.translator.text; missing=t("inspect.not_available")
        self.inspect_file_var.set(self.inspection_path.name if self.inspection_path else t("inspect.none"))
        if self.inspection_result:
            result=self.inspection_result; self.inspect_format_var.set(f"{result.media_format} · {human_file_size(result.size)}"); self.inspect_status_var.set(t("inspect.found") if result.found else t("inspect.not_found")); self.inspect_software_var.set(result.software or missing); self.inspect_label_var.set(result.ai_label or missing); self.inspect_version_var.set(result.marker_version or missing); self.inspect_message_var.set(t("inspect.info") if result.found else t("inspect.not_found_message")+"\n"+t("inspect.no_ai_warning"))
        elif self.inspection_error:
            suffix=self.inspection_path.suffix.lower().lstrip(".").upper() if self.inspection_path else ""; size=human_file_size(self.inspection_path.stat().st_size) if self.inspection_path and self.inspection_path.is_file() else ""; self.inspect_format_var.set(" · ".join(value for value in (suffix,size) if value)); self.inspect_status_var.set(t("inspect.error")); self.inspect_software_var.set(missing); self.inspect_label_var.set(missing); self.inspect_version_var.set(missing); self.inspect_message_var.set(t("inspect.error_message",reason=self.inspection_error))
        else:
            self.inspect_format_var.set(""); self.inspect_status_var.set(t("inspect.ready")); self.inspect_software_var.set(missing); self.inspect_label_var.set(missing); self.inspect_version_var.set(missing); self.inspect_message_var.set(t("inspect.no_ai_warning"))
    def reset_application(self):
        defaults=MarkerSettings(); custom_folder=self.custom_badge_var.get()
        self.sources=[]; self.preview_photo=None; self.video_controls.grid_remove()
        self.badge_source_var.set("standard"); self.custom_badge_var.set(custom_folder); self.badge_var.set(defaults.badge_name); self.position_var.set(defaults.position)
        self.size_var.set(defaults.size_percent); self.margin_var.set(defaults.margin); self.opacity_var.set(defaults.opacity)
        self.batch_suffix_var.set(defaults.batch_filename_suffix)
        self.video_mode_var.set(defaults.video_mode); self.video_duration_var.set(defaults.video_duration)
        self.scan=None; self.cancel_event.clear(); self.scan_summary_var.set(""); self.progress_text_var.set(""); self.progress.set(0)
        self.inspection_path=None; self.inspection_result=None; self.inspection_error=""; self._render_inspection()
        self.refresh_badges(False); self.apply_translations(); self.file_label.configure(text=self.translator.text("files.none")); self.render_start_view()
        if self._reset_after_id:self.after_cancel(self._reset_after_id)
        self._reset_after_id=self.after(150,self._finish_reset_view); self.status_var.set(self.translator.text("status.reset")); self._save()
    def changed(self,*_):
        try:self.video_duration_var.set(max(1,int(self.video_duration_var.get())))
        except (ValueError,TypeError):self.video_duration_var.set(5)
        self.size_label.configure(text="4. "+self.translator.text("size.value",value=self.size_var.get())); self.margin_label.configure(text="5. "+self.translator.text("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text="6. "+self.translator.text("opacity.value",value=self.opacity_var.get())); self.update_preview(); self._save()
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
    def change_badge_source(self): self._show_badge_source_controls(); self.refresh_badges(); self._save()
    def _show_badge_source_controls(self):
        if self.badge_source_var.get()=="custom":self.custom_controls.grid()
        else:self.custom_controls.grid_remove()
    def select_badge(self):
        self.badge_display_var.set(self.badges.display_name(self.badge_var.get()))
        self.update_badge_preview(); self.update_gallery_selection(); self.update_preview(); self._save()
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
        displays=[self.badges.display_name(name) for name in names]; self.badge_display_to_file=dict(zip(displays,names)); self.badge_menu.configure(values=displays or [self.translator.text("badge.none")])
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
                image.thumbnail((145,62),Image.Resampling.LANCZOS); photo=ctk.CTkImage(light_image=image,dark_image=image,size=image.size); self.gallery_photos.append(photo)
                button=ctk.CTkButton(self.gallery,text=self.badges.display_name(badge.name),image=photo,compound="top",height=112,fg_color="transparent",border_width=1,command=lambda name=badge.name:self.select_gallery_badge(name))
                button.grid(row=index//5,column=index%5,padx=8,pady=8,sticky="nsew"); self.gallery_buttons[badge.name]=button
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
            info=self.badges.metadata(badge.name); self.badge_name_var.set(info.display_name if info else self.badges.display_name(badge.name)); self.badge_description_var.set(info.description if info else self.translator.text("badge.custom_description"))
        except OSError as error:self.single_badge_preview_label.configure(image=None,text=str(error))

    def open_images(self):
        selected=filedialog.askopenfilenames(title=self.translator.text("dialog.open_media"),filetypes=[(self.translator.text("files.supported_media"),"*.jpg *.jpeg *.png *.webp *.mp4 *.mov *.mkv *.avi *.webm"),(self.translator.text("files.all"),"*.*")])
        if selected:
            candidates=[Path(p) for p in selected if Path(p).suffix.lower() in SUPPORTED_EXTENSIONS|VIDEO_EXTENSIONS]
            if any(is_above_recommended_size(p) for p in candidates) and not messagebox.askokcancel(self.translator.text("warning.large_title"),self.translator.text("warning.large_file")):return
            self.sources=candidates; self.file_label.configure(text=self.translator.text("files.selected",count=len(self.sources),name=self.sources[0].name) if self.sources else self.translator.text("files.none_supported")); self.process_button.configure(text=self.translator.text("button.process_video") if self.sources and self.sources[0].suffix.lower() in VIDEO_EXTENSIONS else self.translator.text("button.process")); self.video_controls.grid() if self.sources and self.sources[0].suffix.lower() in VIDEO_EXTENSIONS else self.video_controls.grid_remove(); self.update_preview()

    def update_preview(self):
        badge=self.badges.find(self.badge_var.get())
        if show_welcome(self.sources):self.preview_photo=None; self._show_welcome(); return
        self._show_preview()
        if not badge:self.preview_label.configure(image=None,text=self.translator.text("badge.none")); return
        if self.sources[0].suffix.lower() in VIDEO_EXTENSIONS:
            self.preview_photo=None; self.preview_label.configure(image=None,text=self.translator.text("preview.video_selected",name=self.sources[0].name)); self.status_var.set(self.translator.text("preview.video_selected",name=self.sources[0].name)); return
        try:
            image=self.processor.process(self.sources[0],badge,self.settings()); image.thumbnail((720,600),Image.Resampling.LANCZOS); self.preview_photo=ctk.CTkImage(light_image=image,dark_image=image,size=image.size); self.preview_label.configure(image=self.preview_photo,text=""); self.status_var.set(self.translator.text("preview.showing",name=self.sources[0].name))
        except (OSError,ValueError) as error:self.status_var.set(self.translator.text("error.preview",error=error))

    def clear_images(self):
        self.sources=[]; self.file_label.configure(text=self.translator.text("files.none")); self.update_preview()

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
                else:metadata_written=self.processor.save(self.processor.process(source,badge,self.settings()),target,metadata)
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
        release_regressions={"inspect_then_image":False,"selected_image_inspect_back":False,"inspect_reset_then_image":False,"selected_video_inspect_back":False}
        initial_badge_settings={"source":self.badge_source_var.get(),"folder":self.custom_badge_var.get(),"selection":self.badge_var.get(),"batch_suffix":self.batch_suffix_var.get(),"video_mode":self.video_mode_var.get(),"video_duration":self.video_duration_var.get(),"status":self.status_var.get(),"count":len(self.badges.display_badges()),"custom_controls_visible":self.custom_controls.winfo_manager()=="grid"}
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
            metadata=marker_metadata("ai-localization.png","AI Localization")
            jpeg_output=metadata_root/"sample_ai.jpg"; png_output=metadata_root/"sample_ai.png"; webp_output=metadata_root/"sample_ai.webp"
            jpeg_written=self.processor.save(localization,jpeg_output,metadata)
            png_written=self.processor.save(localization,png_output,metadata)
            webp_written=self.processor.save(localization,webp_output,metadata)
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
            image_metadata_verification={"source_sha256_before":sample_hash,"source_sha256_after":hashlib.sha256(sample_path.read_bytes()).hexdigest(),"jpeg":{"path":str(jpeg_output),"written":jpeg_written,"values":jpeg_values,"inspected":inspected["jpg"].found,"label":inspected["jpg"].ai_label,"version":inspected["jpg"].marker_version},"png":{"path":str(png_output),"written":png_written,"values":png_values,"inspected":inspected["png"].found,"label":inspected["png"].ai_label},"webp":{"path":str(webp_output),"written":webp_written,"values":webp_values,"inspected":inspected["webp"].found},"ordinary_not_found":not ordinary.found,"inspect_back_preserved":inspect_back_preserved}
        self.select_gallery_badge("ai-software.png"); gallery_selection_persisted=self.badge_var.get()=="ai-software.png" and self.badge_display_var.get()=="AI Software"
        custom_verification=None
        custom_folder=os.environ.get("NENOLINK_VERIFY_CUSTOM_BADGES")
        if custom_folder:
            self.custom_badge_var.set(custom_folder); self.badge_source_var.set("custom"); self.refresh_badges(False); self.update()
            custom_paths=self.badges.display_badges(); custom_names=[path.name for path in custom_paths]
            custom_displays=[self.badges.display_name(path.name) for path in custom_paths]
            if custom_paths:
                chosen=custom_paths[-1]; self.select_gallery_badge(chosen.name); self.update()
                if sample:self.sources=[Path(sample)]; self.update_preview(); self.update()
                output=report_path.with_name("verified-custom-output.png")
                processed=self.processor.process(Path(sample),chosen,self.settings()) if sample else None
                if processed is not None:self.processor.save(processed,output,marker_metadata(chosen.name,self.badges.display_name(chosen.name)))
                custom_metadata=None
                if output.is_file():
                    with Image.open(output) as checked:custom_metadata={key:checked.info.get(key) for key in ("Software","AI Label","Marker Version","NenolinkAIMarker")}
                selected_custom=self.badge_var.get(); retained_custom=self.custom_badge_var.get(); retained_sources=list(self.sources); self.show_tab("badges"); self.update(); self.badges_back_button.invoke(); self.update(); time.sleep(.15); self.update()
                custom_back_preserved=self.tabs.get()==self.tab_names["single"] and self.badge_source_var.get()=="custom" and self.badge_var.get()==selected_custom and self.custom_badge_var.get()==retained_custom and self.sources==retained_sources
                custom_verification={"files":custom_names,"displays":custom_displays,"selected":self.badge_var.get(),"selector_values":list(self.badge_menu.cget("values")),"gallery_badges":len(self.gallery_buttons),"preview":bool(self.preview_photo),"output_saved":output.is_file(),"metadata":custom_metadata,"status":self.status_var.get(),"source_controls_visible":self.custom_controls.winfo_manager()=="grid","back_preserved":custom_back_preserved}
        guide_paths={code:localized_user_guide_path(code) for code in ("da","en","fr")}
        guide_language=os.environ.get("NENOLINK_VERIFY_GUIDE_LANGUAGE","en").lower()
        guide=localized_user_guide_path(guide_language); guide_opened=False
        if os.environ.get("NENOLINK_VERIFY_OPEN_GUIDE") == "1":
            try:open_user_guide(guide); guide_opened=True
            except OSError:guide_opened=False
        payload={"version":__version__,"english":english,"danish":danish,"german":german,"french":french,"initial_badge_settings":initial_badge_settings,"welcome_before_image":welcome_before_image,"welcome_illustration":welcome_illustration,"welcome_hidden_after_image":(not sample or self.welcome_frame.winfo_manager()==""),"badges_found":len(badge_names),"badge_selector_visible":self.badge_menu.winfo_manager()=="grid","badge_selector_values":list(self.badge_menu.cget("values")),"gallery_badges":len(self.gallery_buttons),"gallery_selection_persisted":gallery_selection_persisted,"badges_tab_is_distinct":self.badge_source_frame.master is self.settings_tab,"selected_badges":selected,"image_preview":bool(self.preview_photo),"selected_badge_written":selected_badge_written,"image_metadata_verification":image_metadata_verification,"custom_verification":custom_verification,"friendly_status":("_MEI" not in self.status_var.get() and "assets" not in self.status_var.get()),"process_button_state":self.process_button.cget("state"),"guide_language":guide_language,"guide_filename":guide.name,"guide_paths":{code:path.name for code,path in guide_paths.items()},"guide_exists":guide.is_file(),"guide_opened":guide_opened,"translation_keys_visible":any("." in str(value) and " " not in str(value) for group in (english,danish,german,french) for value in group.values() if isinstance(value,str))}
        ffmpeg_path=find_ffmpeg(); payload["ffmpeg_found"]=bool(ffmpeg_path); payload["ffmpeg_path"]=ffmpeg_path
        video_source=os.environ.get("NENOLINK_VERIFY_VIDEO")
        if video_source and ffmpeg_path:
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
            self.batch_processor.process_video(video_source_path,standard.find(settings_b.badge_name),output_b,settings_b)
            self.batch_processor.process_video(video_source_path,standard.find(settings_c.badge_name),output_c,settings_c)
            self.batch_processor.process_video(video_source_path,standard.find(settings_d.badge_name),output_d,settings_d)
            mov_output=video_root/f"{video_source_path.stem}_ai.mov"
            self.batch_processor.process_video(video_source_path,standard.find(settings_c.badge_name),mov_output,settings_c)
            batch_input=video_root/"batch-input"; batch_output=video_root/"batch-output"; batch_input.mkdir(exist_ok=True)
            shutil.copy2(video_source_path,batch_input/"clip01.mp4"); shutil.copy2(video_source_path,batch_input/"clip02.mp4")
            batch_settings=MarkerSettings(badge_name="ai-generated.png",position="top-right",size_percent=25,margin=30,opacity=75,process_images=False,process_videos=True,output_preference="separate",output_folder=str(batch_output),batch_filename_suffix="_ai",video_mode="end",video_duration=5)
            batch_result=self.batch_processor.process(scan_folder(batch_input),standard.find(batch_settings.badge_name),batch_settings)
            inspected_mp4=inspect_file(output_c); inspected_mov=inspect_file(mov_output); ordinary_video_hash=hashlib.sha256(video_source_path.read_bytes()).hexdigest(); ordinary_video=inspect_file(video_source_path)
            self.sources=[video_source_path]; self.inspection_path=output_c; self.inspection_result=inspected_mp4; self._render_inspection(); self.show_tab("inspect"); self.update(); self.inspect_back_button.invoke(); self.update()
            regression_video=video_root/"inspect-back-regression.mp4"; self.batch_processor.process_video(video_source_path,standard.find(settings_c.badge_name),regression_video,settings_c)
            release_regressions["selected_video_inspect_back"]=self.sources==[video_source_path] and regression_video.is_file()
            version=subprocess.run([ffmpeg_path,"-version"],capture_output=True,text=True,**hidden_subprocess_kwargs()).stdout.splitlines()[0]
            payload["video_verification"]={"ffmpeg_version":version,"suggested_name":f"{video_source_path.stem}_ai{video_source_path.suffix}","outputs":{"permanent":str(output_a),"beginning5":str(output_b),"end5":str(output_c),"end10":str(output_d),"mov":str(mov_output)},"all_outputs_exist":all(path.is_file() for path in (output_a,output_b,output_c,output_d,mov_output)),"mp4_inspection":{"found":inspected_mp4.found,"software":inspected_mp4.software,"label":inspected_mp4.ai_label,"version":inspected_mp4.marker_version},"mov_inspection":{"found":inspected_mov.found,"software":inspected_mov.software,"label":inspected_mov.ai_label,"version":inspected_mov.marker_version},"ordinary_not_found":not ordinary_video.found,"source_sha256_before":ordinary_video_hash,"source_sha256_after":hashlib.sha256(video_source_path.read_bytes()).hexdigest(),"settings":[{"badge":s.badge_name,"mode":s.video_mode,"duration":s.video_duration,"position":s.position,"size":s.size_percent,"margin":s.margin,"opacity":s.opacity} for s in (settings_a,settings_b,settings_c,settings_d)],"batch_mode":batch_settings.video_mode,"batch_duration":batch_settings.video_duration,"batch_badge":batch_settings.badge_name,"batch_successful":batch_result.successful,"batch_metadata_warnings":batch_result.metadata_warnings,"batch_outputs":sorted(path.name for path in batch_output.glob("*.mp4"))}
        payload["tab_switching"]=tab_switching
        payload["back_navigation"]={"badges_preserved":badges_back_preserved,"batch_preserved":batch_back_preserved,"english_label":english["back"],"danish_label":danish["back"]}
        if os.environ.get("NENOLINK_VERIFY_RESET_LANGUAGE")=="da":self.change_language("Dansk")
        retained_custom_folder=self.custom_badge_var.get(); self.reset_application(); self.update(); time.sleep(.2); self.update()
        payload["reset_verification"]={"source":self.badge_source_var.get(),"selection":self.badge_var.get(),"folder_retained":self.custom_badge_var.get()==retained_custom_folder,"position":self.position_var.get(),"size":self.size_var.get(),"margin":self.margin_var.get(),"opacity":self.opacity_var.get(),"video_mode":self.video_mode_var.get(),"video_duration":self.video_duration_var.get(),"batch_suffix":self.batch_suffix_var.get(),"sources":len(self.sources),"scan_cleared":self.scan is None,"inspection_cleared":self.inspection_path is None and self.inspection_result is None and not self.inspection_error,"single_selected":self.tabs.get()==self.tab_names["single"],"welcome":self.welcome_frame.winfo_manager()=="grid","welcome_mapped":bool(self.welcome_frame.winfo_ismapped()),"welcome_title":self.welcome_title.cget("text"),"welcome_illustration":bool(self.welcome_photo and self.welcome_illustration.winfo_ismapped()),"preview_hidden":not bool(self.preview_label.winfo_ismapped()),"status":self.status_var.get()}
        if sample:
            after_reset=self.processor.process(Path(sample),self.badges.find("ai-assisted.png"),self.settings())
            release_regressions["inspect_reset_then_image"]=bool(after_reset.width and after_reset.height)
        payload["release_regressions"]=release_regressions
        report_path.write_text(json.dumps(payload,indent=2),encoding="utf-8"); self.destroy()

    def settings(self):
        return MarkerSettings(badge_name=self.badge_var.get(),position=self.position_var.get(),size_percent=self.size_var.get(),margin=self.margin_var.get(),opacity=self.opacity_var.get(),language=self.translator.language,badge_source=self.badge_source_var.get(),custom_badge_folder=self.custom_badge_var.get(),input_folder=self.input_folder_var.get(),output_preference=self.output_preference_var.get(),output_folder=self.output_folder_var.get(),output_subfolder=self.output_subfolder_var.get(),include_subfolders=self.recursive_var.get(),preserve_folder_structure=self.preserve_var.get(),process_images=self.images_var.get(),process_videos=self.videos_var.get(),skip_processed=self.skip_var.get(),video_mode=self.video_mode_var.get(),video_duration=self.video_duration_var.get(),batch_filename_suffix=self.batch_suffix_var.get()).validated()
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


def run():
    ctk.set_appearance_mode("system"); ctk.set_default_color_theme("blue"); MarkerApp().mainloop()
