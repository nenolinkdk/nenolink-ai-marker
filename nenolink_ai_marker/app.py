from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import sys
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image

from . import __version__
from .badges import BadgeSourceManager, choose_badge_selection
from .batch import BatchProcessor, BatchResult, FolderScan, destination_root, scan_folder
from .config import ConfigStore
from .guide import open_user_guide
from .i18n import LANGUAGES, Translator
from .models import MarkerSettings
from .paths import badge_directory, locale_directory, localized_user_guide_path, welcome_image_path
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS, output_path
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
        self.geometry("1180x800"); self.minsize(980, 700)
        self.processor = ImageProcessor(); self.batch_processor = BatchProcessor(self.processor)
        self.config_store = ConfigStore(); saved = self.config_store.load()
        self.translator = Translator(locale_directory(), saved.language)
        self.badge_sources = BadgeSourceManager(badge_directory())
        self.badges = self.badge_sources.repository(saved.badge_source, saved.custom_badge_folder)
        self.sources: list[Path] = []; self.scan: FolderScan | None = None
        self.cancel_event = threading.Event(); self.preview_photo = None; self.badge_photo = None; self.single_badge_photo = None; self.welcome_photo = None; self.welcome_image = None
        self.gallery_photos = []; self.gallery_buttons = {}; self.badge_display_to_file = {}
        self.badge_var=ctk.StringVar(value=saved.badge_name); self.position_var=ctk.StringVar(value=saved.position)
        self.size_var=ctk.IntVar(value=saved.size_percent); self.margin_var=ctk.IntVar(value=saved.margin); self.opacity_var=ctk.IntVar(value=saved.opacity)
        self.language_var=ctk.StringVar(value=Translator.language_name(saved.language)); self.badge_source_var=ctk.StringVar(value=saved.badge_source)
        self.custom_badge_var=ctk.StringVar(value=saved.custom_badge_folder); self.input_folder_var=ctk.StringVar(value=saved.input_folder)
        self.output_preference_var=ctk.StringVar(value=saved.output_preference); self.output_folder_var=ctk.StringVar(value=saved.output_folder)
        self.output_subfolder_var=ctk.StringVar(value=saved.output_subfolder); self.recursive_var=ctk.BooleanVar(value=saved.include_subfolders)
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
        self.guide_button=ctk.CTkButton(header,text="",command=self.open_guide,width=170); self.guide_button.grid(row=0,column=3,padx=(8,20))
        self.tabs=ctk.CTkTabview(self); self.tabs.grid(row=1,column=0,padx=16,pady=12,sticky="nsew")
        self.tab_names={"single":"Single image","batch":"Folder batch","badges":"Badge settings"}
        self.single_tab=self.tabs.add(self.tab_names["single"]); self.batch_tab=self.tabs.add(self.tab_names["batch"]); self.settings_tab=self.tabs.add(self.tab_names["badges"])
        self._single_ui(); self._batch_ui(); self._settings_ui()
        ctk.CTkLabel(self,text="(c) Copyright Henrik Nielsen - nenolink.com",text_color="gray60").grid(row=2,column=0,padx=20,pady=(0,10),sticky="w")

    def _single_ui(self) -> None:
        tab=self.single_tab; tab.grid_columnconfigure(1,weight=1); tab.grid_rowconfigure(0,weight=1)
        left=ctk.CTkFrame(tab,width=330); left.grid(row=0,column=0,padx=(4,8),pady=4,sticky="ns"); left.grid_columnconfigure(0,weight=1)
        self.open_button=ctk.CTkButton(left,text="",command=self.open_images); self.open_button.grid(row=0,column=0,padx=16,pady=(18,8),sticky="ew")
        self.file_label=ctk.CTkLabel(left,text="",wraplength=280,justify="left"); self.file_label.grid(row=1,column=0,padx=16,pady=6,sticky="w")
        self.single_badge_label=ctk.CTkLabel(left,text="",font=ctk.CTkFont(weight="bold")); self.single_badge_label.grid(row=2,column=0,padx=16,pady=(12,2),sticky="w")
        self.badge_menu=ctk.CTkOptionMenu(left,variable=self.badge_display_var,values=["—"],command=self.select_badge_display); self.badge_menu.grid(row=3,column=0,padx=16,pady=4,sticky="ew")
        badge_preview=ctk.CTkFrame(left); badge_preview.grid(row=4,column=0,padx=16,pady=6,sticky="ew"); badge_preview.grid_columnconfigure(1,weight=1)
        self.single_badge_preview_label=ctk.CTkLabel(badge_preview,text="",width=110,height=54); self.single_badge_preview_label.grid(row=0,column=0,padx=8,pady=8)
        self.single_badge_name_label=ctk.CTkLabel(badge_preview,textvariable=self.badge_name_var,font=ctk.CTkFont(weight="bold"),anchor="w"); self.single_badge_name_label.grid(row=0,column=1,padx=(4,8),pady=8,sticky="ew")
        self.position_label=ctk.CTkLabel(left,text=""); self.position_label.grid(row=5,column=0,padx=16,pady=(8,2),sticky="w")
        self.position_menu=ctk.CTkOptionMenu(left,variable=self.position_var,values=["top-left","top-right","bottom-left","bottom-right"],command=self.changed); self.position_menu.grid(row=6,column=0,padx=16,pady=4,sticky="ew")
        self.size_label=self._slider(left,self.size_var,1,100,7); self.margin_label=self._slider(left,self.margin_var,0,250,9); self.opacity_label=self._slider(left,self.opacity_var,0,100,11)
        self.process_button=ctk.CTkButton(left,text="",command=self.save_images); self.process_button.grid(row=13,column=0,padx=16,pady=14,sticky="ew")
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
        ctk.CTkLabel(right,textvariable=self.status_var,wraplength=650).grid(row=1,column=0,padx=12,pady=(0,12),sticky="ew")

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

    def _slider(self,parent,var,start,end,row):
        label=ctk.CTkLabel(parent,text=""); label.grid(row=row,column=0,padx=16,pady=(8,0),sticky="w")
        ctk.CTkSlider(parent,from_=start,to=end,number_of_steps=end-start,variable=var,command=self.changed).grid(row=row+1,column=0,padx=16,pady=(2,6),sticky="ew")
        return label

    def _settings_ui(self) -> None:
        tab=self.settings_tab; tab.grid_columnconfigure(0,weight=1); tab.grid_rowconfigure(3,weight=1)
        source=ctk.CTkFrame(tab); self.badge_source_frame=source; source.grid(row=0,column=0,padx=16,pady=(14,6),sticky="ew"); source.grid_columnconfigure(0,weight=1)
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
        ctk.CTkEntry(tab,textvariable=self.input_folder_var).grid(row=1,column=0,padx=16,pady=4,sticky="ew")
        self.choose_input_button=ctk.CTkButton(tab,text="",command=self.choose_input_folder); self.choose_input_button.grid(row=1,column=1,padx=10)
        self.output_subfolder_radio=ctk.CTkRadioButton(tab,text="",variable=self.output_preference_var,value="subfolder",command=self.changed); self.output_subfolder_radio.grid(row=2,column=0,padx=16,pady=(12,4),sticky="w")
        ctk.CTkEntry(tab,textvariable=self.output_subfolder_var).grid(row=3,column=0,padx=36,pady=4,sticky="ew")
        self.output_separate_radio=ctk.CTkRadioButton(tab,text="",variable=self.output_preference_var,value="separate",command=self.changed); self.output_separate_radio.grid(row=4,column=0,padx=16,pady=(8,4),sticky="w")
        ctk.CTkEntry(tab,textvariable=self.output_folder_var).grid(row=5,column=0,padx=36,pady=4,sticky="ew")
        self.choose_output_button=ctk.CTkButton(tab,text="",command=self.choose_output_folder); self.choose_output_button.grid(row=5,column=1,padx=10)
        options=ctk.CTkFrame(tab,fg_color="transparent"); options.grid(row=6,column=0,columnspan=2,padx=16,pady=10,sticky="ew"); self.batch_checks=[]
        for i,(key,var) in enumerate((("batch.recursive",self.recursive_var),("batch.preserve",self.preserve_var),("batch.images",self.images_var),("batch.videos",self.videos_var),("batch.skip",self.skip_var))):
            check=ctk.CTkCheckBox(options,text="",variable=var,command=self.changed); check.grid(row=i//3,column=i%3,padx=8,pady=6,sticky="w"); self.batch_checks.append((key,check))
        buttons=ctk.CTkFrame(tab,fg_color="transparent"); buttons.grid(row=7,column=0,columnspan=2,padx=16,pady=8,sticky="w")
        self.scan_button=ctk.CTkButton(buttons,text="",command=self.scan_input_folder); self.scan_button.grid(row=0,column=0,padx=(0,8))
        self.start_batch_button=ctk.CTkButton(buttons,text="",command=self.start_batch); self.start_batch_button.grid(row=0,column=1,padx=8)
        self.cancel_batch_button=ctk.CTkButton(buttons,text="",command=self.cancel_batch,state="disabled"); self.cancel_batch_button.grid(row=0,column=2,padx=8)
        ctk.CTkLabel(tab,textvariable=self.scan_summary_var,justify="left",anchor="w").grid(row=8,column=0,columnspan=2,padx=16,pady=6,sticky="ew")
        self.progress=ctk.CTkProgressBar(tab); self.progress.set(0); self.progress.grid(row=9,column=0,columnspan=2,padx=16,pady=8,sticky="ew")
        ctk.CTkLabel(tab,textvariable=self.progress_text_var,justify="left",anchor="w").grid(row=10,column=0,columnspan=2,padx=16,pady=6,sticky="ew")

    def apply_translations(self) -> None:
        t=self.translator.text; self.title(f"Nenolink AI Marker {__version__} - {t('app.window')}"); self.guide_button.configure(text=t("button.user_guide"))
        for key,translation_key in (("single","tab.single"),("batch","tab.batch"),("badges","tab.badges")):
            new=t(translation_key); old=self.tab_names[key]
            if old != new:self.tabs.rename(old,new); self.tab_names[key]=new
        self.open_button.configure(text=t("button.open_images")); self.process_button.configure(text=t("button.process")); self.file_label.configure(text=t("files.none") if not self.sources else t("files.selected",count=len(self.sources),name=self.sources[0].name))
        self.position_label.configure(text=t("position")); self.size_label.configure(text=t("size.value",value=self.size_var.get())); self.margin_label.configure(text=t("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text=t("opacity.value",value=self.opacity_var.get()))
        self.single_badge_label.configure(text=t("badge")); self.badge_source_heading.configure(text=t("badge.source_label")); self.standard_badge_radio.configure(text=t("badge.source_standard")); self.custom_badge_radio.configure(text=t("badge.source_custom")); self.custom_folder_label.configure(text=t("badge.custom_path")+":"); self.custom_entry.configure(placeholder_text=t("badge.custom_path"))
        self.choose_badge_folder_button.configure(text=t("button.choose_badge_folder")); self.refresh_button.configure(text=t("badge.refresh")); self.badge_gallery_title.configure(text=t("badge.gallery")); self.badge_help.configure(text=t("badge.help")); self._show_badge_source_controls()
        self.input_label.configure(text=t("batch.input")); self.choose_input_button.configure(text=t("button.choose_input")); self.choose_output_button.configure(text=t("button.choose_output")); self.output_subfolder_radio.configure(text=t("batch.output_subfolder")); self.output_separate_radio.configure(text=t("batch.output_separate"))
        self.welcome_title.configure(text=t("welcome.title")); self.welcome_tagline.configure(text=t("welcome.tagline")); self.welcome_description1.configure(text=t("welcome.description1")); self.welcome_description2.configure(text=t("welcome.description2"))
        for key,check in self.batch_checks: check.configure(text=t(key))
        self.scan_button.configure(text=t("button.scan_folder")); self.start_batch_button.configure(text=t("button.start_batch")); self.cancel_batch_button.configure(text=t("button.cancel_batch"))

    def change_language(self,name): self.translator.set_language(LANGUAGES.get(name,"en")); self.apply_translations(); self._save()
    def changed(self,*_):
        self.size_label.configure(text=self.translator.text("size.value",value=self.size_var.get())); self.margin_label.configure(text=self.translator.text("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text=self.translator.text("opacity.value",value=self.opacity_var.get())); self.update_preview(); self._save()
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
        selected=filedialog.askopenfilenames(title=self.translator.text("dialog.open_images"),filetypes=[(self.translator.text("files.supported"),"*.jpg *.jpeg *.png *.webp"),(self.translator.text("files.all"),"*.*")])
        if selected:self.sources=[Path(p) for p in selected if Path(p).suffix.lower() in SUPPORTED_EXTENSIONS]; self.file_label.configure(text=self.translator.text("files.selected",count=len(self.sources),name=self.sources[0].name) if self.sources else self.translator.text("files.none_supported")); self.update_preview()

    def update_preview(self):
        badge=self.badges.find(self.badge_var.get())
        if show_welcome(self.sources):self.preview_photo=None; self._show_welcome(); return
        self._show_preview()
        if not badge:self.preview_label.configure(image=None,text=self.translator.text("badge.none")); return
        try:
            image=self.processor.process(self.sources[0],badge,self.settings()); image.thumbnail((720,600),Image.Resampling.LANCZOS); self.preview_photo=ctk.CTkImage(light_image=image,dark_image=image,size=image.size); self.preview_label.configure(image=self.preview_photo,text=""); self.status_var.set(self.translator.text("preview.showing",name=self.sources[0].name))
        except (OSError,ValueError) as error:self.status_var.set(self.translator.text("error.preview",error=error))

    def clear_images(self):
        self.sources=[]; self.file_label.configure(text=self.translator.text("files.none")); self.update_preview()

    def save_images(self):
        badge=self.badges.find(self.badge_var.get())
        if not self.sources or not badge:messagebox.showwarning(self.translator.text("warning.title"),self.translator.text("warning.nothing_to_save")); return
        folder=filedialog.askdirectory(title=self.translator.text("dialog.output_folder"))
        if not folder:return
        saved=[]; failures=[]
        for source in self.sources:
            try:target=output_path(source,Path(folder)); self.processor.save(self.processor.process(source,badge,self.settings()),target); saved.append(target)
            except (OSError,ValueError) as error:failures.append(f"{source.name}: {error}")
        summary=self.translator.text("process.summary",saved=len(saved),total=len(self.sources)); self.status_var.set(summary)
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
        self.scan_summary_var.set(self.translator.text("batch.scan_summary",images=len(self.scan.images),videos=len(self.scan.videos),unsupported=len(self.scan.unsupported),total=len(selected),output=out)); self._save()
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
        initial_badge_settings={"source":self.badge_source_var.get(),"folder":self.custom_badge_var.get(),"selection":self.badge_var.get(),"status":self.status_var.get(),"count":len(self.badges.display_badges()),"custom_controls_visible":self.custom_controls.winfo_manager()=="grid"}
        welcome_before_image=self.welcome_frame.winfo_manager()=="grid" and self.preview_label.winfo_manager()==""
        welcome_illustration=bool(self.welcome_image and self.welcome_photo)
        self.change_language("English"); self.update()
        english={"title":self.title(),"tabs":list(self.tab_names.values()),"guide":self.guide_button.cget("text"),"choose":self.open_button.cget("text"),"process":self.process_button.cget("text"),"position":self.position_label.cget("text"),"welcome_title":self.welcome_title.cget("text"),"welcome_tagline":self.welcome_tagline.cget("text"),"welcome_description1":self.welcome_description1.cget("text"),"welcome_description2":self.welcome_description2.cget("text")}
        self.change_language("Dansk"); self.update(); danish={"guide":self.guide_button.cget("text"),"choose":self.open_button.cget("text"),"tabs":list(self.tab_names.values()),"welcome_title":self.welcome_title.cget("text"),"welcome_tagline":self.welcome_tagline.cget("text"),"welcome_description1":self.welcome_description1.cget("text"),"welcome_description2":self.welcome_description2.cget("text")}
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
                custom_verification={"files":custom_names,"displays":custom_displays,"selected":self.badge_var.get(),"selector_values":list(self.badge_menu.cget("values")),"gallery_badges":len(self.gallery_buttons),"preview":bool(self.preview_photo),"output_saved":output.is_file(),"status":self.status_var.get(),"source_controls_visible":self.custom_controls.winfo_manager()=="grid"}
        guide_paths={code:localized_user_guide_path(code) for code in ("da","en","fr")}
        guide_language=os.environ.get("NENOLINK_VERIFY_GUIDE_LANGUAGE","en").lower()
        guide=localized_user_guide_path(guide_language); guide_opened=False
        if os.environ.get("NENOLINK_VERIFY_OPEN_GUIDE") == "1":
            try:open_user_guide(guide); guide_opened=True
            except OSError:guide_opened=False
        payload={"english":english,"danish":danish,"german":german,"french":french,"initial_badge_settings":initial_badge_settings,"welcome_before_image":welcome_before_image,"welcome_illustration":welcome_illustration,"welcome_hidden_after_image":(not sample or self.welcome_frame.winfo_manager()==""),"badges_found":len(badge_names),"badge_selector_visible":self.badge_menu.winfo_manager()=="grid","badge_selector_values":list(self.badge_menu.cget("values")),"gallery_badges":len(self.gallery_buttons),"gallery_selection_persisted":gallery_selection_persisted,"badges_tab_is_distinct":self.badge_source_frame.master is self.settings_tab,"selected_badges":selected,"image_preview":bool(self.preview_photo),"selected_badge_written":selected_badge_written,"custom_verification":custom_verification,"friendly_status":("_MEI" not in self.status_var.get() and "assets" not in self.status_var.get()),"process_button_state":self.process_button.cget("state"),"guide_language":guide_language,"guide_filename":guide.name,"guide_paths":{code:path.name for code,path in guide_paths.items()},"guide_exists":guide.is_file(),"guide_opened":guide_opened,"translation_keys_visible":any("." in str(value) and " " not in str(value) for group in (english,danish,german,french) for value in group.values() if isinstance(value,str))}
        report_path.write_text(json.dumps(payload,indent=2),encoding="utf-8"); self.destroy()

    def settings(self):
        return MarkerSettings(badge_name=self.badge_var.get(),position=self.position_var.get(),size_percent=self.size_var.get(),margin=self.margin_var.get(),opacity=self.opacity_var.get(),language=self.translator.language,badge_source=self.badge_source_var.get(),custom_badge_folder=self.custom_badge_var.get(),input_folder=self.input_folder_var.get(),output_preference=self.output_preference_var.get(),output_folder=self.output_folder_var.get(),output_subfolder=self.output_subfolder_var.get(),include_subfolders=self.recursive_var.get(),preserve_folder_structure=self.preserve_var.get(),process_images=self.images_var.get(),process_videos=self.videos_var.get(),skip_processed=self.skip_var.get(),video_mode="overlay").validated()
    def _save(self):
        try:self.config_store.save(self.settings())
        except OSError:pass
    def destroy(self):self.cancel_event.set(); self._save(); super().destroy()


def run():
    ctk.set_appearance_mode("system"); ctk.set_default_color_theme("blue"); MarkerApp().mainloop()
