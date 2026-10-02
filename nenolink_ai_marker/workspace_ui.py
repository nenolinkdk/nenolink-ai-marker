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
