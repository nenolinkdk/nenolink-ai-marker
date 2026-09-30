"""Isolated outer navigation state for the 1.0.3 shell audit."""

from __future__ import annotations

from dataclasses import dataclass


DESTINATIONS = ("image", "video", "pdf", "pptx", "badges", "inspect")
DEFAULT_DESTINATION = "image"


@dataclass(frozen=True)
class ShellTransition:
    previous: str
    event: str
    next: str
    mounted_view: str
    active_content_type: str = DEFAULT_DESTINATION
    active_tool: str | None = None


class ShellController:
    """The sole writer for the outer destination during shell isolation."""

    def __init__(self) -> None:
        self.active_content_type = DEFAULT_DESTINATION
        self.active_tool: str | None = None
        self.transitions: list[ShellTransition] = []

    @property
    def destination(self) -> str:
        """Compatibility view name; content state remains authoritative."""
        return self.active_content_type

    def dispatch(self, event: str) -> ShellTransition:
        previous = self.active_tool or self.active_content_type
        if event == "reset":
            self.active_content_type = DEFAULT_DESTINATION
            self.active_tool = None
            next_destination = DEFAULT_DESTINATION
        elif event in {"badges", "inspect"}:
            self.active_tool = event
            next_destination = event
        elif event == "back":
            self.active_tool = None
            next_destination = self.active_content_type
        elif event in {"image", "video", "pdf", "pptx"}:
            self.active_content_type = event
            self.active_tool = None
            next_destination = event
        else:
            raise ValueError(f"Unknown shell event: {event}")
        transition = ShellTransition(previous, event, next_destination, placeholder_for(next_destination), self.active_content_type, self.active_tool)
        self.transitions.append(transition)
        return transition


def placeholder_for(destination: str) -> str:
    if destination not in DESTINATIONS:
        raise ValueError(f"Unknown shell destination: {destination}")
    return f"{destination.upper()} TEST"
