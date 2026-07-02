"""Frozen event model for the organism architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class EventType(str, Enum):
    """Architecture-level event types for the frozen model."""

    BELIEF_UPDATED = "belief.updated"
    PLAN_PROPOSED = "plan.proposed"
    PLAN_ABANDONED = "plan.abandoned"
    PLAN_SELECTED = "plan.selected"
    APPROVAL_GRANTED = "approval.granted"
    ACTION_ATTEMPTED = "action.attempted"


@dataclass(slots=True, kw_only=True)
class Event:
    """Base event definition shared by the entire organism."""

    source_component: str
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    event_type: EventType = EventType.BELIEF_UPDATED
    event_version: int = 1


@dataclass(slots=True, kw_only=True)
class BeliefUpdatedEvent(Event):
    """Represents a belief-state update."""

    belief_id: str
    previous_confidence: float
    new_confidence: float
    provenance: str
    event_type: EventType = EventType.BELIEF_UPDATED


@dataclass(slots=True, kw_only=True)
class PlanProposedEvent(Event):
    """Represents a plan created during planning."""

    plan_id: str
    opportunity_id: str
    rationale: str
    event_type: EventType = EventType.PLAN_PROPOSED


@dataclass(slots=True, kw_only=True)
class PlanAbandonedEvent(Event):
    """Represents a plan that was discarded."""

    plan_id: str
    reason: str
    event_type: EventType = EventType.PLAN_ABANDONED


@dataclass(slots=True, kw_only=True)
class ExecutiveDecisionEvent(Event):
    """Represents an executive decision to commit to a plan."""

    decision_id: str
    plan_id: str
    rationale: str
    event_type: EventType = EventType.PLAN_SELECTED


@dataclass(slots=True, kw_only=True)
class ApprovalGrantedEvent(Event):
    """Represents a governor approval decision."""

    approval_id: str
    policy_id: str
    decision_id: str
    event_type: EventType = EventType.APPROVAL_GRANTED


@dataclass(slots=True, kw_only=True)
class ActionAttemptedEvent(Event):
    """Represents an execution attempt by the executor."""

    action_id: str
    tool_name: str
    attempt: int
    event_type: EventType = EventType.ACTION_ATTEMPTED


__all__ = [
    "Event",
    "EventType",
    "BeliefUpdatedEvent",
    "PlanProposedEvent",
    "PlanAbandonedEvent",
    "ExecutiveDecisionEvent",
    "ApprovalGrantedEvent",
    "ActionAttemptedEvent",
]
