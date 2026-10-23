"""Stateless sequential composition for workspace control columns."""
from __future__ import annotations

from typing import Any
import customtkinter as ctk

PARAM_LABEL_WIDTH = 110
PARAM_CONTROL_WIDTH = 205
PARAM_DROPDOWN_WIDTH = 205
PARAM_PADX = 8
PARAM_LABEL_PADY = (2, 0)
PARAM_SLIDER_PADY = (1, 3)
BADGE_PREVIEW_PADY = (4, 0)
PARAM_ROW_PADY = (0, 2)
PANEL_SECTION_PADY = (3, 3)
FILE_CHOOSE_WIDTH = 148
FILE_SAVE_WIDTH = 120
FILE_ACTION_GAP = 6


class ParameterRow:
    """A stateless, consistently sized label/slider presentation row."""

    def __init__(self, parent, *, text, start, end, value, command, variable=None):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(self.frame, text=text, width=PARAM_LABEL_WIDTH, anchor="w")
        self.label.grid(row=0, column=0, padx=PARAM_PADX, pady=PARAM_LABEL_PADY, sticky="w")
        self.slider = ctk.CTkSlider(
            self.frame, from_=start, to=end, width=PARAM_CONTROL_WIDTH,
            number_of_steps=end - start, command=command, variable=variable,
        )
        self.slider.grid(row=1, column=0, padx=PARAM_PADX, pady=PARAM_SLIDER_PADY, sticky="ew")
        self.slider.set(value)

    def project(self, *, text, value):
        self.label.configure(text=text)
        self.slider.set(value)


class WorkspaceControlPanel:
    """Owns only compact section placement; workspaces own all semantics."""

    def __init__(self, parent: Any, *, width: int = 320, scrollable_frame_cls=None) -> None:
        frame_cls = scrollable_frame_cls or ctk.CTkScrollableFrame
        self.frame = frame_cls(parent, width=width, fg_color=("gray86", "gray17"))
        self.frame.grid_columnconfigure(0, weight=1)
        self._next_row = 0
        self.sections: dict[str, Any] = {}
        self.section_order: list[str] = []

    def declare_section(self, name: str) -> None:
        if name not in self.section_order:
            self.section_order.append(name)

    def add_section(self, name: str, block: Any, *, padx: int = 12, pady: tuple[int, int] = PANEL_SECTION_PADY) -> Any:
        """Attach one natural-height block at the next consecutive row."""
        row = self._next_row
        block.grid(row=row, column=0, padx=padx, pady=pady, sticky="ew")
        self.sections[name] = block
        self._next_row += 1
        return block

    @property
    def row_count(self) -> int:
        return self._next_row
