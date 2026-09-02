from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import sys
import threading
import time
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image

from . import __version__
from .badges import BadgeSourceManager, choose_badge_selection
from .batch import BatchProcessor, BatchResult, FolderScan, VIDEO_EXTENSIONS, destination_root, is_above_recommended_size, scan_folder
from .config import ConfigStore
from .guide import open_user_guide
from .i18n import LANGUAGES, Translator
from .models import MarkerSettings
from .paths import badge_directory, locale_directory, localized_user_guide_path, welcome_image_path
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS
from .ui_state import show_welcome


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
        self.status_var=ctk.StringVar(); self.badge_name_var=ctk.StringVar(); self.badge_description_var=ctk.StringVar(); self.badge_display_var=ctk.StringVar()
        self.scan_summary_var=ctk.StringVar(); self.progress_text_var=ctk.StringVar()
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
        self.tab_names={"single":self.translator.text("tab.single"),"batch":self.translator.text("tab.batch"),"badges":self.translator.text("tab.badges")}
        self.single_tab=self.tabs.add(self.tab_names["single"]); self.batch_tab=self.tabs.add(self.tab_names["batch"]); self.settings_tab=self.tabs.add(self.tab_names["badges"])
        self._single_ui(); self._batch_ui(); self._settings_ui()
        footer=ctk.CTkFrame(self,corner_radius=0,fg_color="transparent"); footer.grid(row=2,column=0,padx=20,pady=(0,8),sticky="ew"); footer.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(footer,text="(c) Copyright Henrik Nielsen - nenolink.com",text_color="gray60").grid(row=0,column=0,sticky="w")
        self.status_label=ctk.CTkLabel(footer,textvariable=self.status_var,text_color="gray60",anchor="e"); self.status_label.grid(row=0,column=1,padx=(20,0),sticky="ew")

    def _single_ui(self) -> None:
        tab=self.single_tab; tab.grid_columnconfigure(1,weight=1); tab.grid_rowconfigure(0,weight=1)
        left=ctk.CTkFrame(tab,width=310); left.grid(row=0,column=0,padx=(4,8),pady=4,sticky="ns"); left.grid_columnconfigure(0,weight=1)
        self.open_button=ctk.CTkButton(left,text="",command=self.open_images); self.open_button.grid(row=0,column=0,padx=16,pady=(14,6),sticky="ew")
        self.file_label=ctk.CTkLabel(left,text="",wraplength=280,justify="left"); self.file_label.grid(row=1,column=0,padx=16,pady=6,sticky="w")
        self.file_size_guidance=ctk.CTkLabel(left,text="",wraplength=280,justify="left",text_color="gray60"); self.file_size_guidance.grid(row=2,column=0,padx=16,pady=(0,4),sticky="w")
        self.single_badge_label=ctk.CTkLabel(left,text="",font=ctk.CTkFont(weight="bold")); self.single_badge_label.grid(row=3,column=0,padx=16,pady=(6,2),sticky="w")
        self.badge_menu=ctk.CTkOptionMenu(left,variable=self.badge_display_var,values=["—"],command=self.select_badge_display); self.badge_menu.grid(row=4,column=0,padx=16,pady=4,sticky="ew")
        badge_preview=ctk.CTkFrame(left); badge_preview.grid(row=5,column=0,padx=16,pady=6,sticky="ew"); badge_preview.grid_columnconfigure(1,weight=1)
        self.single_badge_preview_label=ctk.CTkLabel(badge_preview,text="",width=110,height=54); self.single_badge_preview_label.grid(row=0,column=0,padx=8,pady=8)
        self.single_badge_name_label=ctk.CTkLabel(badge_preview,textvariable=self.badge_name_var,font=ctk.CTkFont(weight="bold"),anchor="w"); self.single_badge_name_label.grid(row=0,column=1,padx=(4,8),pady=8,sticky="ew")
        self.position_label=ctk.CTkLabel(left,text=""); self.position_label.grid(row=6,column=0,padx=16,pady=(8,2),sticky="w")
        self.position_menu=ctk.CTkOptionMenu(left,variable=self.position_display_var,values=["—"],command=self.change_position_display); self.position_menu.grid(row=7,column=0,padx=16,pady=4,sticky="ew")
        self.size_label=self._slider(left,self.size_var,1,100,8); self.margin_label=self._slider(left,self.margin_var,0,250,10); self.opacity_label=self._slider(left,self.opacity_var,0,100,12)
        self.process_button=ctk.CTkButton(left,text="",command=self.save_images); self.process_button.grid(row=14,column=0,padx=16,pady=12,sticky="ew")
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
        self.render_start_view(); self.status_var.set(self.translator.text("status.reset"))

    def _slider(self,parent,var,start,end,row):
        label=ctk.CTkLabel(parent,text=""); label.grid(row=row,column=0,padx=16,pady=(8,0),sticky="w")
        ctk.CTkSlider(parent,from_=start,to=end,number_of_steps=end-start,variable=var,command=self.changed).grid(row=row+1,column=0,padx=16,pady=(2,6),sticky="ew")
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
        self.badge_help=ctk.CTkLabel(tab,text="",justify="left",anchor="w",wraplength=1050); self.badge_help.grid(row=1,column=0,padx=20,pady=4,sticky="ew")
        self.badge_gallery_title=ctk.CTkLabel(tab,text="",font=ctk.CTkFont(size=18,weight="bold")); self.badge_gallery_title.grid(row=2,column=0,padx=16,pady=(10,2),sticky="w")
        self.gallery=ctk.CTkScrollableFrame(tab); self.gallery.grid(row=3,column=0,padx=16,pady=(4,14),sticky="nsew")
        for column in range(5): self.gallery.grid_columnconfigure(column,weight=1)

    def _batch_ui(self) -> None:
        tab=self.batch_tab; tab.grid_columnconfigure(0,weight=1)
        self.input_label=ctk.CTkLabel(tab,text=""); self.input_label.grid(row=0,column=0,padx=16,pady=(18,2),sticky="w")
        self.batch_size_guidance=ctk.CTkLabel(tab,text="",justify="left",text_color="gray60"); self.batch_size_guidance.grid(row=0,column=1,padx=10,pady=(18,2),sticky="e")
        ctk.CTkEntry(tab,textvariable=self.input_folder_var).grid(row=1,column=0,padx=16,pady=4,sticky="ew")
        self.choose_input_button=ctk.CTkButton(tab,text="",command=self.choose_input_folder); self.choose_input_button.grid(row=1,column=1,padx=10)
        self.batch_back_button=ctk.CTkButton(tab,text="",command=self.navigate_home,width=110); self.batch_back_button.grid(row=0,column=2,padx=(0,16),pady=(18,2),sticky="ne")
        self.output_subfolder_radio=ctk.CTkRadioButton(tab,text="",variable=self.output_preference_var,value="subfolder",command=self.changed); self.output_subfolder_radio.grid(row=2,column=0,padx=16,pady=(12,4),sticky="w")
        ctk.CTkEntry(tab,textvariable=self.output_subfolder_var).grid(row=3,column=0,padx=36,pady=4,sticky="ew")
        self.output_separate_radio=ctk.CTkRadioButton(tab,text="",variable=self.output_preference_var,value="separate",command=self.changed); self.output_separate_radio.grid(row=4,column=0,padx=16,pady=(8,4),sticky="w")
        ctk.CTkEntry(tab,textvariable=self.output_folder_var).grid(row=5,column=0,padx=36,pady=4,sticky="ew")
        self.choose_output_button=ctk.CTkButton(tab,text="",command=self.choose_output_folder); self.choose_output_button.grid(row=5,column=1,padx=10)
        self.batch_suffix_label=ctk.CTkLabel(tab,text=""); self.batch_suffix_label.grid(row=6,column=0,padx=16,pady=(8,2),sticky="w")
        self.batch_suffix_entry=ctk.CTkEntry(tab,textvariable=self.batch_suffix_var); self.batch_suffix_entry.grid(row=7,column=0,padx=36,pady=(0,4),sticky="ew"); self.batch_suffix_entry.bind("<FocusOut>",self.changed)
        options=ctk.CTkFrame(tab,fg_color="transparent"); options.grid(row=8,column=0,columnspan=2,padx=16,pady=10,sticky="ew"); self.batch_checks=[]
        for i,(key,var) in enumerate((("batch.recursive",self.recursive_var),("batch.preserve",self.preserve_var),("batch.images",self.images_var),("batch.videos",self.videos_var),("batch.skip",self.skip_var))):
            check=ctk.CTkCheckBox(options,text="",variable=var,command=self.changed); check.grid(row=i//3,column=i%3,padx=8,pady=6,sticky="w"); self.batch_checks.append((key,check))
        buttons=ctk.CTkFrame(tab,fg_color="transparent"); buttons.grid(row=9,column=0,columnspan=2,padx=16,pady=8,sticky="w")
        self.scan_button=ctk.CTkButton(buttons,text="",command=self.scan_input_folder); self.scan_button.grid(row=0,column=0,padx=(0,8))
        self.start_batch_button=ctk.CTkButton(buttons,text="",command=self.start_batch); self.start_batch_button.grid(row=0,column=1,padx=8)
        self.cancel_batch_button=ctk.CTkButton(buttons,text="",command=self.cancel_batch,state="disabled"); self.cancel_batch_button.grid(row=0,column=2,padx=8)
        ctk.CTkLabel(tab,textvariable=self.scan_summary_var,justify="left",anchor="w").grid(row=10,column=0,columnspan=2,padx=16,pady=6,sticky="ew")
        self.progress=ctk.CTkProgressBar(tab); self.progress.set(0); self.progress.grid(row=11,column=0,columnspan=2,padx=16,pady=8,sticky="ew")
        ctk.CTkLabel(tab,textvariable=self.progress_text_var,justify="left",anchor="w").grid(row=12,column=0,columnspan=2,padx=16,pady=6,sticky="ew")

    def apply_translations(self) -> None:
        t=self.translator.text; self.title(f"Nenolink AI Marker {__version__} - {t('app.window')}"); self.guide_button.configure(text=t("button.user_guide")); self.reset_button.configure(text=t("button.reset")); self.batch_back_button.configure(text=t("button.back")); self.badges_back_button.configure(text=t("button.back"))
        current_key=next((key for key,name in self.tab_names.items() if name==self.tabs.get()),"single")
        for key,translation_key in (("single","tab.single"),("batch","tab.batch"),("badges","tab.badges")):
            new=t(translation_key); old=self.tab_names[key]
            if old != new:self.tabs.rename(old,new); self.tab_names[key]=new
        self.tabs.set(self.tab_names[current_key])
        self.open_button.configure(text="1. "+t("button.open_media")); self.process_button.configure(text=t("button.process_video") if self.sources and self.sources[0].suffix.lower() in VIDEO_EXTENSIONS else t("button.process")); self.file_label.configure(text=t("files.none") if not self.sources else t("files.selected",count=len(self.sources),name=self.sources[0].name))
        self.file_size_guidance.configure(text=t("files.size_guidance")); self.batch_size_guidance.configure(text=t("files.size_guidance_short"))
        self.position_label.configure(text="3. "+t("position")); self.size_label.configure(text="4. "+t("size.value",value=self.size_var.get())); self.margin_label.configure(text="5. "+t("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text="6. "+t("opacity.value",value=self.opacity_var.get()))
        self.single_badge_label.configure(text="2. "+t("badge")); self.badge_source_heading.configure(text=t("badge.source_label")); self.standard_badge_radio.configure(text=t("badge.source_standard")); self.custom_badge_radio.configure(text=t("badge.source_custom")); self.custom_folder_label.configure(text=t("badge.custom_path")+":"); self.custom_entry.configure(placeholder_text=t("badge.custom_path"))
        self.position_display_to_value={t("position.top_left"):"top-left",t("position.top_right"):"top-right",t("position.bottom_left"):"bottom-left",t("position.bottom_right"):"bottom-right"}; self.position_menu.configure(values=list(self.position_display_to_value)); self.position_display_var.set(next((label for label,value in self.position_display_to_value.items() if value==self.position_var.get()),t("position.bottom_right")))
        self.choose_badge_folder_button.configure(text=t("button.choose_badge_folder")); self.refresh_button.configure(text=t("badge.refresh")); self.badge_gallery_title.configure(text=t("badge.gallery")); self.badge_help.configure(text=t("badge.help")); self._show_badge_source_controls()
        self.input_label.configure(text=t("batch.input")); self.choose_input_button.configure(text=t("button.choose_input")); self.choose_output_button.configure(text=t("button.choose_output")); self.output_subfolder_radio.configure(text=t("batch.output_subfolder")); self.output_separate_radio.configure(text=t("batch.output_separate")); self.batch_suffix_label.configure(text=t("batch.filename_suffix"))
        self.welcome_title.configure(text=t("welcome.title")); self.welcome_tagline.configure(text=t("welcome.tagline")); self.welcome_description1.configure(text=t("welcome.description1")); self.welcome_description2.configure(text=t("welcome.description2"))
        for key,check in self.batch_checks: check.configure(text=t(key))
        self.scan_button.configure(text=t("button.scan_folder")); self.start_batch_button.configure(text=t("button.start_batch")); self.cancel_batch_button.configure(text=t("button.cancel_batch"))

    def change_language(self,name): self.translator.set_language(LANGUAGES.get(name,"en")); self.apply_translations(); self._save()
    def show_tab(self,key): self.tabs.set(self.tab_names[key])
    def navigate_home(self): self.show_tab("single")
    def reset_application(self):
        defaults=MarkerSettings(); custom_folder=self.custom_badge_var.get()
        self.sources=[]; self.preview_photo=None
        self.badge_source_var.set("standard"); self.custom_badge_var.set(custom_folder); self.badge_var.set(defaults.badge_name); self.position_var.set(defaults.position)
        self.size_var.set(defaults.size_percent); self.margin_var.set(defaults.margin); self.opacity_var.set(defaults.opacity)
        self.batch_suffix_var.set(defaults.batch_filename_suffix)
        self.scan=None; self.cancel_event.clear(); self.scan_summary_var.set(""); self.progress_text_var.set(""); self.progress.set(0)
        self.refresh_badges(False); self.apply_translations(); self.file_label.configure(text=self.translator.text("files.none")); self.render_start_view(); self.after(150,self._finish_reset_view); self.status_var.set(self.translator.text("status.reset")); self._save()
    def changed(self,*_):
        self.size_label.configure(text="4. "+self.translator.text("size.value",value=self.size_var.get())); self.margin_label.configure(text="5. "+self.translator.text("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text="6. "+self.translator.text("opacity.value",value=self.opacity_var.get())); self.update_preview(); self._save()
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
            self.sources=candidates; self.file_label.configure(text=self.translator.text("files.selected",count=len(self.sources),name=self.sources[0].name) if self.sources else self.translator.text("files.none_supported")); self.process_button.configure(text=self.translator.text("button.process_video") if self.sources and self.sources[0].suffix.lower() in VIDEO_EXTENSIONS else self.translator.text("button.process")); self.update_preview()

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
        saved=[]; failures=[]
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
                    self.batch_processor.process_video(source,badge,target,self.settings())
                else:self.processor.save(self.processor.process(source,badge,self.settings()),target)
                saved.append(target)
            except (OSError,ValueError) as error:failures.append(f"{source.name}: {error}")
        only_video=bool(saved) and all(path.suffix.lower() in VIDEO_EXTENSIONS for path in self.sources)
        summary=self.translator.text("video.saved_name",name=saved[-1].name) if only_video and not failures else self.translator.text("process.summary",saved=len(saved),total=len(self.sources)); self.status_var.set(summary)
        (messagebox.showerror if failures else messagebox.showinfo)(self.translator.text("error.completed") if failures else self.translator.text("complete.title"),summary+("\n\n"+"\n".join(failures[:8]) if failures else ""))

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
        self.cancel_event.clear(); self.start_batch_button.configure(state="disabled"); self.cancel_batch_button.configure(state="normal"); settings=self.settings()
        def report(path,index,total,result):self.after(0,lambda:self._batch_progress(path,index,total,result))
        def work():
            result=self.batch_processor.process(self.scan,badge,settings,cancelled=self.cancel_event.is_set,progress=report); self.after(0,lambda:self._batch_done(result))
        threading.Thread(target=work,daemon=True).start()
    def _batch_progress(self,path,index,total,result):self.progress.set(index/max(1,total)); self.progress_text_var.set(self.translator.text("batch.progress",name=path.name,completed=index,total=total,success=result.successful,skipped=result.skipped,errors=len(result.errors)))
    def _batch_done(self,result:BatchResult):
        self.start_batch_button.configure(state="normal"); self.cancel_batch_button.configure(state="disabled"); text=self.translator.text("batch.done",success=result.successful,skipped=result.skipped,errors=len(result.errors)); self.progress_text_var.set((self.translator.text("batch.cancelled")+"\n" if result.cancelled else "")+text)
        if result.errors:messagebox.showerror(self.translator.text("error.completed"),text+"\n\n"+"\n".join(result.errors[:8]))
    def cancel_batch(self):self.cancel_event.set()
    def open_guide(self):
        try:open_user_guide(localized_user_guide_path(self.translator.language))
        except (OSError,FileNotFoundError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("guide.missing",error=error))

    def _write_hotfix_verification(self):
        """Exercise the real packaged widgets for release verification only."""
        report_path=Path(os.environ["NENOLINK_VERIFY_REPORT"])
        initial_badge_settings={"source":self.badge_source_var.get(),"folder":self.custom_badge_var.get(),"selection":self.badge_var.get(),"batch_suffix":self.batch_suffix_var.get(),"status":self.status_var.get(),"count":len(self.badges.display_badges()),"custom_controls_visible":self.custom_controls.winfo_manager()=="grid"}
        tab_switching={}
        for key,frame in (("single",self.single_tab),("batch",self.batch_tab),("badges",self.settings_tab)):
            self.show_tab(key); self.update(); time.sleep(.15); self.update()
            tab_switching[key]={"selected":self.tabs.get()==self.tab_names[key],"visible":bool(frame.winfo_ismapped()),"other_visible":any(bool(other.winfo_ismapped()) for other in (self.single_tab,self.batch_tab,self.settings_tab) if other is not frame)}
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
        if sample:
            translation=self.processor.process(Path(sample),self.badges.find("ai-translation.png"),self.settings())
            assisted=self.processor.process(Path(sample),self.badges.find("ai-assisted.png"),self.settings())
            selected_badge_written=translation.tobytes()!=assisted.tobytes() and self.badge_var.get()=="ai-translation.png"
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
                if processed is not None:self.processor.save(processed,output)
                selected_custom=self.badge_var.get(); retained_custom=self.custom_badge_var.get(); retained_sources=list(self.sources); self.show_tab("badges"); self.update(); self.badges_back_button.invoke(); self.update(); time.sleep(.15); self.update()
                custom_back_preserved=self.tabs.get()==self.tab_names["single"] and self.badge_source_var.get()=="custom" and self.badge_var.get()==selected_custom and self.custom_badge_var.get()==retained_custom and self.sources==retained_sources
                custom_verification={"files":custom_names,"displays":custom_displays,"selected":self.badge_var.get(),"selector_values":list(self.badge_menu.cget("values")),"gallery_badges":len(self.gallery_buttons),"preview":bool(self.preview_photo),"output_saved":output.is_file(),"status":self.status_var.get(),"source_controls_visible":self.custom_controls.winfo_manager()=="grid","back_preserved":custom_back_preserved}
        guide_paths={code:localized_user_guide_path(code) for code in ("da","en","fr")}
        guide_language=os.environ.get("NENOLINK_VERIFY_GUIDE_LANGUAGE","en").lower()
        guide=localized_user_guide_path(guide_language); guide_opened=False
        if os.environ.get("NENOLINK_VERIFY_OPEN_GUIDE") == "1":
            try:open_user_guide(guide); guide_opened=True
            except OSError:guide_opened=False
        payload={"english":english,"danish":danish,"german":german,"french":french,"initial_badge_settings":initial_badge_settings,"welcome_before_image":welcome_before_image,"welcome_illustration":welcome_illustration,"welcome_hidden_after_image":(not sample or self.welcome_frame.winfo_manager()==""),"badges_found":len(badge_names),"badge_selector_visible":self.badge_menu.winfo_manager()=="grid","badge_selector_values":list(self.badge_menu.cget("values")),"gallery_badges":len(self.gallery_buttons),"gallery_selection_persisted":gallery_selection_persisted,"badges_tab_is_distinct":self.badge_source_frame.master is self.settings_tab,"selected_badges":selected,"image_preview":bool(self.preview_photo),"selected_badge_written":selected_badge_written,"custom_verification":custom_verification,"friendly_status":("_MEI" not in self.status_var.get() and "assets" not in self.status_var.get()),"process_button_state":self.process_button.cget("state"),"guide_language":guide_language,"guide_filename":guide.name,"guide_paths":{code:path.name for code,path in guide_paths.items()},"guide_exists":guide.is_file(),"guide_opened":guide_opened,"translation_keys_visible":any("." in str(value) and " " not in str(value) for group in (english,danish,german,french) for value in group.values() if isinstance(value,str))}
        payload["tab_switching"]=tab_switching
        payload["back_navigation"]={"badges_preserved":badges_back_preserved,"batch_preserved":batch_back_preserved,"english_label":english["back"],"danish_label":danish["back"]}
        if os.environ.get("NENOLINK_VERIFY_RESET_LANGUAGE")=="da":self.change_language("Dansk")
        retained_custom_folder=self.custom_badge_var.get(); self.reset_application(); self.update(); time.sleep(.2); self.update()
        payload["reset_verification"]={"source":self.badge_source_var.get(),"selection":self.badge_var.get(),"folder_retained":self.custom_badge_var.get()==retained_custom_folder,"position":self.position_var.get(),"size":self.size_var.get(),"margin":self.margin_var.get(),"opacity":self.opacity_var.get(),"batch_suffix":self.batch_suffix_var.get(),"sources":len(self.sources),"scan_cleared":self.scan is None,"single_selected":self.tabs.get()==self.tab_names["single"],"welcome":self.welcome_frame.winfo_manager()=="grid","welcome_mapped":bool(self.welcome_frame.winfo_ismapped()),"welcome_title":self.welcome_title.cget("text"),"welcome_illustration":bool(self.welcome_photo and self.welcome_illustration.winfo_ismapped()),"preview_hidden":not bool(self.preview_label.winfo_ismapped()),"status":self.status_var.get()}
        report_path.write_text(json.dumps(payload,indent=2),encoding="utf-8"); self.destroy()

    def settings(self):
        return MarkerSettings(badge_name=self.badge_var.get(),position=self.position_var.get(),size_percent=self.size_var.get(),margin=self.margin_var.get(),opacity=self.opacity_var.get(),language=self.translator.language,badge_source=self.badge_source_var.get(),custom_badge_folder=self.custom_badge_var.get(),input_folder=self.input_folder_var.get(),output_preference=self.output_preference_var.get(),output_folder=self.output_folder_var.get(),output_subfolder=self.output_subfolder_var.get(),include_subfolders=self.recursive_var.get(),preserve_folder_structure=self.preserve_var.get(),process_images=self.images_var.get(),process_videos=self.videos_var.get(),skip_processed=self.skip_var.get(),video_mode="overlay",batch_filename_suffix=self.batch_suffix_var.get()).validated()
    def _save(self):
        try:self.config_store.save(self.settings())
        except OSError:pass
    def destroy(self):self.cancel_event.set(); self._save(); super().destroy()


def run():
    ctk.set_appearance_mode("system"); ctk.set_default_color_theme("blue"); MarkerApp().mainloop()
