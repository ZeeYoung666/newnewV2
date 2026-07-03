"""Executive: generates opportunities, scores them, and proposes plans.

Owns the goal tree, opportunity store, plan store, and decision records.
The Executive proposes only — it does not approve and does not execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.events import (
    BeliefCreatedEvent,
    BeliefUpdatedEvent,
    EventType,
    OpportunityIdentifiedEvent,
    OpportunityScoredEvent,
    PlanProposedEvent,
)
from src.kernel import Kernel

EXPECTED_VALUE_PER_CONFIDENCE = 100.0
ATTENTION_COST_BASELINE = 1.0
CAPITAL_COST_FRACTION = 0.1


@dataclass(slots=True, kw_only=True, frozen=True)
class Goal:
    """A durable objective the Executive plans against."""

    goal_id: str
    description: str
    priority: int
    parent_goal_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class Opportunity:
    """A candidate course of action derived from one or more beliefs."""

    opportunity_id: str
    belief_ids: tuple[str, ...]
    expected_value: float
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class Plan:
    """An ordered sequence of proposed actions pursuing an opportunity."""

    plan_id: str
    opportunity_id: str
    ordered_actions: tuple[str, ...]
    expected_value: float
    attention_cost: float
    capital_cost: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class DecisionRecord:
    """An immutable audit trail entry for a single Executive decision."""

    decision_id: str
    decision_type: str
    subject_id: str
    rationale: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class GoalStore:
    """Append-only store of goals, keyed by goal_id."""

    def __init__(self) -> None:
        self._goals: list[Goal] = []
        self._by_id: dict[str, Goal] = {}

    def append(self, goal: Goal) -> None:
        self._goals.append(goal)
        self._by_id[goal.goal_id] = goal

    def get(self, goal_id: str) -> Goal:
        return self._by_id[goal_id]

    def read_all(self) -> list[Goal]:
        return list(self._goals)


class OpportunityStore:
    """Append-only store of opportunities, keyed by opportunity_id."""

    def __init__(self) -> None:
        self._opportunities: list[Opportunity] = []
        self._by_id: dict[str, Opportunity] = {}

    def append(self, opportunity: Opportunity) -> None:
        self._opportunities.append(opportunity)
        self._by_id[opportunity.opportunity_id] = opportunity

    def get(self, opportunity_id: str) -> Opportunity:
        return self._by_id[opportunity_id]

    def read_all(self) -> list[Opportunity]:
        return list(self._opportunities)


class PlanStore:
    """Append-only store of plans, keyed by plan_id."""

    def __init__(self) -> None:
        self._plans: list[Plan] = []
        self._by_id: dict[str, Plan] = {}

    def append(self, plan: Plan) -> None:
        self._plans.append(plan)
        self._by_id[plan.plan_id] = plan

    def get(self, plan_id: str) -> Plan:
        return self._by_id[plan_id]

    def read_all(self) -> list[Plan]:
        return list(self._plans)


class DecisionRecordStore:
    """Append-only store of decision records, keyed by decision_id."""

    def __init__(self) -> None:
        self._records: list[DecisionRecord] = []
        self._by_id: dict[str, DecisionRecord] = {}

    def append(self, record: DecisionRecord) -> None:
        self._records.append(record)
        self._by_id[record.decision_id] = record

    def get(self, decision_id: str) -> DecisionRecord:
        return self._by_id[decision_id]

    def read_all(self) -> list[DecisionRecord]:
        return list(self._records)


class Executive:
    """Reacts to belief events by proposing opportunities and plans. Proposes only."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.goal_store = GoalStore()
        self.opportunity_store = OpportunityStore()
        self.plan_store = PlanStore()
        self.decision_record_store = DecisionRecordStore()
        kernel.register_subscriber(EventType.BELIEF_CREATED, self._on_belief_created)
        kernel.register_subscriber(EventType.BELIEF_UPDATED, self._on_belief_updated)
        kernel.register_snapshot_source(
            "executive.opportunities", Opportunity, self.opportunity_store.read_all, self._restore_opportunities
        )
        kernel.register_snapshot_source("executive.plans", Plan, self.plan_store.read_all, self._restore_plans)
        kernel.register_snapshot_source(
            "executive.decision_records",
            DecisionRecord,
            self.decision_record_store.read_all,
            self._restore_decision_records,
        )

    def _restore_opportunities(self, opportunities: list[Opportunity]) -> None:
        for opportunity in opportunities:
            self.opportunity_store.append(opportunity)

    def _restore_plans(self, plans: list[Plan]) -> None:
        for plan in plans:
            self.plan_store.append(plan)

    def _restore_decision_records(self, records: list[DecisionRecord]) -> None:
        for record in records:
            self.decision_record_store.append(record)

    def _on_belief_created(self, event: BeliefCreatedEvent) -> None:
        self._process_belief(belief_id=event.belief_id, confidence=event.confidence)

    def _on_belief_updated(self, event: BeliefUpdatedEvent) -> None:
        self._process_belief(belief_id=event.belief_id, confidence=event.new_confidence)

    def _process_belief(self, *, belief_id: str, confidence: float) -> None:
        opportunity = self._identify_opportunity(belief_id=belief_id, confidence=confidence)
        self._score_opportunity(opportunity)
        self._propose_plan(opportunity)

    def _identify_opportunity(self, *, belief_id: str, confidence: float) -> Opportunity:
        opportunity = Opportunity(
            opportunity_id=str(uuid4()),
            belief_ids=(belief_id,),
            expected_value=round(confidence * EXPECTED_VALUE_PER_CONFIDENCE, 4),
            confidence=confidence,
        )
        self.opportunity_store.append(opportunity)
        self._kernel.publish(
            OpportunityIdentifiedEvent(
                source_component="executive",
                opportunity_id=opportunity.opportunity_id,
                belief_ids=opportunity.belief_ids,
                confidence=opportunity.confidence,
            )
        )
        self.decision_record_store.append(
            DecisionRecord(
                decision_id=str(uuid4()),
                decision_type="opportunity_identified",
                subject_id=opportunity.opportunity_id,
                rationale=f"belief {belief_id} observed with confidence {confidence}",
            )
        )
        return opportunity

    def _score_opportunity(self, opportunity: Opportunity) -> None:
        self._kernel.publish(
            OpportunityScoredEvent(
                source_component="executive",
                opportunity_id=opportunity.opportunity_id,
                expected_value=opportunity.expected_value,
                confidence=opportunity.confidence,
            )
        )
        self.decision_record_store.append(
            DecisionRecord(
                decision_id=str(uuid4()),
                decision_type="opportunity_scored",
                subject_id=opportunity.opportunity_id,
                rationale=f"expected_value={opportunity.expected_value} confidence={opportunity.confidence}",
            )
        )

    def _propose_plan(self, opportunity: Opportunity) -> None:
        plan = Plan(
            plan_id=str(uuid4()),
            opportunity_id=opportunity.opportunity_id,
            ordered_actions=(
                f"investigate:{opportunity.opportunity_id}",
                f"act_on:{opportunity.opportunity_id}",
            ),
            expected_value=opportunity.expected_value,
            attention_cost=ATTENTION_COST_BASELINE,
            capital_cost=round(opportunity.expected_value * CAPITAL_COST_FRACTION, 4),
        )
        self.plan_store.append(plan)
        self._kernel.publish(
            PlanProposedEvent(
                source_component="executive",
                plan_id=plan.plan_id,
                opportunity_id=opportunity.opportunity_id,
                rationale=(
                    f"expected_value={plan.expected_value} "
                    f"attention_cost={plan.attention_cost} "
                    f"capital_cost={plan.capital_cost}"
                ),
                expected_value=plan.expected_value,
                attention_cost=plan.attention_cost,
                capital_cost=plan.capital_cost,
                ordered_actions=plan.ordered_actions,
            )
        )
        self.decision_record_store.append(
            DecisionRecord(
                decision_id=str(uuid4()),
                decision_type="plan_proposed",
                subject_id=plan.plan_id,
                rationale=f"plan for opportunity {opportunity.opportunity_id}",
            )
        )


__all__ = [
    "Goal",
    "GoalStore",
    "Opportunity",
    "OpportunityStore",
    "Plan",
    "PlanStore",
    "DecisionRecord",
    "DecisionRecordStore",
    "Executive",
]
