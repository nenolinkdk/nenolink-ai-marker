"""Shared presentation tokens for workspace control columns.

These values describe layout only; they intentionally own no workspace state.
"""

from dataclasses import dataclass


class Section:
    """Stateless section container used only for presentation structure."""
    def __init__(self, parent, *, title: str = "", padding=(0, 0), gap: int = 4):
        import customtkinter as ctk
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.heading = ctk.CTkLabel(self.frame, text=title,
                                    font=ctk.CTkFont(weight="bold"))
        if title:
            self.heading.grid(row=0, column=0, padx=padding[0], pady=(padding[1], gap), sticky="w")

    def set_title(self, title: str) -> None:
        self.heading.configure(text=title)


@dataclass(frozen=True)
class WorkspaceLayoutTokens:
    section_gap: int = 4
    row_gap: int = 1
    heading_gap: int = 2
    control_width: int = 320
    dropdown_width: int = 180
    slider_width: int = 260
    badge_row_height: int = 62
    badge_thumbnail_width: int = 110
    badge_thumbnail_height: int = 54


WORKSPACE_LAYOUT = WorkspaceLayoutTokens()


def build_badge_visual(parent, *, name_variable=None):
    """Create the shared stateless badge image/name projection widget."""
    import customtkinter as ctk
    return ctk.CTkLabel(
        parent, textvariable=name_variable, anchor="w", compound="left",
        width=WORKSPACE_LAYOUT.badge_thumbnail_width,
        height=WORKSPACE_LAYOUT.badge_row_height,
    )


def build_badge_section(parent, *, enabled_var, badge_var, badge_values,
                        on_enabled, on_selected, on_position, on_size,
                        on_margin, on_opacity, position_values,
                        initial_position="bottom-right"):
    """Build a stateless AI BADGE presentation section.

    The caller supplies Tk variables and callbacks; this helper never stores or
    mutates workspace runtime state.  Returned widgets are presentation
    adapters that emit the supplied workspace events.
    """
    import customtkinter as ctk
    section = Section(parent, title="AI BADGE")
    frame = section.frame
    ctk.CTkCheckBox(frame, text="Add AI badge", variable=enabled_var,
                    command=on_enabled).grid(row=1, column=0, sticky="w")
    menu = ctk.CTkOptionMenu(frame, variable=badge_var, values=list(badge_values),
                             command=on_selected, width=WORKSPACE_LAYOUT.dropdown_width)
    menu.grid(row=2, column=0, sticky="w", pady=WORKSPACE_LAYOUT.row_gap)
    ctk.CTkLabel(frame, text="Badge Position").grid(row=3, column=0, sticky="w")
    position = ctk.CTkOptionMenu(frame, values=list(position_values), command=on_position,
                                 width=WORKSPACE_LAYOUT.dropdown_width)
    position.set(initial_position)
    position.grid(row=4, column=0, sticky="w")
    size = ctk.CTkSlider(frame, from_=1, to=100, number_of_steps=99, command=on_size,
                         width=WORKSPACE_LAYOUT.slider_width)
    margin = ctk.CTkSlider(frame, from_=0, to=250, number_of_steps=250, command=on_margin,
                           width=WORKSPACE_LAYOUT.slider_width)
    opacity = ctk.CTkSlider(frame, from_=0, to=100, number_of_steps=100, command=on_opacity,
                            width=WORKSPACE_LAYOUT.slider_width)
    for row, label, slider in ((5, "Badge Size", size), (7, "Margin", margin), (9, "Opacity", opacity)):
        ctk.CTkLabel(frame, text=label).grid(row=row, column=0, sticky="w")
        slider.grid(row=row + 1, column=0, sticky="w")
    return {"frame": frame, "badge_menu": menu, "position_menu": position,
            "size_slider": size, "margin_slider": margin, "opacity_slider": opacity}


