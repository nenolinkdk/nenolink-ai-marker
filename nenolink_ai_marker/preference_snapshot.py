"""Immutable preference snapshots and one-way UI compatibility projection.

Persistent settings seed workspace state at mount time.  Tk variables are
adapters for unmigrated workspaces and never the preference authority.
"""
from dataclasses import dataclass
from typing import Any

from .models import MarkerSettings


@dataclass(frozen=True, slots=True)
class VisualPreferenceSnapshot:
    badge_name: str
    position: str
    size_percent: int
    margin: int
    opacity: int
    logo_enabled: bool
    logo_path: str
    logo_position: str
    logo_size_percent: int
    logo_margin: int
    logo_opacity: int
    video_mode: str
    video_duration: int

    @classmethod
    def from_settings(cls, settings: MarkerSettings) -> "VisualPreferenceSnapshot":
        value = settings.validated()
        return cls(value.badge_name, value.position, value.size_percent,
                   value.margin, value.opacity, value.logo_enabled,
                   value.logo_path, value.logo_position, value.logo_size_percent,
                   value.logo_margin, value.logo_opacity, value.video_mode,
                   value.video_duration)


def project_snapshot_to_tk(snapshot: VisualPreferenceSnapshot, variables: dict[str, Any]) -> None:
    """Project a snapshot into legacy Tk adapters in one direction only."""
    mapping = {
        "badge_var": snapshot.badge_name, "position_var": snapshot.position,
        "size_var": snapshot.size_percent, "margin_var": snapshot.margin,
        "opacity_var": snapshot.opacity, "logo_enabled_var": snapshot.logo_enabled,
        "logo_path_var": snapshot.logo_path, "logo_position_var": snapshot.logo_position,
        "logo_size_var": snapshot.logo_size_percent, "logo_margin_var": snapshot.logo_margin,
        "logo_opacity_var": snapshot.logo_opacity, "video_mode_var": snapshot.video_mode,
        "video_duration_var": snapshot.video_duration,
    }
    for name, value in mapping.items():
        variable = variables.get(name)
        if variable is not None and hasattr(variable, "set"):
            variable.set(value)
