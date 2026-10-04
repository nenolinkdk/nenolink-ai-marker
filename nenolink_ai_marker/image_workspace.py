"""Image workspace UI ownership during the Image migration.

The workspace receives the existing ImageWorkspaceState and injected legacy
callbacks/resources.  MarkerApp remains a temporary lifecycle entry adapter;
widget construction lives here.
"""
from __future__ import annotations

import customtkinter as ctk


class ImageWorkspace:
    def __init__(self, app, state, *, scrollable_frame_cls):
        self.app = app
        self.state = state
        self.scrollable_frame_cls = scrollable_frame_cls
        self.root = None

    def mount(self, host):
        """Own Image view creation and projection; registry switch is deferred."""
        if self.root is not None and self.root.winfo_exists():
            self.root.grid()
            self.project()
            return
        self.app._clear_content_host()
        self.root = ctk.CTkFrame(host, fg_color="transparent")
        self.root.grid(row=0, column=0, sticky="nsew")
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.app.image_workspace = self.root
        self._build_ui(self.root)
        self.project()
        self.app.apply_image_translations()
        self.app._validate_saved_logo()
        self.app._show_welcome()

    def unmount(self):
        if self.root is not None and self.root.winfo_exists():
            self.root.grid_remove()

    def has_active_work(self):
        return bool(self.state.selected_files)

    def clear_runtime_state(self):
        self.state.clear_runtime_state()

    def project(self):
        """Project authoritative state through the existing app adapters."""
        if self.root is not None and self.root.winfo_exists():
            self.app.refresh_image_badges()

    def _slider(self, parent, variable, start, end, row):
        app = self.app
        label = ctk.CTkLabel(parent)
        label.grid(row=row, column=0, padx=14, pady=(4, 0), sticky="w")
        ctk.CTkSlider(parent, from_=start, to=end, number_of_steps=end-start,
                      variable=variable, command=app.changed).grid(
                          row=row + 1, column=0, padx=14, pady=(1, 3), sticky="ew")
        return label

    def _build_ui(self, workspace):
        """Build the existing Image controls; this is the sole UI builder."""
        app = self.app
        workspace.grid_columnconfigure(1, weight=1)
        workspace.grid_rowconfigure(0, weight=1)
        left = self.scrollable_frame_cls(workspace, width=320, fg_color=("gray86", "gray17"))
        app.image_controls = left
        left.grid(row=0, column=0, padx=(4, 8), pady=4, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        app.open_button = ctk.CTkButton(left, command=app.open_images)
        app.open_button.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="ew")
        app.file_label = ctk.CTkLabel(left, anchor="w", justify="left", wraplength=280)
        app.file_label.grid(row=1, column=0, padx=14, pady=3, sticky="ew")
        app.file_size_guidance = ctk.CTkLabel(left, anchor="w", justify="left", wraplength=280, text_color="gray60")
        app.file_size_guidance.grid(row=2, column=0, padx=14, pady=(0, 4), sticky="ew")
        badge_section = ctk.CTkFrame(left)
        badge_section.grid(row=3, column=0, padx=14, pady=(4, 4), sticky="ew")
        badge_section.grid_columnconfigure(0, weight=1)
        app.badge_enable = ctk.CTkCheckBox(badge_section, variable=app.badge_enabled_var, command=app.badge_enabled_changed)
        app.badge_enable.grid(row=0, column=0, padx=8, pady=(7, 3), sticky="w")
        app.single_badge_label = ctk.CTkLabel(badge_section, font=ctk.CTkFont(weight="bold"))
        app.single_badge_label.grid(row=1, column=0, padx=8, pady=(2, 1), sticky="w")
        app.badge_menu = ctk.CTkOptionMenu(badge_section, variable=app.badge_display_var, values=["—"], command=app.select_badge_display)
        app.badge_menu.grid(row=2, column=0, padx=8, pady=2, sticky="ew")
        badge_preview = ctk.CTkFrame(badge_section)
        badge_preview.grid(row=3, column=0, padx=8, pady=(3, 7), sticky="ew")
        badge_preview.grid_columnconfigure(1, weight=1)
        app.single_badge_preview_label = ctk.CTkLabel(badge_preview, width=90, height=44)
        app.single_badge_preview_label.grid(row=0, column=0, padx=5, pady=5)
        app.single_badge_name_label = ctk.CTkLabel(badge_preview, textvariable=app.badge_name_var, font=ctk.CTkFont(weight="bold"), anchor="w", wraplength=155)
        app.single_badge_name_label.grid(row=0, column=1, padx=(3, 5), pady=5, sticky="ew")
        app.position_label = ctk.CTkLabel(left)
        app.position_label.grid(row=4, column=0, padx=14, pady=(5, 1), sticky="w")
        app.position_menu = ctk.CTkOptionMenu(left, variable=app.position_display_var, values=["—"], command=app.change_position_display)
        app.position_menu.grid(row=5, column=0, padx=14, pady=2, sticky="ew")
        app.size_label = self._slider(left, app.size_var, 1, 100, 6)
        app.margin_label = self._slider(left, app.margin_var, 0, 250, 8)
        app.opacity_label = self._slider(left, app.opacity_var, 0, 100, 10)
        app.logo_controls = ctk.CTkFrame(left)
        app.logo_controls.grid(row=12, column=0, padx=14, pady=(5, 8), sticky="ew")
        app.logo_controls.grid_columnconfigure(1, weight=1)
        app.logo_heading = ctk.CTkLabel(app.logo_controls, font=ctk.CTkFont(weight="bold")); app.logo_heading.grid(row=0, column=0, columnspan=2, padx=8, pady=(6, 2), sticky="w")
        app.logo_enable = ctk.CTkCheckBox(app.logo_controls, variable=app.logo_enabled_var, command=app.logo_changed); app.logo_enable.grid(row=1, column=0, columnspan=2, padx=8, pady=3, sticky="w")
        app.logo_choose = ctk.CTkButton(app.logo_controls, command=app.choose_logo, height=28); app.logo_choose.grid(row=2, column=0, padx=8, pady=3, sticky="w")
        app.logo_filename = ctk.CTkLabel(app.logo_controls, textvariable=app.logo_filename_var, anchor="w", wraplength=155); app.logo_filename.grid(row=2, column=1, padx=(2, 8), pady=3, sticky="ew")
        app.logo_position_label = ctk.CTkLabel(app.logo_controls); app.logo_position_label.grid(row=3, column=0, padx=8, pady=2, sticky="w")
        app.logo_position_menu = ctk.CTkOptionMenu(app.logo_controls, variable=app.logo_position_display_var, values=["—"], command=app.change_logo_position, height=28); app.logo_position_menu.grid(row=3, column=1, padx=8, pady=2, sticky="ew")
        app.logo_size_label = ctk.CTkLabel(app.logo_controls); app.logo_size_label.grid(row=4, column=0, columnspan=2, padx=8, sticky="w")
        app.logo_size_slider = ctk.CTkSlider(app.logo_controls, from_=1, to=100, number_of_steps=99, variable=app.logo_size_var, command=app.logo_changed); app.logo_size_slider.grid(row=5, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        app.logo_margin_label = ctk.CTkLabel(app.logo_controls); app.logo_margin_label.grid(row=6, column=0, columnspan=2, padx=8, sticky="w")
        app.logo_margin_slider = ctk.CTkSlider(app.logo_controls, from_=0, to=250, number_of_steps=250, variable=app.logo_margin_var, command=app.logo_changed); app.logo_margin_slider.grid(row=7, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        app.logo_opacity_label = ctk.CTkLabel(app.logo_controls); app.logo_opacity_label.grid(row=8, column=0, columnspan=2, padx=8, sticky="w")
        app.logo_opacity_slider = ctk.CTkSlider(app.logo_controls, from_=0, to=100, number_of_steps=100, variable=app.logo_opacity_var, command=app.logo_changed); app.logo_opacity_slider.grid(row=9, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="ew")
        app.logo_images_only = ctk.CTkLabel(app.logo_controls, text_color="gray60"); app.logo_images_only.grid(row=10, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w")
        app.process_button = ctk.CTkButton(left, command=app.save_images); app.process_button.grid(row=13, column=0, padx=14, pady=(2, 10), sticky="ew")
        right = ctk.CTkFrame(workspace); right.grid(row=0, column=1, padx=(8, 4), pady=4, sticky="nsew"); right.grid_columnconfigure(0, weight=1); right.grid_rowconfigure(0, weight=1)
        app.preview_label = ctk.CTkLabel(right)
        app.welcome_frame = ctk.CTkFrame(right, fg_color="transparent"); app.welcome_frame.grid(row=0, column=0, padx=18, pady=14, sticky="nsew"); app.welcome_frame.grid_columnconfigure(0, weight=1); app.welcome_frame.grid_rowconfigure(4, weight=1)
        app.welcome_title = ctk.CTkLabel(app.welcome_frame, font=ctk.CTkFont(size=28, weight="bold")); app.welcome_title.grid(row=0, column=0, padx=12, pady=(12, 4))
        app.welcome_tagline = ctk.CTkLabel(app.welcome_frame, font=ctk.CTkFont(size=18, weight="bold"), text_color=("#2469a0", "#65b6ef")); app.welcome_tagline.grid(row=1, column=0, padx=12, pady=(0, 10))
        app.welcome_description1 = ctk.CTkLabel(app.welcome_frame, wraplength=720, justify="center"); app.welcome_description1.grid(row=2, column=0, padx=18, pady=2)
        app.welcome_description2 = ctk.CTkLabel(app.welcome_frame, wraplength=720, justify="center"); app.welcome_description2.grid(row=3, column=0, padx=18, pady=(2, 10))
        app.welcome_illustration = ctk.CTkLabel(app.welcome_frame, anchor="center"); app.welcome_illustration.grid(row=4, column=0, padx=12, pady=(4, 12), sticky="nsew")
        app._load_image_welcome(); app.welcome_frame.bind("<Configure>", app._resize_image_welcome)
