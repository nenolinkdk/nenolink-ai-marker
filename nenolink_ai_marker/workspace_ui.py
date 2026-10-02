"""Shared presentation tokens for workspace control columns.

These values describe layout only; they intentionally own no workspace state.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceLayoutTokens:
    section_gap: int = 6
    row_gap: int = 2
    heading_gap: int = 2
    control_width: int = 320
    dropdown_width: int = 180
    slider_width: int = 260
    badge_row_height: int = 62
    badge_thumbnail_width: int = 110
    badge_thumbnail_height: int = 54


WORKSPACE_LAYOUT = WorkspaceLayoutTokens()


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
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text="AI BADGE", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
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
    for row, label, callback, maximum in ((4, "Logo Size", on_size, 100),
                                          (6, "Logo Margin", on_margin, 250),
                                          (8, "Logo Opacity", on_opacity, 100)):
        ctk.CTkLabel(frame, text=label).grid(row=row, column=0, sticky="w")
        ctk.CTkSlider(frame, from_=0 if maximum == 250 else 1, to=maximum,
                      number_of_steps=maximum, command=callback,
                      width=WORKSPACE_LAYOUT.slider_width).grid(row=row + 1, column=0, sticky="w")
    return {"frame": frame, "position_menu": position}
