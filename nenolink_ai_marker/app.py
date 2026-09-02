from __future__ import annotations

from pathlib import Path
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image

from . import __version__
from .badges import BadgeSourceManager
from .batch import BatchProcessor, BatchResult, FolderScan, destination_root, scan_folder
from .config import ConfigStore
from .guide import open_user_guide
from .i18n import LANGUAGES, Translator
from .models import MarkerSettings
from .paths import badge_directory, locale_directory, user_guide_path
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS, output_path


class MarkerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.geometry("1180x800"); self.minsize(980, 700)
        self.processor = ImageProcessor(); self.batch_processor = BatchProcessor(self.processor)
        self.config_store = ConfigStore(); saved = self.config_store.load()
        self.translator = Translator(locale_directory(), saved.language)
        self.badge_sources = BadgeSourceManager(badge_directory())
        self.badges = self.badge_sources.repository(saved.badge_source, saved.custom_badge_folder)
        self.sources: list[Path] = []; self.scan: FolderScan | None = None
        self.cancel_event = threading.Event(); self.preview_photo = None; self.badge_photo = None
        self.badge_var=ctk.StringVar(value=saved.badge_name); self.position_var=ctk.StringVar(value=saved.position)
        self.size_var=ctk.IntVar(value=saved.size_percent); self.margin_var=ctk.IntVar(value=saved.margin); self.opacity_var=ctk.IntVar(value=saved.opacity)
        self.language_var=ctk.StringVar(value=Translator.language_name(saved.language)); self.badge_source_var=ctk.StringVar(value=saved.badge_source)
        self.custom_badge_var=ctk.StringVar(value=saved.custom_badge_folder); self.input_folder_var=ctk.StringVar(value=saved.input_folder)
        self.output_preference_var=ctk.StringVar(value=saved.output_preference); self.output_folder_var=ctk.StringVar(value=saved.output_folder)
        self.output_subfolder_var=ctk.StringVar(value=saved.output_subfolder); self.recursive_var=ctk.BooleanVar(value=saved.include_subfolders)
        self.preserve_var=ctk.BooleanVar(value=saved.preserve_folder_structure); self.images_var=ctk.BooleanVar(value=saved.process_images)
        self.videos_var=ctk.BooleanVar(value=saved.process_videos); self.skip_var=ctk.BooleanVar(value=saved.skip_processed)
        self.status_var=ctk.StringVar(); self.badge_name_var=ctk.StringVar(); self.badge_description_var=ctk.StringVar()
        self.scan_summary_var=ctk.StringVar(); self.progress_text_var=ctk.StringVar()
        self._build_ui(); self.apply_translations(); self.refresh_badges(False); self.protocol("WM_DELETE_WINDOW", self.destroy)

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
        self.position_label=ctk.CTkLabel(left,text=""); self.position_label.grid(row=2,column=0,padx=16,pady=(12,2),sticky="w")
        self.position_menu=ctk.CTkOptionMenu(left,variable=self.position_var,values=["top-left","top-right","bottom-left","bottom-right"],command=self.changed); self.position_menu.grid(row=3,column=0,padx=16,pady=4,sticky="ew")
        self.size_label=self._slider(left,self.size_var,1,100,4); self.margin_label=self._slider(left,self.margin_var,0,250,6); self.opacity_label=self._slider(left,self.opacity_var,0,100,8)
        self.process_button=ctk.CTkButton(left,text="",command=self.save_images); self.process_button.grid(row=10,column=0,padx=16,pady=18,sticky="ew")
        right=ctk.CTkFrame(tab); right.grid(row=0,column=1,padx=(8,4),pady=4,sticky="nsew"); right.grid_columnconfigure(0,weight=1); right.grid_rowconfigure(0,weight=1)
        self.preview_label=ctk.CTkLabel(right,text=""); self.preview_label.grid(row=0,column=0,padx=12,pady=12,sticky="nsew")
        ctk.CTkLabel(right,textvariable=self.status_var,wraplength=650).grid(row=1,column=0,padx=12,pady=(0,12),sticky="ew")

    def _slider(self,parent,var,start,end,row):
        label=ctk.CTkLabel(parent,text=""); label.grid(row=row,column=0,padx=16,pady=(8,0),sticky="w")
        ctk.CTkSlider(parent,from_=start,to=end,number_of_steps=end-start,variable=var,command=self.changed).grid(row=row+1,column=0,padx=16,pady=(2,6),sticky="ew")
        return label

    def _settings_ui(self) -> None:
        tab=self.settings_tab; tab.grid_columnconfigure(0,weight=1); tab.grid_columnconfigure(1,weight=0)
        self.badge_settings_title=ctk.CTkLabel(tab,text="",font=ctk.CTkFont(size=18,weight="bold")); self.badge_settings_title.grid(row=0,column=0,columnspan=2,padx=20,pady=(20,10),sticky="w")
        self.standard_radio=ctk.CTkRadioButton(tab,text="",variable=self.badge_source_var,value="standard",command=self.change_badge_source); self.standard_radio.grid(row=1,column=0,padx=20,pady=6,sticky="w")
        self.custom_radio=ctk.CTkRadioButton(tab,text="",variable=self.badge_source_var,value="custom",command=self.change_badge_source); self.custom_radio.grid(row=2,column=0,padx=20,pady=6,sticky="w")
        self.custom_entry=ctk.CTkEntry(tab,textvariable=self.custom_badge_var); self.custom_entry.grid(row=3,column=0,padx=20,pady=6,sticky="ew")
        self.choose_badge_folder_button=ctk.CTkButton(tab,text="",command=self.browse_custom_badges); self.choose_badge_folder_button.grid(row=3,column=1,padx=12,pady=6)
        self.badge_label=ctk.CTkLabel(tab,text=""); self.badge_label.grid(row=4,column=0,padx=20,pady=(18,2),sticky="w")
        self.badge_menu=ctk.CTkOptionMenu(tab,variable=self.badge_var,values=["—"],command=lambda _:self.select_badge()); self.badge_menu.grid(row=5,column=0,padx=20,pady=4,sticky="ew")
        self.refresh_button=ctk.CTkButton(tab,text="",command=self.refresh_badges); self.refresh_button.grid(row=5,column=1,padx=12,pady=4)
        frame=ctk.CTkFrame(tab); frame.grid(row=6,column=0,columnspan=2,padx=20,pady=18,sticky="nsew"); frame.grid_columnconfigure(1,weight=1)
        self.badge_preview_label=ctk.CTkLabel(frame,text="",width=330,height=140); self.badge_preview_label.grid(row=0,column=0,rowspan=2,padx=16,pady=16)
        ctk.CTkLabel(frame,textvariable=self.badge_name_var,font=ctk.CTkFont(size=18,weight="bold"),anchor="w").grid(row=0,column=1,padx=12,pady=(20,2),sticky="sw")
        ctk.CTkLabel(frame,textvariable=self.badge_description_var,wraplength=500,justify="left",anchor="nw").grid(row=1,column=1,padx=12,pady=(2,20),sticky="nw")

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
        self.badge_settings_title.configure(text=t("menu.settings")); self.standard_radio.configure(text=t("badge.standard")); self.custom_radio.configure(text=t("badge.custom")); self.custom_entry.configure(placeholder_text=t("badge.custom_path"))
        self.choose_badge_folder_button.configure(text=t("button.choose_badge_folder")); self.badge_label.configure(text=t("badge")); self.refresh_button.configure(text=t("badge.refresh"))
        self.input_label.configure(text=t("batch.input")); self.choose_input_button.configure(text=t("button.choose_input")); self.choose_output_button.configure(text=t("button.choose_output")); self.output_subfolder_radio.configure(text=t("batch.output_subfolder")); self.output_separate_radio.configure(text=t("batch.output_separate"))
        for key,check in self.batch_checks: check.configure(text=t(key))
        self.scan_button.configure(text=t("button.scan_folder")); self.start_batch_button.configure(text=t("button.start_batch")); self.cancel_batch_button.configure(text=t("button.cancel_batch"))

    def change_language(self,name): self.translator.set_language(LANGUAGES.get(name,"en")); self.apply_translations(); self._save()
    def changed(self,*_):
        self.size_label.configure(text=self.translator.text("size.value",value=self.size_var.get())); self.margin_label.configure(text=self.translator.text("margin.value",value=self.margin_var.get())); self.opacity_label.configure(text=self.translator.text("opacity.value",value=self.opacity_var.get())); self.update_preview(); self._save()
    def change_badge_source(self): self.refresh_badges(); self._save()
    def select_badge(self): self.update_badge_preview(); self.update_preview(); self._save()

    def browse_custom_badges(self):
        value=filedialog.askdirectory(title=self.translator.text("dialog.custom_badges"))
        if value: self.custom_badge_var.set(value); self.badge_source_var.set("custom"); self.refresh_badges(); self._save()

    def refresh_badges(self,show_dialog=True):
        self.badges=self.badge_sources.repository(self.badge_source_var.get(),self.custom_badge_var.get()); missing=self.badge_sources.fallback_reason
        if missing:self.badge_source_var.set("standard")
        names=[p.name for p in self.badges.list_badges()]; self.badge_menu.configure(values=names or [self.translator.text("badge.none")])
        if self.badge_var.get() not in names:self.badge_var.set(names[0] if names else self.translator.text("badge.none"))
        if missing:text=self.translator.text("badge.custom_missing",folder=missing,fallback=self.badges.directory)
        elif names:text=self.translator.text("badge.found",count=len(names),folder=self.badges.directory)
        else:text=self.translator.text("badge.not_found",folder=self.badges.directory)
        self.status_var.set(text)
        if show_dialog and (missing or not names):messagebox.showwarning(self.translator.text("warning.title"),text)
        self.update_badge_preview(); self.update_preview()

    def update_badge_preview(self):
        badge=self.badges.find(self.badge_var.get())
        if not badge:self.badge_preview_label.configure(image=None,text=self.translator.text("badge.none")); return
        try:
            with Image.open(badge) as opened:image=opened.convert("RGBA")
            image.thumbnail((320,130),Image.Resampling.LANCZOS); self.badge_photo=ctk.CTkImage(light_image=image,dark_image=image,size=image.size); self.badge_preview_label.configure(image=self.badge_photo,text="")
            info=self.badges.metadata(badge.name); self.badge_name_var.set(info.display_name if info else badge.stem.replace("-"," ").title()); self.badge_description_var.set(info.description if info else self.translator.text("badge.custom_description"))
        except OSError as error:self.badge_preview_label.configure(image=None,text=str(error))

    def open_images(self):
        selected=filedialog.askopenfilenames(title=self.translator.text("dialog.open_images"),filetypes=[(self.translator.text("files.supported"),"*.jpg *.jpeg *.png *.webp"),(self.translator.text("files.all"),"*.*")])
        if selected:self.sources=[Path(p) for p in selected if Path(p).suffix.lower() in SUPPORTED_EXTENSIONS]; self.file_label.configure(text=self.translator.text("files.selected",count=len(self.sources),name=self.sources[0].name) if self.sources else self.translator.text("files.none_supported")); self.update_preview()

    def update_preview(self):
        badge=self.badges.find(self.badge_var.get())
        if not self.sources or not badge:self.preview_label.configure(image=None,text=self.translator.text("preview.select_image")); return
        try:
            image=self.processor.process(self.sources[0],badge,self.settings()); image.thumbnail((720,600),Image.Resampling.LANCZOS); self.preview_photo=ctk.CTkImage(light_image=image,dark_image=image,size=image.size); self.preview_label.configure(image=self.preview_photo,text=""); self.status_var.set(self.translator.text("preview.showing",name=self.sources[0].name))
        except (OSError,ValueError) as error:self.status_var.set(self.translator.text("error.preview",error=error))

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
        try:open_user_guide(user_guide_path())
        except (OSError,FileNotFoundError) as error:messagebox.showerror(self.translator.text("error.title"),self.translator.text("guide.missing",error=error))

    def settings(self):
        return MarkerSettings(badge_name=self.badge_var.get(),position=self.position_var.get(),size_percent=self.size_var.get(),margin=self.margin_var.get(),opacity=self.opacity_var.get(),language=self.translator.language,badge_source=self.badge_source_var.get(),custom_badge_folder=self.custom_badge_var.get(),input_folder=self.input_folder_var.get(),output_preference=self.output_preference_var.get(),output_folder=self.output_folder_var.get(),output_subfolder=self.output_subfolder_var.get(),include_subfolders=self.recursive_var.get(),preserve_folder_structure=self.preserve_var.get(),process_images=self.images_var.get(),process_videos=self.videos_var.get(),skip_processed=self.skip_var.get(),video_mode="overlay").validated()
    def _save(self):
        try:self.config_store.save(self.settings())
        except OSError:pass
    def destroy(self):self.cancel_event.set(); self._save(); super().destroy()


def run():
    ctk.set_appearance_mode("system"); ctk.set_default_color_theme("blue"); MarkerApp().mainloop()
