"""Isolated outer navigation state for the 1.0.3 shell audit."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class ContentState(str, Enum):
    IMAGE = "image"; VIDEO = "video"; PDF = "pdf"; PPTX = "pptx"

class ContentEvent(str, Enum):
    SELECT_IMAGE = "image"; SELECT_VIDEO = "video"; SELECT_PDF = "pdf"; SELECT_PPTX = "pptx"

DESTINATIONS = tuple(state.value for state in ContentState)
DEFAULT_DESTINATION = ContentState.IMAGE.value

class ToolState(str, Enum):
    NONE = "none"; BADGES = "badges"; INSPECT = "inspect"

class ShellEvent(str, Enum):
    IMAGE = "image"; VIDEO = "video"; PDF = "pdf"; PPTX = "pptx"
    BADGES = "badges"; INSPECT = "inspect"; BACK = "back"; RESET = "reset"

class ShellAction(str, Enum):
    PRESERVE_SOURCE = "preserve_source"
    CLEAR_SOURCE = "clear_source"
    UNMOUNT_SOURCE = "unmount_source"
    MOUNT_DESTINATION = "mount_destination"
    PROJECT_DESTINATION = "project_destination"
    MOUNT_TOOL = "mount_tool"
    UNMOUNT_TOOL = "unmount_tool"
    CLEAR_TOOL = "clear_tool"
    CLEAR_ALL_WORKSPACES = "clear_all_workspaces"
    CLEAN_DESTINATION = "clean_destination"

@dataclass(frozen=True)
class ShellTransitionSpec:
    source_content: ContentState
    source_tool: ToolState
    event: ShellEvent
    requires_confirmation: bool
    actions: Tuple[ShellAction, ...]
    destination_content: ContentState
    destination_tool: ToolState
    preserve_source: bool
    decision: str | None = None

class ShellTransitionExecutor:
    """Single lifecycle executor for table-resolved shell plans."""
    def execute(self, spec: ShellTransitionSpec, runtime) -> tuple[str, ...]:
        executed = []; failure = None
        if hasattr(runtime, "begin_receipt"):
            runtime.begin_receipt(spec)
        try:
          for action in spec.actions:
            if action is ShellAction.PRESERVE_SOURCE:
                runtime.preserve_source(); executed.append(action.value)
            elif action is ShellAction.CLEAR_SOURCE:
                runtime.clear_source(spec.source_content.value); executed.append(action.value)
            elif action is ShellAction.CLEAR_ALL_WORKSPACES:
                runtime.clear_all_workspaces(); executed.append(action.value)
            elif action is ShellAction.CLEAN_DESTINATION:
                runtime.clean_destination(spec.destination_content.value); executed.append(action.value)
            elif action is ShellAction.UNMOUNT_SOURCE:
                runtime.unmount_source(spec.source_content.value); executed.append(action.value)
            elif action is ShellAction.MOUNT_DESTINATION:
                runtime.mount_destination(spec.destination_content.value); executed.append(action.value)
            elif action is ShellAction.PROJECT_DESTINATION:
                runtime.project_destination(spec.destination_content.value); executed.append(action.value)
            elif action is ShellAction.MOUNT_TOOL:
                runtime.mount_tool(spec.destination_tool.value); executed.append(action.value)
            elif action is ShellAction.UNMOUNT_TOOL:
                runtime.unmount_tool(); executed.append(action.value)
            elif action is ShellAction.CLEAR_TOOL:
                runtime.clear_tool(); executed.append(action.value)
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
        receipt = TransitionReceipt(
            spec.source_content.value, spec.event.value,
            spec.destination_content.value,
            spec.destination_content.value if not failure else spec.source_content.value,
            getattr(runtime, "resolved_workspace", spec.destination_content.value),
            tuple(a.value for a in spec.actions),
            "failure" if failure else "success",
            spec.source_tool.value, spec.requires_confirmation, spec.decision,
            tuple(a.value for a in spec.actions), tuple(executed), failure,
            executed[-1] if executed else None,
            getattr(runtime, "destination_lookup", "not_attempted"),
            getattr(runtime, "mount_result", "not_attempted"),
            getattr(runtime, "project_result", "not_attempted"),
            getattr(runtime, "tool_result", "not_attempted"),
            tuple(getattr(runtime, "cleared_workspaces", ())),
            tuple(getattr(runtime, "clear_failures", ())),
            spec.destination_tool.value if not failure else spec.source_tool.value,
        )
        runtime.record_receipt(receipt)
        if failure: raise RuntimeError(failure)
        return tuple(executed)

def shell_transition_spec(source: str, tool: str | None, event: str, active_work: bool = False, decision: str | None = None) -> ShellTransitionSpec:
    """Return the executable shell contract for one state/event/context."""
    src = ContentState(source); src_tool = ToolState(tool or "none"); ev = ShellEvent(event)
    if ev in {ShellEvent.BADGES, ShellEvent.INSPECT}:
        return ShellTransitionSpec(src, src_tool, ev, False, (ShellAction.PRESERVE_SOURCE, ShellAction.MOUNT_TOOL), src, ToolState(ev.value), True, decision)
    if ev is ShellEvent.BACK:
        return ShellTransitionSpec(src, src_tool, ev, False, (ShellAction.UNMOUNT_TOOL, ShellAction.CLEAR_TOOL, ShellAction.PROJECT_DESTINATION), src, ToolState.NONE, True, decision)
    if ev is ShellEvent.RESET:
        confirm = bool(active_work)
        if confirm and decision == "cancel":
            return ShellTransitionSpec(src, src_tool, ev, True, (ShellAction.PRESERVE_SOURCE,), src, src_tool, True, decision)
        actions = [ShellAction.CLEAR_ALL_WORKSPACES]
        if src_tool is not ToolState.NONE:
            actions.append(ShellAction.UNMOUNT_TOOL)
        actions.extend((ShellAction.CLEAR_TOOL, ShellAction.MOUNT_DESTINATION, ShellAction.PROJECT_DESTINATION))
        return ShellTransitionSpec(src, src_tool, ev, confirm, tuple(actions), ContentState.IMAGE, ToolState.NONE, False, decision)
    dest = ContentState(ev.value)
    if dest is src and src_tool is ToolState.NONE:
        return ShellTransitionSpec(src, src_tool, ev, False, (ShellAction.PRESERVE_SOURCE, ShellAction.PROJECT_DESTINATION), src, ToolState.NONE, True, decision)
    if active_work and decision == "cancel":
        return ShellTransitionSpec(src, src_tool, ev, True, (ShellAction.PRESERVE_SOURCE,), src, src_tool, True, decision)
    actions = ((ShellAction.CLEAR_SOURCE, ShellAction.UNMOUNT_SOURCE, ShellAction.CLEAN_DESTINATION, ShellAction.MOUNT_DESTINATION, ShellAction.PROJECT_DESTINATION)
               if active_work else
               (ShellAction.UNMOUNT_SOURCE, ShellAction.CLEAN_DESTINATION, ShellAction.MOUNT_DESTINATION, ShellAction.PROJECT_DESTINATION))
    return ShellTransitionSpec(src, src_tool, ev, active_work, actions, dest, ToolState.NONE, False, decision)

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
    source_tool: str = "none"; guard: bool = False; decision: str | None = None
    planned_actions: tuple[str, ...] = (); executed_actions: tuple[str, ...] = ()
    failure: str | None = None; last_successful_action: str | None = None
    destination_lookup: str = "not_attempted"; mount_result: str = "not_attempted"
    project_result: str = "not_attempted"; tool_result: str = "not_attempted"
    cleared_workspaces: tuple[str, ...] = ()
    clear_failures: tuple[str, ...] = ()
    final_tool: str = "none"


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

    def commit_content(self, destination: str) -> None:
        """Commit executor-owned content state without resolving a transition."""
        if destination not in DESTINATIONS:
            raise ValueError(f"Unknown shell destination: {destination}")
        self.active_content_type = destination
        self.active_tool = None

    def commit_tool(self, tool: str) -> None:
        """Commit executor-owned overlay state without a second FSM."""
        if tool not in {"badges", "inspect"}:
            raise ValueError(f"Unknown shell tool: {tool}")
        self.active_tool = tool

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
