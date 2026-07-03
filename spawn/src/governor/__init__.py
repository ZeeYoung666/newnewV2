"""Governor: enforces invariants, approval policy, budgets, and owner escalation.

Owns the constitution, budget state, and approval log. The Governor approves
or rejects plans proposed by the Executive. It never creates or executes plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import uuid4

from src.events import (
    ApprovalDeniedEvent,
    ApprovalGrantedEvent,
    ApprovalRequiredEvent,
    BudgetCheckedEvent,
    ConstitutionAmendedEvent,
    ConstitutionAmendmentProposedEvent,
    ConstitutionAmendmentRejectedEvent,
    EscalationCreatedEvent,
    EscalationResolvedEvent,
    EventType,
    PlanProposedEvent,
    PolicyEvaluatedEvent,
)
from src.kernel import Kernel

RuleEvaluator = Callable[[PlanProposedEvent, tuple[str, ...]], Optional[str]]


def _parse_rule(rule: str) -> tuple[str, tuple[str, ...]]:
    """Split a rule string into its name and comma-separated argument list.

    "non_negative_costs" -> ("non_negative_costs", ())
    "max_capital_cost:500" -> ("max_capital_cost", ("500",))
    """
    name, _, raw_args = rule.partition(":")
    args = tuple(arg for arg in raw_args.split(",") if arg) if raw_args else ()
    return name, args


def _rule_non_negative_costs(event: PlanProposedEvent, args: tuple[str, ...]) -> Optional[str]:
    if event.attention_cost < 0 or event.capital_cost < 0:
        return f"attention_cost={event.attention_cost} capital_cost={event.capital_cost} must be >= 0"
    return None


def _rule_max_capital_cost(event: PlanProposedEvent, args: tuple[str, ...]) -> Optional[str]:
    limit = float(args[0])
    if event.capital_cost > limit:
        return f"capital_cost={event.capital_cost} exceeds limit={limit}"
    return None


def _rule_max_attention_cost(event: PlanProposedEvent, args: tuple[str, ...]) -> Optional[str]:
    limit = float(args[0])
    if event.attention_cost > limit:
        return f"attention_cost={event.attention_cost} exceeds limit={limit}"
    return None


DEFAULT_RULES: dict[str, RuleEvaluator] = {
    "non_negative_costs": _rule_non_negative_costs,
    "max_capital_cost": _rule_max_capital_cost,
    "max_attention_cost": _rule_max_attention_cost,
}


class RuleRegistry:
    """Deterministic, order-independent rule evaluator.

    Every rule in a constitution is evaluated independently against the
    proposed plan; violations are collected (not short-circuited on the
    first match) and sorted before being joined into the final reason
    string, so declaration order in `Constitution.rules` never affects the
    pass/fail verdict or the reported violations. Unknown rule names are
    silently ignored, matching the foundation's prior behavior.
    """

    def __init__(self, rules: Optional[dict[str, RuleEvaluator]] = None) -> None:
        self._rules: dict[str, RuleEvaluator] = dict(rules if rules is not None else DEFAULT_RULES)

    def register(self, name: str, evaluator: RuleEvaluator) -> None:
        """Register (or replace) a rule evaluator under the given name."""
        self._rules[name] = evaluator

    def evaluate(self, constitution: "Constitution", event: PlanProposedEvent) -> tuple[bool, str]:
        violations: list[str] = []
        for rule in constitution.rules:
            name, args = _parse_rule(rule)
            evaluator = self._rules.get(name)
            if evaluator is None:
                continue
            violation = evaluator(event, args)
            if violation is not None:
                violations.append(f"{name}: {violation}")
        if violations:
            return False, "; ".join(sorted(violations))
        return True, "all rules satisfied"


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


@dataclass(slots=True, kw_only=True, frozen=True)
class Amendment:
    """An immutable audit trail entry for one constitutional amendment lifecycle transition.

    One record is appended per transition (proposed, then approved or
    rejected) — never mutated — so the full amendment history survives in
    `AmendmentLog` even though `status` only ever describes that single
    transition.
    """

    amendment_id: str
    constitution_id: str
    previous_constitution_id: Optional[str]
    version: int
    proposed_rules: tuple[str, ...]
    justification: str
    status: str
    proposed_at: datetime
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    reason: Optional[str] = None


@dataclass(slots=True, kw_only=True, frozen=True)
class EscalationRecord:
    """An immutable audit trail entry for one escalation lifecycle transition.

    One record is appended per transition (pending, then resolved) — never
    mutated — mirroring AmendmentLog's shape, so the full history survives
    in EscalationStore even though `status` only ever describes that single
    transition.
    """

    escalation_id: str
    plan_id: str
    reason: str
    ordered_actions: tuple[str, ...]
    status: str
    created_at: datetime
    decision: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None


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


class AmendmentLog:
    """Append-only log of amendment lifecycle transitions.

    Unlike ApprovalLog, an amendment_id can appear more than once (proposed,
    then approved or rejected) — read_all() returns every transition ever
    recorded, in order, so the full audit trail is always available.
    """

    def __init__(self) -> None:
        self._records: list[Amendment] = []

    def append(self, record: Amendment) -> None:
        self._records.append(record)

    def read_all(self) -> list[Amendment]:
        return list(self._records)

    def history_for(self, amendment_id: str) -> list[Amendment]:
        """All transitions recorded for a single amendment, in order."""
        return [record for record in self._records if record.amendment_id == amendment_id]


class EscalationStore:
    """Append-only log of escalation lifecycle transitions.

    Like AmendmentLog, an escalation_id can appear more than once (pending,
    then resolved) — read_all() returns every transition ever recorded, in
    order, so the full audit trail is always available.
    """

    def __init__(self) -> None:
        self._records: list[EscalationRecord] = []

    def append(self, record: EscalationRecord) -> None:
        self._records.append(record)

    def read_all(self) -> list[EscalationRecord]:
        return list(self._records)

    def history_for(self, escalation_id: str) -> list[EscalationRecord]:
        """All transitions recorded for a single escalation, in order."""
        return [record for record in self._records if record.escalation_id == escalation_id]


class Governor:
    """Evaluates proposed plans against the constitution and budget, and authorizes or rejects them."""

    def __init__(self, kernel: Kernel, rule_registry: Optional[RuleRegistry] = None) -> None:
        self._kernel = kernel
        self._rule_registry = rule_registry if rule_registry is not None else RuleRegistry()
        self.constitution_store = ConstitutionStore()
        self.budget_store = BudgetStore()
        self.approval_log = ApprovalLog()
        self.amendment_log = AmendmentLog()
        self.escalation_store = EscalationStore()
        self._active_budget_id: Optional[str] = None
        self._pending_amendments: dict[str, Constitution] = {}
        self._pending_escalations: dict[str, EscalationRecord] = {}
        kernel.register_subscriber(EventType.PLAN_PROPOSED, self._on_plan_proposed)
        kernel.register_subscriber(EventType.CONSTITUTION_AMENDMENT_PROPOSED, self._on_amendment_proposed)
        kernel.register_subscriber(EventType.CONSTITUTION_AMENDED, self._on_amendment_approved)
        kernel.register_subscriber(EventType.CONSTITUTION_AMENDMENT_REJECTED, self._on_amendment_rejected)
        kernel.register_subscriber(EventType.ESCALATION_CREATED, self._on_escalation_created)
        kernel.register_subscriber(EventType.ESCALATION_RESOLVED, self._on_escalation_resolved)
        kernel.register_snapshot_source(
            "governor.budgets", BudgetState, self.budget_store.read_all, self._restore_budgets
        )
        kernel.register_snapshot_source(
            "governor.approvals", ApprovalRecord, self.approval_log.read_all, self._restore_approvals
        )
        kernel.register_snapshot_source(
            "governor.constitutions", Constitution, self.constitution_store.read_all, self._restore_constitutions
        )
        kernel.register_snapshot_source(
            "governor.amendments", Amendment, self.amendment_log.read_all, self._restore_amendments
        )
        kernel.register_snapshot_source(
            "governor.escalations", EscalationRecord, self.escalation_store.read_all, self._restore_escalations
        )

    def _restore_budgets(self, budgets: list[BudgetState]) -> None:
        for budget in budgets:
            self.budget_store.put(budget)

    def _restore_approvals(self, records: list[ApprovalRecord]) -> None:
        for record in records:
            self.approval_log.append(record)

    def _restore_constitutions(self, constitutions: list[Constitution]) -> None:
        for constitution in constitutions:
            self.constitution_store.append(constitution)

    def _restore_amendments(self, records: list[Amendment]) -> None:
        for record in records:
            self.amendment_log.append(record)
        latest_by_id: dict[str, Amendment] = {}
        for record in records:
            latest_by_id[record.amendment_id] = record
        self._pending_amendments = {
            amendment_id: Constitution(
                constitution_id=record.constitution_id,
                version=record.version,
                rules=record.proposed_rules,
                created_at=record.proposed_at,
            )
            for amendment_id, record in latest_by_id.items()
            if record.status == "proposed"
        }

    def _restore_escalations(self, records: list[EscalationRecord]) -> None:
        for record in records:
            self.escalation_store.append(record)
        latest_by_id: dict[str, EscalationRecord] = {}
        for record in records:
            latest_by_id[record.escalation_id] = record
        self._pending_escalations = {
            escalation_id: record
            for escalation_id, record in latest_by_id.items()
            if record.status == "pending"
        }

    def adopt_constitution(self, constitution: Constitution) -> None:
        """Adopt a constitution as the currently active one.

        Bootstrap-only: the same kind of direct configuration call as
        `fund_budget`. Changing an already-adopted constitution goes through
        `propose_amendment` / `approve_amendment` instead.
        """
        self.constitution_store.append(constitution)

    def fund_budget(self, budget: BudgetState) -> None:
        """Fund (or refund) the currently active budget."""
        self.budget_store.put(budget)
        self._active_budget_id = budget.budget_id

    def propose_amendment(self, *, rules: tuple[str, ...], justification: str) -> str:
        """Propose a new constitution version for owner approval.

        Does not activate anything by itself — publishes
        ConstitutionAmendmentProposedEvent, which is what actually records
        the candidate (via this Governor's own subscriber), so the proposal
        is replay-correct.
        """
        amendment_id = str(uuid4())
        existing = self.constitution_store.read_all()
        previous_constitution_id = existing[-1].constitution_id if existing else None
        next_version = existing[-1].version + 1 if existing else 1
        constitution_id = str(uuid4())
        self._kernel.publish(
            ConstitutionAmendmentProposedEvent(
                source_component="governor",
                amendment_id=amendment_id,
                constitution_id=constitution_id,
                previous_constitution_id=previous_constitution_id,
                version=next_version,
                rules=rules,
                justification=justification,
            )
        )
        return amendment_id

    def approve_amendment(self, amendment_id: str, *, approved_by: str = "owner") -> None:
        """Approve a pending amendment, making it the active constitution.

        Raises KeyError if the amendment is unknown or already decided.
        """
        candidate = self._pending_amendments[amendment_id]
        self._kernel.publish(
            ConstitutionAmendedEvent(
                source_component="governor",
                amendment_id=amendment_id,
                constitution_id=candidate.constitution_id,
                version=candidate.version,
                approved_by=approved_by,
            )
        )

    def reject_amendment(self, amendment_id: str, *, reason: str) -> None:
        """Reject a pending amendment; it never becomes active.

        Raises KeyError if the amendment is unknown or already decided.
        """
        candidate = self._pending_amendments[amendment_id]
        self._kernel.publish(
            ConstitutionAmendmentRejectedEvent(
                source_component="governor",
                amendment_id=amendment_id,
                constitution_id=candidate.constitution_id,
                reason=reason,
            )
        )

    def approve_escalation(self, escalation_id: str, *, approved_by: str = "owner") -> None:
        """Approve a pending escalation, resuming the normal approval pipeline for its plan.

        Raises KeyError if the escalation is unknown or already resolved.
        """
        pending = self._pending_escalations[escalation_id]
        self._kernel.publish(
            EscalationResolvedEvent(
                source_component="governor",
                escalation_id=escalation_id,
                plan_id=pending.plan_id,
                decision="approved",
                resolved_by=approved_by,
                reason="owner approved escalation",
            )
        )

    def deny_escalation(self, escalation_id: str, *, reason: str, denied_by: str = "owner") -> None:
        """Deny a pending escalation, permanently rejecting its plan.

        Raises KeyError if the escalation is unknown or already resolved.
        """
        pending = self._pending_escalations[escalation_id]
        self._kernel.publish(
            EscalationResolvedEvent(
                source_component="governor",
                escalation_id=escalation_id,
                plan_id=pending.plan_id,
                decision="denied",
                resolved_by=denied_by,
                reason=reason,
            )
        )

    def _on_amendment_proposed(self, event: ConstitutionAmendmentProposedEvent) -> None:
        constitution = Constitution(
            constitution_id=event.constitution_id,
            version=event.version,
            rules=event.rules,
            created_at=event.timestamp,
        )
        self._pending_amendments[event.amendment_id] = constitution
        self.amendment_log.append(
            Amendment(
                amendment_id=event.amendment_id,
                constitution_id=event.constitution_id,
                previous_constitution_id=event.previous_constitution_id,
                version=event.version,
                proposed_rules=event.rules,
                justification=event.justification,
                status="proposed",
                proposed_at=event.timestamp,
            )
        )

    def _on_amendment_approved(self, event: ConstitutionAmendedEvent) -> None:
        constitution = self._pending_amendments.pop(event.amendment_id)
        self.constitution_store.append(constitution)
        proposed = self.amendment_log.history_for(event.amendment_id)[0]
        self.amendment_log.append(
            Amendment(
                amendment_id=event.amendment_id,
                constitution_id=event.constitution_id,
                previous_constitution_id=proposed.previous_constitution_id,
                version=event.version,
                proposed_rules=proposed.proposed_rules,
                justification=proposed.justification,
                status="approved",
                proposed_at=proposed.proposed_at,
                decided_at=event.timestamp,
                decided_by=event.approved_by,
            )
        )

    def _on_amendment_rejected(self, event: ConstitutionAmendmentRejectedEvent) -> None:
        self._pending_amendments.pop(event.amendment_id)
        proposed = self.amendment_log.history_for(event.amendment_id)[0]
        self.amendment_log.append(
            Amendment(
                amendment_id=event.amendment_id,
                constitution_id=event.constitution_id,
                previous_constitution_id=proposed.previous_constitution_id,
                version=proposed.version,
                proposed_rules=proposed.proposed_rules,
                justification=proposed.justification,
                status="rejected",
                proposed_at=proposed.proposed_at,
                decided_at=event.timestamp,
                reason=event.reason,
            )
        )

    def _on_plan_proposed(self, event: PlanProposedEvent) -> None:
        try:
            constitution = self.constitution_store.current()
        except LookupError:
            self._require_approval(event, "no constitution configured")
            return
        if self._active_budget_id is None:
            self._require_approval(event, "no budget configured")
            return

        policy_passed, policy_reason = self._rule_registry.evaluate(constitution, event)
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

    def _require_approval(self, event: PlanProposedEvent, reason: str) -> None:
        """Escalate a plan the Governor cannot decide on automatically.

        Publishes the pre-existing dead-end signal (ApprovalRequiredEvent,
        unchanged for backward compatibility) alongside EscalationCreatedEvent,
        which is what this Governor's own subscriber actually turns into a
        durable, resumable escalation.
        """
        self._kernel.publish(
            ApprovalRequiredEvent(source_component="governor", plan_id=event.plan_id, reason=reason)
        )
        self._kernel.publish(
            EscalationCreatedEvent(
                source_component="governor",
                escalation_id=str(uuid4()),
                plan_id=event.plan_id,
                reason=reason,
                ordered_actions=event.ordered_actions,
            )
        )

    def _on_escalation_created(self, event: EscalationCreatedEvent) -> None:
        record = EscalationRecord(
            escalation_id=event.escalation_id,
            plan_id=event.plan_id,
            reason=event.reason,
            ordered_actions=event.ordered_actions,
            status="pending",
            created_at=event.timestamp,
        )
        self.escalation_store.append(record)
        self._pending_escalations[event.escalation_id] = record

    def _on_escalation_resolved(self, event: EscalationResolvedEvent) -> None:
        pending = self._pending_escalations.pop(event.escalation_id)
        self.escalation_store.append(
            EscalationRecord(
                escalation_id=event.escalation_id,
                plan_id=pending.plan_id,
                reason=pending.reason,
                ordered_actions=pending.ordered_actions,
                status="resolved",
                created_at=pending.created_at,
                decision=event.decision,
                resolved_at=event.timestamp,
                resolved_by=event.resolved_by,
            )
        )
        if event.decision == "approved":
            self._grant_via_escalation(pending.plan_id, pending.ordered_actions)
        else:
            self._deny(pending.plan_id, event.reason)

    def _grant_via_escalation(self, plan_id: str, ordered_actions: tuple[str, ...]) -> None:
        approval_id = str(uuid4())
        reason = "owner-approved escalation"
        self.approval_log.append(
            ApprovalRecord(approval_id=approval_id, plan_id=plan_id, decision="approved", reason=reason)
        )
        self._kernel.publish(
            ApprovalGrantedEvent(
                source_component="governor",
                approval_id=approval_id,
                plan_id=plan_id,
                reason=reason,
                ordered_actions=ordered_actions,
            )
        )


__all__ = [
    "Constitution",
    "BudgetState",
    "ApprovalRecord",
    "Amendment",
    "EscalationRecord",
    "ConstitutionStore",
    "BudgetStore",
    "ApprovalLog",
    "AmendmentLog",
    "EscalationStore",
    "RuleRegistry",
    "RuleEvaluator",
    "DEFAULT_RULES",
    "Governor",
]
