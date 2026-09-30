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


class ShellController:
    """The sole writer for the outer destination during shell isolation."""

    def __init__(self) -> None:
        self.destination = DEFAULT_DESTINATION
        self.transitions: list[ShellTransition] = []

    def dispatch(self, event: str) -> ShellTransition:
        previous = self.destination
        if event == "reset":
            next_destination = DEFAULT_DESTINATION
        elif event in DESTINATIONS:
            next_destination = event
        else:
            raise ValueError(f"Unknown shell event: {event}")
        self.destination = next_destination
        transition = ShellTransition(previous, event, next_destination, placeholder_for(next_destination))
        self.transitions.append(transition)
        return transition


def placeholder_for(destination: str) -> str:
    if destination not in DESTINATIONS:
        raise ValueError(f"Unknown shell destination: {destination}")
    return f"{destination.upper()} TEST"
