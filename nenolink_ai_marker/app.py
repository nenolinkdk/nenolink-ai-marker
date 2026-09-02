from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from . import __version__
from .badges import BadgeRepository, BadgeSourceManager
from .config import ConfigStore
from .i18n import LANGUAGES, Translator
from .models import MarkerSettings
from .paths import badge_directory, locale_directory
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS, output_path

BADGES_DIR = badge_directory()
POSITION_LABELS = {
    "Top left": "top-left",
    "Top right": "top-right",
    "Bottom left": "bottom-left",
    "Bottom right": "bottom-right",
}


class MarkerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Nenolink AI Marker {__version__}")
        self.geometry("1100x760")
        self.minsize(900, 650)

        self.processor = ImageProcessor()
        self.config_store = ConfigStore()
        settings = self.config_store.load()
        self.translator = Translator(locale_directory(), settings.language)
        self.badge_sources = BadgeSourceManager(BADGES_DIR)
        self.badges = self.badge_sources.repository(settings.badge_source, settings.custom_badge_folder)
        self.sources: list[Path] = []
        self.preview_photo: ctk.CTkImage | None = None

        self.badge_var = ctk.StringVar(value=settings.badge_name)
        self.position_code = settings.position
        self.position_var = ctk.StringVar(value="")
        self.size_var = ctk.IntVar(value=settings.size_percent)
        self.margin_var = ctk.IntVar(value=settings.margin)
        self.opacity_var = ctk.IntVar(value=settings.opacity)
        self.language_var = ctk.StringVar(value=Translator.language_name(settings.language))
        self.badge_source_var = ctk.StringVar(value=settings.badge_source)
        self.custom_badge_var = ctk.StringVar(value=settings.custom_badge_folder)
        self.status_var = ctk.StringVar(value="")
        self.position_values: dict[str, str] = {}

        self._build_ui()
        self.apply_translations()
        self.refresh_badges()

    @staticmethod
    def _position_label(position: str) -> str:
        return next((label for label, value in POSITION_LABELS.items() if value == position), "Bottom right")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        controls = ctk.CTkScrollableFrame(self, width=330)
        controls.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        controls.grid_columnconfigure(0, weight=1)

        self.brand_label = ctk.CTkLabel(controls, text="Nenolink AI Marker", font=ctk.CTkFont(size=22, weight="bold"))
        self.brand_label.grid(
            row=0, column=0, padx=18, pady=(20, 14), sticky="w"
        )

        self.language_label = ctk.CTkLabel(controls, text="")
        self.language_label.grid(row=1, column=0, padx=18, sticky="w")
        self.language_menu = ctk.CTkOptionMenu(
            controls, variable=self.language_var, values=list(LANGUAGES), command=self.change_language
        )
        self.language_menu.grid(row=2, column=0, padx=18, pady=(3, 12), sticky="ew")

        self.open_button = ctk.CTkButton(controls, text="", command=self.open_images)
        self.open_button.grid(row=3, column=0, padx=18, pady=6, sticky="ew")
        self.file_label = ctk.CTkLabel(controls, text="", wraplength=280, justify="left")
        self.file_label.grid(row=4, column=0, padx=18, pady=(2, 12), sticky="w")

        self.settings_label = ctk.CTkLabel(controls, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.settings_label.grid(row=5, column=0, padx=18, pady=(6, 6), sticky="w")
        self.standard_radio = ctk.CTkRadioButton(
            controls, text="", variable=self.badge_source_var, value="standard", command=self.change_badge_source
        )
        self.standard_radio.grid(row=6, column=0, padx=18, pady=4, sticky="w")
        self.custom_radio = ctk.CTkRadioButton(
            controls, text="", variable=self.badge_source_var, value="custom", command=self.change_badge_source
        )
        self.custom_radio.grid(row=7, column=0, padx=18, pady=4, sticky="w")

        custom_row = ctk.CTkFrame(controls, fg_color="transparent")
        custom_row.grid(row=8, column=0, padx=18, pady=(2, 10), sticky="ew")
        custom_row.grid_columnconfigure(0, weight=1)
        self.custom_entry = ctk.CTkEntry(custom_row, textvariable=self.custom_badge_var)
        self.custom_entry.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.browse_button = ctk.CTkButton(custom_row, text="", width=80, command=self.browse_custom_badges)
        self.browse_button.grid(row=0, column=1)

        self.badge_label = ctk.CTkLabel(controls, text="")
        self.badge_label.grid(row=9, column=0, padx=18, sticky="w")
        self.badge_menu = ctk.CTkOptionMenu(controls, variable=self.badge_var, values=["—"], command=self.select_badge)
        self.badge_menu.grid(row=10, column=0, padx=18, pady=(3, 8), sticky="ew")
        self.refresh_button = ctk.CTkButton(controls, text="", fg_color="transparent", border_width=1, command=self.refresh_badges)
        self.refresh_button.grid(row=11, column=0, padx=18, pady=(0, 12), sticky="ew")

        self.position_label = ctk.CTkLabel(controls, text="")
        self.position_label.grid(row=12, column=0, padx=18, sticky="w")
        self.position_menu = ctk.CTkOptionMenu(controls, variable=self.position_var, values=["—"], command=self.change_position)
        self.position_menu.grid(row=13, column=0, padx=18, pady=(3, 10), sticky="ew")
        self.size_value_label = self._add_slider(controls, "size", self.size_var, 1, 100, 14)
        self.margin_value_label = self._add_slider(controls, "margin", self.margin_var, 0, 250, 16)
        self.opacity_value_label = self._add_slider(controls, "opacity", self.opacity_var, 0, 100, 18)

        self.save_button = ctk.CTkButton(controls, text="", command=self.save_images)
        self.save_button.grid(row=20, column=0, padx=18, pady=(18, 8), sticky="ew")
        ctk.CTkLabel(controls, text="© Henrik Nielsen · nenolink.com", text_color="gray60").grid(
            row=21, column=0, padx=18, pady=(6, 16), sticky="w"
        )

        preview_frame = ctk.CTkFrame(self)
        preview_frame.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_label = ctk.CTkLabel(preview_frame, text="", anchor="center")
        self.preview_label.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        ctk.CTkLabel(preview_frame, textvariable=self.status_var, anchor="w", wraplength=600).grid(
            row=1, column=0, padx=16, pady=(0, 14), sticky="ew"
        )

    def _add_slider(self, parent: ctk.CTkFrame, key: str, variable: ctk.IntVar, start: int, end: int, row: int) -> ctk.CTkLabel:
        value_label = ctk.CTkLabel(parent, text="")
        value_label.grid(row=row, column=0, padx=18, sticky="w")

        def changed(value: float) -> None:
            variable.set(round(value))
            value_label.configure(text=self.translator.text(f"{key}.value", value=variable.get()))
            self.update_preview()

        ctk.CTkSlider(parent, from_=start, to=end, number_of_steps=end - start, variable=variable, command=changed).grid(
            row=row + 1, column=0, padx=18, pady=(2, 10), sticky="ew"
        )
        return value_label

    def apply_translations(self) -> None:
        t = self.translator.text
        self.title(f"Nenolink AI Marker {__version__} — {t('app.window')}")
        self.language_label.configure(text=t("language"))
        self.open_button.configure(text=t("button.open_images"))
        self.file_label.configure(text=t("files.none") if not self.sources else t("files.selected", count=len(self.sources), name=self.sources[0].name))
        self.settings_label.configure(text=t("menu.settings"))
        self.standard_radio.configure(text=t("badge.standard"))
        self.custom_radio.configure(text=t("badge.custom"))
        self.custom_entry.configure(placeholder_text=t("badge.custom_path"))
        self.browse_button.configure(text=t("button.browse"))
        self.badge_label.configure(text=t("badge"))
        self.refresh_button.configure(text=t("badge.refresh"))
        self.position_label.configure(text=t("position"))
        self.save_button.configure(text=t("button.process"))
        self.size_value_label.configure(text=t("size.value", value=self.size_var.get()))
        self.margin_value_label.configure(text=t("margin.value", value=self.margin_var.get()))
        self.opacity_value_label.configure(text=t("opacity.value", value=self.opacity_var.get()))
        self.position_values = {
            t("position.top_left"): "top-left", t("position.top_right"): "top-right",
            t("position.bottom_left"): "bottom-left", t("position.bottom_right"): "bottom-right",
        }
        self.position_menu.configure(values=list(self.position_values))
        self.position_var.set(next(label for label, code in self.position_values.items() if code == self.position_code))

    def change_language(self, language_name: str) -> None:
        self.translator.set_language(LANGUAGES.get(language_name, "en"))
        self.apply_translations()
        self.refresh_badges()
        self._save_settings_safely()

    def change_position(self, label: str) -> None:
        self.position_code = self.position_values.get(label, "bottom-right")
        self.update_preview()

    def change_badge_source(self) -> None:
        self.refresh_badges()
        self._save_settings_safely()

    def select_badge(self, _badge_name: str) -> None:
        self.update_preview()
        self._save_settings_safely()

    def browse_custom_badges(self) -> None:
        selected = filedialog.askdirectory(title=self.translator.text("dialog.custom_badges"))
        if selected:
            self.custom_badge_var.set(selected)
            self.badge_source_var.set("custom")
            self.refresh_badges()
            self._save_settings_safely()

    def _save_settings_safely(self) -> None:
        try:
            self.config_store.save(self.settings())
        except OSError:
            pass

    def refresh_badges(self) -> None:
        self.badges = self.badge_sources.repository(self.badge_source_var.get(), self.custom_badge_var.get())
        missing_custom = self.badge_sources.fallback_reason
        if missing_custom:
            self.badge_source_var.set("standard")
        badge_names = [path.name for path in self.badges.list_badges()]
        values = badge_names or [self.translator.text("badge.none")]
        self.badge_menu.configure(values=values)
        if self.badge_var.get() not in badge_names:
            self.badge_var.set(badge_names[0] if badge_names else values[0])
        if missing_custom:
            self.status_var.set(self.translator.text("badge.custom_missing", folder=missing_custom, fallback=self.badges.directory))
        elif badge_names:
            self.status_var.set(self.translator.text("badge.found", count=len(badge_names), folder=self.badges.directory))
        else:
            self.status_var.set(self.translator.text("badge.not_found", folder=self.badges.directory))
        self.update_preview()

    def open_images(self) -> None:
        selected = filedialog.askopenfilenames(
            title=self.translator.text("dialog.open_images"),
            filetypes=[(self.translator.text("files.supported"), "*.jpg *.jpeg *.png *.webp"), (self.translator.text("files.all"), "*.*")],
        )
        if not selected:
            return
        self.sources = [Path(name) for name in selected if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS]
        self.file_label.configure(text=self.translator.text("files.selected", count=len(self.sources), name=self.sources[0].name) if self.sources else self.translator.text("files.none_supported"))
        self.update_preview()

    def settings(self) -> MarkerSettings:
        return MarkerSettings(
            badge_name=self.badge_var.get(),
            position=self.position_code,
            size_percent=self.size_var.get(),
            margin=self.margin_var.get(),
            opacity=self.opacity_var.get(),
            language=self.translator.language,
            badge_source=self.badge_source_var.get(),
            custom_badge_folder=self.custom_badge_var.get(),
        ).validated()

    def _selection(self) -> tuple[Path, Path] | None:
        if not self.sources:
            return None
        badge = self.badges.find(self.badge_var.get())
        return (self.sources[0], badge) if badge else None

    def update_preview(self) -> None:
        selection = self._selection()
        if not selection:
            if not self.badges.list_badges():
                text = self.translator.text("badge.not_found_preview", folder=self.badges.directory)
            else:
                text = self.translator.text("preview.select_image")
            self.preview_label.configure(image=None, text=text)
            return
        try:
            preview = self.processor.process(*selection, self.settings())
            preview.thumbnail((640, 540), Image.Resampling.LANCZOS)
            self.preview_photo = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
            self.preview_label.configure(image=self.preview_photo, text="")
            self.status_var.set(self.translator.text("preview.showing", name=selection[0].name))
        except (OSError, ValueError) as error:
            self.status_var.set(self.translator.text("error.preview", error=error))

    def save_images(self) -> None:
        badge = self.badges.find(self.badge_var.get())
        if not self.sources or not badge:
            messagebox.showwarning(self.translator.text("warning.title"), self.translator.text("warning.nothing_to_save"))
            return
        destination = filedialog.askdirectory(title=self.translator.text("dialog.output_folder"))
        if not destination:
            return
        settings = self.settings()
        failures: list[str] = []
        saved: list[Path] = []
        for source in self.sources:
            try:
                result = self.processor.process(source, badge, settings)
                target = output_path(source, Path(destination))
                self.processor.save(result, target)
                saved.append(target)
            except (OSError, ValueError) as error:
                failures.append(f"{source.name}: {error}")
        try:
            self.config_store.save(settings)
        except OSError as error:
                failures.append(self.translator.text("error.settings", error=error))
        summary = self.translator.text("process.summary", saved=len(saved), total=len(self.sources))
        if failures:
            messagebox.showerror(self.translator.text("error.completed"), summary + "\n\n" + "\n".join(failures[:8]))
        else:
            messagebox.showinfo(self.translator.text("complete.title"), summary)
        self.status_var.set(summary)

    def destroy(self) -> None:
        try:
            self.config_store.save(self.settings())
        except OSError:
            pass
        super().destroy()


def run() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    MarkerApp().mainloop()
