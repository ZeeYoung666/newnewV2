"""Executor: translates approved plans into actions and dispatches them through tools.

Owns the tool registry and action log. The Executor executes only — it never
plans and never approves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import uuid4

from src.events import (
    ActionApprovedEvent,
    ActionAttemptedEvent,
    ActionFailedEvent,
    ActionSucceededEvent,
    ApprovalGrantedEvent,
    EventType,
)
from src.kernel import Kernel

Tool = Callable[["Action"], object]


@dataclass(slots=True, kw_only=True, frozen=True)
class Action:
    """A single unit of work translated from an approved plan step."""

    action_id: str
    plan_id: str
    action_type: str
    parameters: dict[str, str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class ActionRecord:
    """An immutable audit trail entry for a single execution attempt."""

    record_id: str
    action_id: str
    status: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result: Optional[str] = None
    error: Optional[str] = None


class ToolRegistry:
    """Maps action types to the tool callables that execute them."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, action_type: str, tool: Tool) -> None:
        self._tools[action_type] = tool

    def get_tool(self, action_type: str) -> Tool:
        return self._tools[action_type]

    def is_registered(self, action_type: str) -> bool:
        return action_type in self._tools


class ActionLog:
    """Append-only log of action records."""

    def __init__(self) -> None:
        self._records: list[ActionRecord] = []

    def append(self, record: ActionRecord) -> None:
        self._records.append(record)

    def read_all(self) -> list[ActionRecord]:
        return list(self._records)


def _parse_ordered_action(ordered_action: str) -> tuple[str, dict[str, str]]:
    action_type, _, target = ordered_action.partition(":")
    parameters = {"target": target} if target else {}
    return action_type, parameters


class Executor:
    """Dispatches approved plans as ordered actions through registered tools."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.tool_registry = ToolRegistry()
        self.action_log = ActionLog()
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, self._on_approval_granted)
        kernel.register_snapshot_source(
            "executor.actions", ActionRecord, self.action_log.read_all, self._restore_actions
        )

    def _restore_actions(self, records: list[ActionRecord]) -> None:
        for record in records:
            self.action_log.append(record)

    def _on_approval_granted(self, event: ApprovalGrantedEvent) -> None:
        for ordered_action in event.ordered_actions:
            self._execute_action(plan_id=event.plan_id, ordered_action=ordered_action)

    def _execute_action(self, *, plan_id: str, ordered_action: str) -> None:
        action_type, parameters = _parse_ordered_action(ordered_action)
        action = Action(
            action_id=str(uuid4()),
            plan_id=plan_id,
            action_type=action_type,
            parameters=parameters,
        )
        self._kernel.publish(
            ActionApprovedEvent(
                source_component="executor",
                action_id=action.action_id,
                plan_id=plan_id,
                action_type=action_type,
            )
        )
        self._kernel.publish(
            ActionAttemptedEvent(
                source_component="executor",
                action_id=action.action_id,
                tool_name=action_type,
                attempt=1,
            )
        )

        try:
            tool = self.tool_registry.get_tool(action_type)
        except KeyError:
            self._record_failure(action, f"no tool registered for action_type '{action_type}'")
            return

        try:
            result = tool(action)
        except Exception as exc:  # noqa: BLE001 - any tool failure is recorded, not propagated
            self._record_failure(action, str(exc))
            return

        self._record_success(action, result)

    def _record_success(self, action: Action, result: object) -> None:
        self.action_log.append(
            ActionRecord(record_id=str(uuid4()), action_id=action.action_id, status="succeeded", result=str(result))
        )
        self._kernel.publish(
            ActionSucceededEvent(
                source_component="executor", action_id=action.action_id, plan_id=action.plan_id, result=str(result)
            )
        )

    def _record_failure(self, action: Action, error: str) -> None:
        self.action_log.append(
            ActionRecord(record_id=str(uuid4()), action_id=action.action_id, status="failed", error=error)
        )
        self._kernel.publish(
            ActionFailedEvent(
                source_component="executor", action_id=action.action_id, plan_id=action.plan_id, error=error
            )
        )


__all__ = ["Action", "ActionRecord", "ToolRegistry", "ActionLog", "Executor"]
