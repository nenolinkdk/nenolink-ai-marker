from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from .badges import BadgeRepository
from .config import ConfigStore
from .models import MarkerSettings
from .processor import ImageProcessor, SUPPORTED_EXTENSIONS, output_path

ROOT_DIR = Path(__file__).resolve().parent.parent
BADGES_DIR = ROOT_DIR / "assets" / "badges"
POSITION_LABELS = {
    "Top left": "top-left",
    "Top right": "top-right",
    "Bottom left": "bottom-left",
    "Bottom right": "bottom-right",
}


class MarkerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Nenolink AI Marker 0.1")
        self.geometry("1000x680")
        self.minsize(820, 580)

        self.processor = ImageProcessor()
        self.badges = BadgeRepository(BADGES_DIR)
        self.config_store = ConfigStore()
        self.sources: list[Path] = []
        self.preview_photo: ctk.CTkImage | None = None

        settings = self.config_store.load()
        self.badge_var = ctk.StringVar(value=settings.badge_name)
        self.position_var = ctk.StringVar(value=self._position_label(settings.position))
        self.size_var = ctk.IntVar(value=settings.size_percent)
        self.margin_var = ctk.IntVar(value=settings.margin)
        self.opacity_var = ctk.IntVar(value=settings.opacity)
        self.status_var = ctk.StringVar(value="Select one or more images to begin.")

        self._build_ui()
        self.refresh_badges()

    @staticmethod
    def _position_label(position: str) -> str:
        return next((label for label, value in POSITION_LABELS.items() if value == position), "Bottom right")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        controls = ctk.CTkFrame(self, width=300)
        controls.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        controls.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(controls, text="Nenolink AI Marker", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(20, 14), sticky="w"
        )
        ctk.CTkButton(controls, text="Open images", command=self.open_images).grid(
            row=1, column=0, padx=18, pady=6, sticky="ew"
        )
        self.file_label = ctk.CTkLabel(controls, text="No images selected", wraplength=250, justify="left")
        self.file_label.grid(row=2, column=0, padx=18, pady=(2, 12), sticky="w")

        ctk.CTkLabel(controls, text="Badge").grid(row=3, column=0, padx=18, sticky="w")
        self.badge_menu = ctk.CTkOptionMenu(controls, variable=self.badge_var, values=["No badges found"], command=lambda _: self.update_preview())
        self.badge_menu.grid(row=4, column=0, padx=18, pady=(3, 10), sticky="ew")
        ctk.CTkButton(controls, text="Refresh badges", fg_color="transparent", border_width=1, command=self.refresh_badges).grid(
            row=5, column=0, padx=18, pady=(0, 12), sticky="ew"
        )

        ctk.CTkLabel(controls, text="Position").grid(row=6, column=0, padx=18, sticky="w")
        ctk.CTkOptionMenu(controls, variable=self.position_var, values=list(POSITION_LABELS), command=lambda _: self.update_preview()).grid(
            row=7, column=0, padx=18, pady=(3, 10), sticky="ew"
        )
        self._add_slider(controls, "Size (% of image width)", self.size_var, 1, 100, 8)
        self._add_slider(controls, "Margin (pixels)", self.margin_var, 0, 250, 10)
        self._add_slider(controls, "Opacity (%)", self.opacity_var, 0, 100, 12)

        ctk.CTkButton(controls, text="Save marked images", command=self.save_images).grid(
            row=14, column=0, padx=18, pady=(18, 8), sticky="ew"
        )

        preview_frame = ctk.CTkFrame(self)
        preview_frame.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_label = ctk.CTkLabel(preview_frame, text="Preview", anchor="center")
        self.preview_label.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        ctk.CTkLabel(preview_frame, textvariable=self.status_var, anchor="w", wraplength=600).grid(
            row=1, column=0, padx=16, pady=(0, 14), sticky="ew"
        )

    def _add_slider(self, parent: ctk.CTkFrame, label: str, variable: ctk.IntVar, start: int, end: int, row: int) -> None:
        value_label = ctk.CTkLabel(parent, text=f"{label}: {variable.get()}")
        value_label.grid(row=row, column=0, padx=18, sticky="w")

        def changed(value: float) -> None:
            variable.set(round(value))
            value_label.configure(text=f"{label}: {variable.get()}")
            self.update_preview()

        ctk.CTkSlider(parent, from_=start, to=end, number_of_steps=end - start, variable=variable, command=changed).grid(
            row=row + 1, column=0, padx=18, pady=(2, 10), sticky="ew"
        )

    def refresh_badges(self) -> None:
        badge_names = [path.name for path in self.badges.list_badges()]
        values = badge_names or ["No badges found"]
        self.badge_menu.configure(values=values)
        if self.badge_var.get() not in badge_names:
            self.badge_var.set(badge_names[0] if badge_names else values[0])
        self.update_preview()

    def open_images(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Open images",
            filetypes=[("Supported images", "*.jpg *.jpeg *.png *.webp"), ("All files", "*.*")],
        )
        if not selected:
            return
        self.sources = [Path(name) for name in selected if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS]
        self.file_label.configure(text=f"{len(self.sources)} image(s) selected\n{self.sources[0].name}" if self.sources else "No supported images selected")
        self.update_preview()

    def settings(self) -> MarkerSettings:
        return MarkerSettings(
            badge_name=self.badge_var.get(),
            position=POSITION_LABELS.get(self.position_var.get(), "bottom-right"),
            size_percent=self.size_var.get(),
            margin=self.margin_var.get(),
            opacity=self.opacity_var.get(),
        ).validated()

    def _selection(self) -> tuple[Path, Path] | None:
        if not self.sources:
            return None
        badge = self.badges.find(self.badge_var.get())
        return (self.sources[0], badge) if badge else None

    def update_preview(self) -> None:
        selection = self._selection()
        if not selection:
            self.preview_label.configure(image=None, text="Add approved PNG badges to assets/badges/\nand select one or more images.")
            return
        try:
            preview = self.processor.process(*selection, self.settings())
            preview.thumbnail((640, 540), Image.Resampling.LANCZOS)
            self.preview_photo = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
            self.preview_label.configure(image=self.preview_photo, text="")
            self.status_var.set(f"Previewing {selection[0].name}")
        except (OSError, ValueError) as error:
            self.status_var.set(f"Preview error: {error}")

    def save_images(self) -> None:
        badge = self.badges.find(self.badge_var.get())
        if not self.sources or not badge:
            messagebox.showwarning("Nothing to save", "Select images and an approved badge first.")
            return
        destination = filedialog.askdirectory(title="Choose output folder")
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
            failures.append(f"Settings could not be saved: {error}")
        summary = f"Saved {len(saved)} of {len(self.sources)} image(s). Originals were not changed."
        if failures:
            messagebox.showerror("Completed with errors", summary + "\n\n" + "\n".join(failures[:8]))
        else:
            messagebox.showinfo("Complete", summary)
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

