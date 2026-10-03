"""Isolated outer navigation state for the 1.0.3 shell audit."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContentState(str, Enum):
    IMAGE = "image"; VIDEO = "video"; PDF = "pdf"; PPTX = "pptx"

class ContentEvent(str, Enum):
    SELECT_IMAGE = "image"; SELECT_VIDEO = "video"; SELECT_PDF = "pdf"; SELECT_PPTX = "pptx"

DESTINATIONS = tuple(state.value for state in ContentState)
DEFAULT_DESTINATION = ContentState.IMAGE.value

SHELL_TRANSITION_TABLE = {
    (source, event): destination
    for source in ContentState
    for event, destination in zip(ContentEvent, ContentState)
}


@dataclass(frozen=True)
class ShellTransition:
    previous: str
    event: str
    next: str
    mounted_view: str
    active_content_type: str = DEFAULT_DESTINATION
    active_tool: str | None = None

@dataclass(frozen=True)
class TransitionReceipt:
    source: str; event: str; expected_destination: str; final_state: str
    workspace: str; stages: tuple[str, ...]; outcome: str = "success"


class ShellController:
    """The sole writer for the outer destination during shell isolation."""

    def __init__(self) -> None:
        self.active_content_type = DEFAULT_DESTINATION
        self.active_tool: str | None = None
        self.transitions: list[ShellTransition] = []
        self.receipts: list[TransitionReceipt] = []

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
        elif event in DESTINATIONS:
            typed_event = ContentEvent(event)
            destination = SHELL_TRANSITION_TABLE[(ContentState(self.active_content_type), typed_event)]
            self.active_content_type = event
            self.active_tool = None
            next_destination = event
        else:
            raise ValueError(f"Unknown shell event: {event}")
        transition = ShellTransition(previous, event, next_destination, placeholder_for(next_destination), self.active_content_type, self.active_tool)
        self.transitions.append(transition)
        self.receipts.append(TransitionReceipt(previous, event, next_destination, self.active_content_type, next_destination, ("event accepted", "transition table entry resolved", "destination state committed")))
        return transition


def placeholder_for(destination: str) -> str:
    if destination not in DESTINATIONS and destination not in {"badges", "inspect"}:
        raise ValueError(f"Unknown shell destination: {destination}")
    return f"{destination.upper()} TEST"
