"""Governor: enforces invariants, approval policy, budgets, and owner escalation.

Owns the constitution, budget state, and approval log. The Governor approves
or rejects plans proposed by the Executive. It never creates or executes plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.events import (
    ApprovalDeniedEvent,
    ApprovalGrantedEvent,
    ApprovalRequiredEvent,
    BudgetCheckedEvent,
    EventType,
    PlanProposedEvent,
    PolicyEvaluatedEvent,
)
from src.kernel import Kernel

# The only constitutional rule this foundation knows how to enforce: a plan's
# costs must not be negative. Unrecognized rule names are ignored.
KNOWN_RULES = {"non_negative_costs"}


@dataclass(slots=True, kw_only=True, frozen=True)
class Constitution:
    """The set of rules the Governor evaluates plans against."""

    constitution_id: str
    version: int
    rules: tuple[str, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class BudgetState:
    """The attention and capital currently available to spend."""

    budget_id: str
    available_attention: float
    available_capital: float
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class ApprovalRecord:
    """An immutable audit trail entry for a single Governor decision."""

    approval_id: str
    plan_id: str
    decision: str
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConstitutionStore:
    """Append-only store of constitutions, keyed by constitution_id."""

    def __init__(self) -> None:
        self._constitutions: list[Constitution] = []
        self._by_id: dict[str, Constitution] = {}

    def append(self, constitution: Constitution) -> None:
        self._constitutions.append(constitution)
        self._by_id[constitution.constitution_id] = constitution

    def get(self, constitution_id: str) -> Constitution:
        return self._by_id[constitution_id]

    def current(self) -> Constitution:
        """Return the most recently adopted constitution. Raises LookupError if none exists."""
        if not self._constitutions:
            raise LookupError("no constitution has been adopted")
        return self._constitutions[-1]

    def read_all(self) -> list[Constitution]:
        return list(self._constitutions)


class BudgetStore:
    """Current-state store of budgets, keyed by budget_id."""

    def __init__(self) -> None:
        self._budgets: dict[str, BudgetState] = {}

    def put(self, budget: BudgetState) -> None:
        self._budgets[budget.budget_id] = budget

    def get(self, budget_id: str) -> BudgetState:
        return self._budgets[budget_id]

    def exists(self, budget_id: str) -> bool:
        return budget_id in self._budgets

    def read_all(self) -> list[BudgetState]:
        return list(self._budgets.values())


class ApprovalLog:
    """Append-only log of approval decisions, keyed by approval_id."""

    def __init__(self) -> None:
        self._records: list[ApprovalRecord] = []
        self._by_id: dict[str, ApprovalRecord] = {}

    def append(self, record: ApprovalRecord) -> None:
        self._records.append(record)
        self._by_id[record.approval_id] = record

    def get(self, approval_id: str) -> ApprovalRecord:
        return self._by_id[approval_id]

    def read_all(self) -> list[ApprovalRecord]:
        return list(self._records)


class Governor:
    """Evaluates proposed plans against the constitution and budget, and authorizes or rejects them."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.constitution_store = ConstitutionStore()
        self.budget_store = BudgetStore()
        self.approval_log = ApprovalLog()
        self._active_constitution_id: Optional[str] = None
        self._active_budget_id: Optional[str] = None
        kernel.register_subscriber(EventType.PLAN_PROPOSED, self._on_plan_proposed)

    def adopt_constitution(self, constitution: Constitution) -> None:
        """Adopt a constitution as the currently active one."""
        self.constitution_store.append(constitution)
        self._active_constitution_id = constitution.constitution_id

    def fund_budget(self, budget: BudgetState) -> None:
        """Fund (or refund) the currently active budget."""
        self.budget_store.put(budget)
        self._active_budget_id = budget.budget_id

    def _on_plan_proposed(self, event: PlanProposedEvent) -> None:
        if self._active_constitution_id is None:
            self._require_approval(event.plan_id, "no constitution configured")
            return
        if self._active_budget_id is None:
            self._require_approval(event.plan_id, "no budget configured")
            return

        constitution = self.constitution_store.get(self._active_constitution_id)
        policy_passed, policy_reason = self._evaluate_policy(constitution, event)
        self._kernel.publish(
            PolicyEvaluatedEvent(
                source_component="governor",
                plan_id=event.plan_id,
                constitution_id=constitution.constitution_id,
                passed=policy_passed,
                reason=policy_reason,
            )
        )
        if not policy_passed:
            self._deny(event.plan_id, policy_reason)
            return

        budget = self.budget_store.get(self._active_budget_id)
        attention_sufficient = event.attention_cost <= budget.available_attention
        capital_sufficient = event.capital_cost <= budget.available_capital
        sufficient = attention_sufficient and capital_sufficient
        self._kernel.publish(
            BudgetCheckedEvent(
                source_component="governor",
                plan_id=event.plan_id,
                budget_id=budget.budget_id,
                attention_required=event.attention_cost,
                attention_available=budget.available_attention,
                capital_required=event.capital_cost,
                capital_available=budget.available_capital,
                sufficient=sufficient,
            )
        )
        if not sufficient:
            self._deny(
                event.plan_id,
                f"insufficient budget: attention_ok={attention_sufficient} capital_ok={capital_sufficient}",
            )
            return

        self._grant(event.plan_id, budget, event)

    def _evaluate_policy(self, constitution: Constitution, event: PlanProposedEvent) -> tuple[bool, str]:
        if "non_negative_costs" in constitution.rules:
            if event.attention_cost < 0 or event.capital_cost < 0:
                return False, (
                    f"rule 'non_negative_costs' violated: attention_cost={event.attention_cost} "
                    f"capital_cost={event.capital_cost}"
                )
        return True, "all rules satisfied"

    def _grant(self, plan_id: str, budget: BudgetState, event: PlanProposedEvent) -> None:
        approval_id = str(uuid4())
        reason = "within policy and budget"
        self.budget_store.put(
            BudgetState(
                budget_id=budget.budget_id,
                available_attention=budget.available_attention - event.attention_cost,
                available_capital=budget.available_capital - event.capital_cost,
            )
        )
        self.approval_log.append(
            ApprovalRecord(approval_id=approval_id, plan_id=plan_id, decision="approved", reason=reason)
        )
        self._kernel.publish(
            ApprovalGrantedEvent(
                source_component="governor",
                approval_id=approval_id,
                plan_id=plan_id,
                reason=reason,
                ordered_actions=event.ordered_actions,
            )
        )

    def _deny(self, plan_id: str, reason: str) -> None:
        approval_id = str(uuid4())
        self.approval_log.append(
            ApprovalRecord(approval_id=approval_id, plan_id=plan_id, decision="rejected", reason=reason)
        )
        self._kernel.publish(
            ApprovalDeniedEvent(source_component="governor", approval_id=approval_id, plan_id=plan_id, reason=reason)
        )

    def _require_approval(self, plan_id: str, reason: str) -> None:
        self._kernel.publish(ApprovalRequiredEvent(source_component="governor", plan_id=plan_id, reason=reason))


__all__ = [
    "Constitution",
    "BudgetState",
    "ApprovalRecord",
    "ConstitutionStore",
    "BudgetStore",
    "ApprovalLog",
    "Governor",
]
