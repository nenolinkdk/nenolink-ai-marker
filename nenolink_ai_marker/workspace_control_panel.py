"""Stateless sequential composition for workspace control columns."""
from __future__ import annotations

from typing import Any
import customtkinter as ctk


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

    def add_section(self, name: str, block: Any, *, padx: int = 12, pady: tuple[int, int] = (4, 4)) -> Any:
        """Attach one natural-height block at the next consecutive row."""
        row = self._next_row
        block.grid(row=row, column=0, padx=padx, pady=pady, sticky="ew")
        self.sections[name] = block
        self._next_row += 1
        return block

    @property
    def row_count(self) -> int:
        return self._next_row