def build_logo_section(parent, *, enabled_var, on_enabled, on_choose,
                       on_position, on_size, on_margin, on_opacity,
                       position_values):
    """Build a stateless OWN LOGO presentation section."""
    import customtkinter as ctk
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text="OWN LOGO", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
    ctk.CTkCheckBox(frame, text="Add own logo", variable=enabled_var,
                    command=on_enabled).grid(row=1, column=0, sticky="w")
    ctk.CTkButton(frame, text="Choose Logo", command=on_choose,
                  width=WORKSPACE_LAYOUT.dropdown_width).grid(row=2, column=0, sticky="w")
    position = ctk.CTkOptionMenu(frame, values=list(position_values), command=on_position,
                                 width=WORKSPACE_LAYOUT.dropdown_width)
    position.grid(row=3, column=0, sticky="w", pady=WORKSPACE_LAYOUT.row_gap)
    logo_sliders = []
    for row, label, callback, maximum in ((4, "Logo Size", on_size, 100),
                                          (6, "Logo Margin", on_margin, 250),
                                          (8, "Logo Opacity", on_opacity, 100)):
        ctk.CTkLabel(frame, text=label).grid(row=row, column=0, sticky="w")
        slider = ctk.CTkSlider(frame, from_=0 if maximum == 250 else 1, to=maximum,
                      number_of_steps=maximum, command=callback,
                      width=WORKSPACE_LAYOUT.slider_width)
        slider.grid(row=row + 1, column=0, sticky="w")
        logo_sliders.append(slider)
    return {"frame": frame, "position_menu": position, "sliders": logo_sliders}


def build_workspace_control_template(parent, *, format_label, choose_command,
                                     save_command, scope_label, scope_command,
                                     scope_update, badge_enabled_var, badge_var,
                                     badge_values, badge_callbacks, logo_enabled_var,
                                     logo_callbacks, position_values):
    """Compose one complete left-column view from projected values/callbacks.

    This is deliberately a view builder: it owns widgets only. Runtime state
    remains in the format-specific workspace state and callbacks are adapters.
    """
    import customtkinter as ctk
    root = ctk.CTkFrame(parent, fg_color="transparent")
    root.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(root, text=format_label, font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
    actions = ctk.CTkFrame(root, fg_color="transparent"); actions.grid(row=1, column=0, sticky="w")
    choose = ctk.CTkButton(actions, text=f"Choose {format_label}", command=choose_command, width=180); choose.grid(row=0, column=0, padx=(0, 6))
    save = ctk.CTkButton(actions, text=f"Save Marked {format_label}...", command=save_command, width=190); save.grid(row=0, column=1)
    file_label = ctk.CTkLabel(root, text="No file selected", anchor="w"); file_label.grid(row=2, column=0, sticky="w")
    scope = None
    if scope_label:
        scope = ctk.CTkFrame(root, fg_color="transparent"); scope.grid(row=3, column=0, sticky="w", pady=(WORKSPACE_LAYOUT.section_gap, 0))
        ctk.CTkLabel(scope, text=scope_label, font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
        menu = ctk.CTkOptionMenu(scope, values=["All", "First", "Selected", "Range"], command=scope_command, width=WORKSPACE_LAYOUT.dropdown_width); menu.grid(row=1, column=0, sticky="w")
        entry = ctk.CTkEntry(scope, placeholder_text="2,4-6,9"); entry.grid(row=2, column=0, sticky="w", pady=WORKSPACE_LAYOUT.row_gap)
        update = ctk.CTkButton(scope, text="Update", command=scope_update, width=100); update.grid(row=3, column=0, sticky="w")
    badge = build_badge_section(root, enabled_var=badge_enabled_var, badge_var=badge_var,
                                badge_values=badge_values, position_values=position_values,
                                on_enabled=badge_callbacks[0], on_selected=badge_callbacks[1],
                                on_position=badge_callbacks[2], on_size=badge_callbacks[3],
                                on_margin=badge_callbacks[4], on_opacity=badge_callbacks[5])
    badge["frame"].grid(row=4 if scope else 3, column=0, sticky="w", pady=(WORKSPACE_LAYOUT.section_gap, 0))
    logo = build_logo_section(root, enabled_var=logo_enabled_var,
                              position_values=position_values,
                              on_enabled=logo_callbacks[0], on_choose=logo_callbacks[1],
                              on_position=logo_callbacks[2], on_size=logo_callbacks[3],
                              on_margin=logo_callbacks[4], on_opacity=logo_callbacks[5])
    logo["frame"].grid(row=(5 if scope else 4), column=0, sticky="w", pady=(WORKSPACE_LAYOUT.section_gap, 0))
    return {"root": root, "choose": choose, "save": save, "file_label": file_label,
            "scope": scope, "badge": badge, "logo": logo}
