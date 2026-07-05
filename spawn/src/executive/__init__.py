"""Executive: generates opportunities, scores them, ranks them, and proposes plans.

Owns the goal tree, opportunity store, plan store, and decision records.
The Executive proposes only — it does not approve, does not reserve budget,
does not touch Governor state, and does not execute. Its deliberation pipeline
ranks competing opportunities, estimates their expected value through the
Inference Port, allocates attention and capital across them, and commits to a
single winning plan while abandoning the rest.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from src.events import (
    BeliefCreatedEvent,
    BeliefUpdatedEvent,
    EventType,
    ExecutiveDecisionEvent,
    KernelStartedEvent,
    OpportunityGenerationCompletedEvent,
    OpportunityGenerationStartedEvent,
    OpportunityIdentifiedEvent,
    OpportunityScoredEvent,
    OutcomeRecordedEvent,
    PlanAbandonedEvent,
    PlanProposedEvent,
    ResearchIntentEvent,
    ResearchSpendApprovedEvent,
    ResearchSpendDeniedEvent,
    ResearchSpendRequestedEvent,
)
from src.inference import InferencePort, InferenceRequest
from src.kernel import Kernel

EXPECTED_VALUE_PER_CONFIDENCE = 100.0
ATTENTION_COST_BASELINE = 1.0
CAPITAL_COST_FRACTION = 0.1

# Deliberation tuning. Expected value is re-estimated through the Inference
# Port (raw value scaled by the provider's judgment); attention and capital a
# plan demands scale with that estimate, so the more an opportunity is worth
# the more of each scarce budget it asks for.
EV_ESTIMATION_PURPOSE = "estimate_expected_value"
ATTENTION_DEMAND_FRACTION = 0.05
CAPITAL_DEMAND_FRACTION = 0.1

# Cold-start research seeding (Charter §2/§6): with zero prior beliefs, the
# Executive still has to produce initial research intents derived from the
# objective, not from a hardcoded industry or venture pick. Each seed query
# asks a broad, industry-agnostic question aimed at DISCOVERING the space of
# possible ventures ("what business models/niches exist right now") — it
# never names a specific venture or industry to pursue. That is the whole
# distinction Charter §4 ("not a recommendation engine") and §6 ("humans do
# not choose industries, choose ventures") draw: discovering the search
# space is not the same act as selecting within it. Selection still happens
# later, in OpportunityGenerator/deliberate(), from whatever beliefs these
# seed queries' results eventually produce.
COLD_START_DELIBERATION_ID = "cold-start"
COLD_START_ESTIMATED_COST_PER_QUERY = 5.0
COLD_START_SEARCH_DEPTH = 1
COLD_START_SEED_QUERIES: tuple[tuple[str, int], ...] = (
    ("emerging profitable online business models 2026", 3),
    ("underserved niche markets with low startup cost", 2),
    ("recurring-revenue business models a solo operator can run", 1),
)

# Soft-stop heuristic (Executive's own call, distinct from Task #0's hard
# budget/search/depth caps): a simple diminishing-returns check, deliberately
# not over-engineered — every SOFT_STOP_WINDOW_SEARCHES searches issued, look
# at how many of them led to an accepted (novel) opportunity-generation pass;
# below SOFT_STOP_MIN_NOVEL_RATE, stop requesting more research until this
# is revisited. No Charter/Architecture amendment needed to change these
# numbers or the formula later.
SOFT_STOP_WINDOW_SEARCHES = 5
SOFT_STOP_MIN_NOVEL_RATE = 0.2


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


@dataclass(slots=True, kw_only=True, frozen=True)
class Allocation:
    """How much attention and capital deliberation apportioned to one candidate.

    ``funded`` is True when the candidate fit within the attention and capital
    still available when it was reached in ranked order; a funded candidate is
    executable and eligible to win, an unfunded one is discarded.
    """

    plan_id: str
    opportunity_id: str
    estimated_value: float
    attention_allocated: float
    capital_allocated: float
    funded: bool


@dataclass(slots=True, kw_only=True, frozen=True)
class DeliberationResult:
    """The outcome of one deliberation pass over the competing candidates."""

    winning_plan_id: Optional[str]
    ranked_plan_ids: tuple[str, ...]
    abandoned_plan_ids: tuple[str, ...]
    allocations: tuple[Allocation, ...]


@dataclass(slots=True, kw_only=True, frozen=True)
class _Candidate:
    """Working state for a single competing plan during one deliberation pass."""

    sequence: int
    plan: Plan
    opportunity: Opportunity
    estimated_value: float
    attention_demand: float
    capital_demand: float


@dataclass(slots=True, kw_only=True, frozen=True)
class OpportunityGroup:
    """An immutable record of the belief cluster aggregated into one opportunity.

    Append-only: a signature that gains further corroborating beliefs appends
    a NEW record under the same group_id rather than mutating the prior one,
    so replay never needs to recompute what aggregation already decided.
    """

    group_id: str
    signature: str
    belief_ids: tuple[str, ...]
    aggregated_confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class OpportunityGenerationRecord:
    """An immutable audit trail entry for one opportunity-generation pass transition.

    One record is appended per transition (started, then completed) — never
    mutated — mirroring LearningIteration/KnowledgeRevision's shape-evolution
    pattern, so the full history survives in OpportunityGenerationLedger even
    though `status` only ever describes that single transition.
    """

    generation_id: str
    status: str
    signature: str
    belief_ids: tuple[str, ...]
    started_at: datetime
    completed_at: Optional[datetime] = None
    accepted: Optional[bool] = None
    reason: Optional[str] = None
    group_id: Optional[str] = None
    opportunity_id: Optional[str] = None


@dataclass(slots=True, kw_only=True, frozen=True)
class ResolvedSituation:
    """An immutable record marking a signature as resolved via Memory's episodic history.

    Persists the novelty index across a snapshot boundary: without this, a
    signature resolved before the latest snapshot would be forgotten on
    restore (only events after the snapshot are replayed) and could be
    re-proposed as novel.
    """

    signature: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class PendingResearchIntent:
    """A research spend request awaiting Governor's approve/deny decision.

    Executive's own bookkeeping — recovers the query/priority/rationale a
    bare ResearchSpendApprovedEvent/ResearchSpendDeniedEvent (Task #0) can't
    carry, since that gate deliberately knows nothing about ResearchIntentEvent's
    schema. Matched back to its decision by request_id.
    """

    request_id: str
    query: str
    estimated_cost: float
    search_depth: int
    priority: int
    rationale: str
    deliberation_id: str


@dataclass(slots=True, kw_only=True, frozen=True)
class ResearchCandidate:
    """One candidate research query competing for scarce research budget."""

    query: str
    estimated_cost: float
    search_depth: int
    priority: int
    rationale: str
    deliberation_id: str


@dataclass(slots=True, kw_only=True, frozen=True)
class ResearchSoftStopState:
    """Executive's own diminishing-returns bookkeeping for the research soft stop.

    A single current-state snapshot (not an append-only ledger): only the
    latest counters matter for the next decision.
    """

    searches_issued_in_window: int
    novel_opportunities_in_window: int
    last_window_novel_rate: Optional[float]


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


class OpportunityGroupStore:
    """Append-only store of opportunity groups.

    A signature can appear more than once (initial acceptance, then further
    corroboration) — read_all() returns every version ever recorded, in order.
    """

    def __init__(self) -> None:
        self._groups: list[OpportunityGroup] = []

    def append(self, group: OpportunityGroup) -> None:
        self._groups.append(group)

    def read_all(self) -> list[OpportunityGroup]:
        return list(self._groups)


class OpportunityGenerationLedger:
    """Append-only log of opportunity-generation pass transitions.

    A generation_id can appear more than once (started, then completed) —
    read_all() returns every transition ever recorded, in order.
    """

    def __init__(self) -> None:
        self._records: list[OpportunityGenerationRecord] = []

    def append(self, record: OpportunityGenerationRecord) -> None:
        self._records.append(record)

    def read_all(self) -> list[OpportunityGenerationRecord]:
        return list(self._records)

    def history_for(self, generation_id: str) -> list[OpportunityGenerationRecord]:
        """All transitions recorded for a single generation pass, in order."""
        return [record for record in self._records if record.generation_id == generation_id]


class ResolvedSituationStore:
    """Append-only store of signatures resolved via Memory's episodic history."""

    def __init__(self) -> None:
        self._entries: list[ResolvedSituation] = []

    def append(self, entry: ResolvedSituation) -> None:
        self._entries.append(entry)

    def read_all(self) -> list[ResolvedSituation]:
        return list(self._entries)


class OpportunityGenerator:
    """Deterministic, stateless computation for aggregating related beliefs and
    suppressing non-novel or duplicate situations.

    Owns no store of its own — Executive owns OpportunityGenerationLedger and
    OpportunityGroupStore. Given the same belief cluster and the same seen-
    signature history, this always returns the same decision, which is what
    makes replay and repeated runs over identical history produce identical
    opportunities regardless of the order related beliefs originally arrived
    in.
    """

    def aggregate_confidence(self, confidences: list[float]) -> float:
        """The mean confidence across every belief in the aggregated group."""
        return round(sum(confidences) / len(confidences), 6)

    def decide(
        self,
        *,
        belief_ids: tuple[str, ...],
        previously_generated_belief_ids: Optional[tuple[str, ...]],
        already_resolved: bool,
    ) -> tuple[bool, str]:
        """Decide whether this belief cluster is novel enough to propose.

        Rejects an identical belief cluster already generated for this
        signature (duplicate situation, still in flight), and separately
        rejects a signature Memory's episodic history already shows was
        resolved (not novel), even if the cluster itself just grew.
        """
        if belief_ids == previously_generated_belief_ids:
            return False, "duplicate: identical belief cluster already generated"
        if already_resolved:
            return False, "not novel: situation already resolved in episodic memory"
        return True, "novel aggregated situation"


class Executive:
    """Reacts to belief events by proposing opportunities and plans. Proposes only."""

    def __init__(self, kernel: Kernel, inference_port: Optional[InferencePort] = None) -> None:
        self._kernel = kernel
        self._inference_port = inference_port
        self.goal_store = GoalStore()
        self.opportunity_store = OpportunityStore()
        self.plan_store = PlanStore()
        self.decision_record_store = DecisionRecordStore()
        self.opportunity_group_store = OpportunityGroupStore()
        self.opportunity_generation_ledger = OpportunityGenerationLedger()
        self.resolved_situation_store = ResolvedSituationStore()
        self._opportunity_generator = OpportunityGenerator()
        # Plans proposed but not yet decided, oldest first. Deliberation
        # ranks and clears these; the list order is the deterministic FIFO
        # tie-break among equally valued candidates.
        self._pending_plan_ids: list[str] = []
        # Executive's own read model of belief signals, built purely from the
        # events it already subscribes to (never reads World Model's store).
        self._belief_confidence: dict[str, float] = {}
        self._belief_claim: dict[str, str] = {}
        self._signature_for_belief: dict[str, str] = {}
        self._belief_ids_by_signature: dict[str, set[str]] = {}
        # Bookkeeping for aggregation and duplicate/novelty suppression.
        self._group_id_by_signature: dict[str, str] = {}
        self._last_generated_belief_ids: dict[str, tuple[str, ...]] = {}
        self._opportunity_signature: dict[str, str] = {}
        # Novelty index derived solely from Memory's OUTCOME_RECORDED events —
        # the sanctioned, event-based path into Memory's episodic history.
        self._resolved_signatures: set[str] = set()
        # Research spend requests awaiting Governor's decision (Task #0's
        # gate), keyed by request_id — never a new store, just an in-flight
        # correlation map, mirroring Governor's own _pending_amendments shape.
        self._pending_research_intents: dict[str, PendingResearchIntent] = {}
        # Soft-stop bookkeeping (distinct from Task #0's hard caps): reset
        # every SOFT_STOP_WINDOW_SEARCHES searches issued.
        self._searches_issued_in_window = 0
        self._novel_opportunities_in_window = 0
        self._last_window_novel_rate: Optional[float] = None
        kernel.register_subscriber(EventType.BELIEF_CREATED, self._on_belief_created)
        kernel.register_subscriber(EventType.BELIEF_UPDATED, self._on_belief_updated)
        kernel.register_subscriber(EventType.OPPORTUNITY_GENERATION_STARTED, self._on_opportunity_generation_started)
        kernel.register_subscriber(
            EventType.OPPORTUNITY_GENERATION_COMPLETED, self._on_opportunity_generation_completed
        )
        kernel.register_subscriber(EventType.OUTCOME_RECORDED, self._on_outcome_recorded)
        # Decision records for committed and abandoned plans are appended in
        # response to the emitted events, not inside deliberate() itself, so a
        # full replay of the log reconstructs them exactly as a live run did.
        kernel.register_subscriber(EventType.PLAN_SELECTED, self._on_plan_selected)
        kernel.register_subscriber(EventType.PLAN_ABANDONED, self._on_plan_abandoned)
        kernel.register_subscriber(EventType.RESEARCH_SPEND_APPROVED, self._on_research_spend_approved)
        kernel.register_subscriber(EventType.RESEARCH_SPEND_DENIED, self._on_research_spend_denied)
        kernel.register_subscriber(EventType.KERNEL_STARTED, self._on_kernel_started)
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
        kernel.register_snapshot_source(
            "executive.opportunity_groups",
            OpportunityGroup,
            self.opportunity_group_store.read_all,
            self._restore_opportunity_groups,
        )
        kernel.register_snapshot_source(
            "executive.opportunity_generation_records",
            OpportunityGenerationRecord,
            self.opportunity_generation_ledger.read_all,
            self._restore_opportunity_generation_records,
        )
        kernel.register_snapshot_source(
            "executive.resolved_situations",
            ResolvedSituation,
            self.resolved_situation_store.read_all,
            self._restore_resolved_situations,
        )
        kernel.register_snapshot_source(
            "executive.pending_research_intents",
            PendingResearchIntent,
            self._capture_pending_research_intents,
            self._restore_pending_research_intents,
        )
        kernel.register_snapshot_source(
            "executive.research_soft_stop_state",
            ResearchSoftStopState,
            self._capture_research_soft_stop_state,
            self._restore_research_soft_stop_state,
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

    def _restore_opportunity_groups(self, groups: list[OpportunityGroup]) -> None:
        for group in groups:
            self.opportunity_group_store.append(group)
            self._group_id_by_signature[group.signature] = group.group_id
            self._last_generated_belief_ids[group.signature] = group.belief_ids
            # signature is always "{correlation_id}:{claim_key}" (correlation_id
            # is a UUID's str(), which never contains ':'); recovering claim_key
            # here is what lets a belief event arriving after restore compute
            # the SAME signature its earlier sibling did, instead of falling
            # back to belief_id and silently opening a new, mismatched cluster.
            _, claim_key = group.signature.split(":", 1)
            for belief_id in group.belief_ids:
                self._belief_ids_by_signature.setdefault(group.signature, set()).add(belief_id)
                self._signature_for_belief[belief_id] = group.signature
                self._belief_claim.setdefault(belief_id, claim_key)
                # Per-member confidence isn't preserved by the group snapshot;
                # seed it with the group's aggregate so a signature reopened
                # after restore has a value to aggregate from until the next
                # belief event for that member overwrites it with the real one.
                self._belief_confidence.setdefault(belief_id, group.aggregated_confidence)

    def _restore_opportunity_generation_records(self, records: list[OpportunityGenerationRecord]) -> None:
        for record in records:
            self.opportunity_generation_ledger.append(record)
            if record.status == "completed" and record.accepted and record.opportunity_id is not None:
                self._opportunity_signature[record.opportunity_id] = record.signature

    def _restore_resolved_situations(self, entries: list[ResolvedSituation]) -> None:
        for entry in entries:
            self.resolved_situation_store.append(entry)
            self._resolved_signatures.add(entry.signature)

    def _capture_pending_research_intents(self) -> list[PendingResearchIntent]:
        return list(self._pending_research_intents.values())

    def _restore_pending_research_intents(self, records: list[PendingResearchIntent]) -> None:
        for record in records:
            self._pending_research_intents[record.request_id] = record

    def _capture_research_soft_stop_state(self) -> list[ResearchSoftStopState]:
        return [
            ResearchSoftStopState(
                searches_issued_in_window=self._searches_issued_in_window,
                novel_opportunities_in_window=self._novel_opportunities_in_window,
                last_window_novel_rate=self._last_window_novel_rate,
            )
        ]

    def _restore_research_soft_stop_state(self, records: list[ResearchSoftStopState]) -> None:
        if not records:
            return
        latest = records[-1]
        self._searches_issued_in_window = latest.searches_issued_in_window
        self._novel_opportunities_in_window = latest.novel_opportunities_in_window
        self._last_window_novel_rate = latest.last_window_novel_rate

    def _on_belief_created(self, event: BeliefCreatedEvent) -> None:
        self._belief_claim[event.belief_id] = event.claim
        self._register_belief_signal(
            belief_id=event.belief_id, confidence=event.confidence, correlation_id=event.correlation_id
        )

    def _on_belief_updated(self, event: BeliefUpdatedEvent) -> None:
        # BeliefUpdatedEvent carries no claim, so the cached claim from this
        # belief's own BeliefCreatedEvent (World Model never changes a
        # belief's claim on a decay tick) is reused; an update with no prior
        # cached claim falls back to the belief_id itself.
        self._register_belief_signal(
            belief_id=event.belief_id, confidence=event.new_confidence, correlation_id=event.correlation_id
        )

    def _register_belief_signal(self, *, belief_id: str, confidence: float, correlation_id: Optional[UUID]) -> None:
        """Record one belief signal and trigger an opportunity-generation pass.

        Beliefs are related when they share both a correlation_id (the same
        causal cascade) AND a claim (the same asserted situation) — a
        correlation_id alone is not enough: a batch of otherwise-unrelated
        beliefs updated back-to-back within one dispatch (e.g. World Model's
        apply_decay sweeping every belief in one call) shares one active
        correlation_id without being about the same situation. The actual
        accept/aggregate decision is made in `_on_opportunity_generation_started`,
        not here, so a sibling belief already queued for the same cascade is
        folded into the same pass regardless of which one arrives first.
        """
        claim_key = self._belief_claim.get(belief_id, belief_id)
        signature = f"{correlation_id}:{claim_key}"
        self._belief_confidence[belief_id] = confidence
        previous_signature = self._signature_for_belief.get(belief_id)
        if previous_signature is not None and previous_signature != signature:
            self._belief_ids_by_signature.get(previous_signature, set()).discard(belief_id)
        self._signature_for_belief[belief_id] = signature
        self._belief_ids_by_signature.setdefault(signature, set()).add(belief_id)
        self._kernel.publish(
            OpportunityGenerationStartedEvent(
                source_component="executive",
                generation_id=str(uuid4()),
                signature=signature,
                triggering_belief_id=belief_id,
            )
        )

    def _on_opportunity_generation_started(self, event: OpportunityGenerationStartedEvent) -> None:
        belief_ids = tuple(sorted(self._belief_ids_by_signature.get(event.signature, set())))
        self.opportunity_generation_ledger.append(
            OpportunityGenerationRecord(
                generation_id=event.generation_id,
                status="started",
                signature=event.signature,
                belief_ids=belief_ids,
                started_at=event.timestamp,
            )
        )

        if not belief_ids:
            # Every belief that was under this signature moved to a different
            # one before this pass was reached (e.g. the same belief_id
            # re-signatured twice within one undrained batch) — nothing is
            # left to aggregate, so this pass is stale rather than a decision.
            self._kernel.publish(
                OpportunityGenerationCompletedEvent(
                    source_component="executive",
                    generation_id=event.generation_id,
                    signature=event.signature,
                    belief_ids=belief_ids,
                    accepted=False,
                    aggregated_confidence=0.0,
                    reason="stale: no beliefs remain under this signature",
                )
            )
            return

        aggregated_confidence = self._opportunity_generator.aggregate_confidence(
            [self._belief_confidence[belief_id] for belief_id in belief_ids]
        )
        accepted, reason = self._opportunity_generator.decide(
            belief_ids=belief_ids,
            previously_generated_belief_ids=self._last_generated_belief_ids.get(event.signature),
            already_resolved=event.signature in self._resolved_signatures,
        )

        group_id: Optional[str] = None
        opportunity_id: Optional[str] = None
        if accepted:
            group_id = self._group_id_by_signature.get(event.signature) or str(uuid4())
            opportunity_id = str(uuid4())
            # Recorded immediately — not deferred to the Completed handler —
            # so a sibling generation pass for the same signature, already
            # queued right behind this one, sees this decision and is
            # correctly treated as a duplicate rather than racing to accept
            # the identical cluster a second time.
            self._group_id_by_signature[event.signature] = group_id
            self._last_generated_belief_ids[event.signature] = belief_ids

        self._kernel.publish(
            OpportunityGenerationCompletedEvent(
                source_component="executive",
                generation_id=event.generation_id,
                signature=event.signature,
                belief_ids=belief_ids,
                accepted=accepted,
                aggregated_confidence=aggregated_confidence,
                reason=reason,
                group_id=group_id,
                opportunity_id=opportunity_id,
            )
        )

    def _on_opportunity_generation_completed(self, event: OpportunityGenerationCompletedEvent) -> None:
        started_record = self.opportunity_generation_ledger.history_for(event.generation_id)[0]
        self.opportunity_generation_ledger.append(
            OpportunityGenerationRecord(
                generation_id=event.generation_id,
                status="completed",
                signature=event.signature,
                belief_ids=event.belief_ids,
                started_at=started_record.started_at,
                completed_at=event.timestamp,
                accepted=event.accepted,
                reason=event.reason,
                group_id=event.group_id,
                opportunity_id=event.opportunity_id,
            )
        )
        if not event.accepted:
            return

        # One data point for the research soft-stop heuristic: an accepted
        # (novel) opportunity-generation pass, regardless of which sensor or
        # belief triggered it. Until Task #2 wires research-attributed
        # beliefs, this is the best available proxy for "did the last batch
        # of searches turn up anything new."
        self._novel_opportunities_in_window += 1

        assert event.group_id is not None and event.opportunity_id is not None
        self.opportunity_group_store.append(
            OpportunityGroup(
                group_id=event.group_id,
                signature=event.signature,
                belief_ids=event.belief_ids,
                aggregated_confidence=event.aggregated_confidence,
            )
        )
        self._opportunity_signature[event.opportunity_id] = event.signature

        opportunity = self._identify_opportunity(
            opportunity_id=event.opportunity_id, belief_ids=event.belief_ids, confidence=event.aggregated_confidence
        )
        self._score_opportunity(opportunity)
        self._propose_plan(opportunity)

    def _on_outcome_recorded(self, event: OutcomeRecordedEvent) -> None:
        """Fold Memory's episodic history into the novelty index.

        The sole sanctioned path into Memory's episodic memory: Executive
        never reads Memory's stores directly, it only ever learns that a
        situation was resolved via this published event, resolved back to
        the signature through Executive's own plan/opportunity records.
        """
        try:
            plan = self.plan_store.get(event.plan_id)
        except KeyError:
            return
        signature = self._opportunity_signature.get(plan.opportunity_id)
        if signature is not None and signature not in self._resolved_signatures:
            self._resolved_signatures.add(signature)
            self.resolved_situation_store.append(ResolvedSituation(signature=signature))

    def _identify_opportunity(self, *, opportunity_id: str, belief_ids: tuple[str, ...], confidence: float) -> Opportunity:
        opportunity = Opportunity(
            opportunity_id=opportunity_id,
            belief_ids=belief_ids,
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
                rationale=f"beliefs {belief_ids} aggregated with confidence {confidence}",
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
        self._pending_plan_ids.append(plan.plan_id)
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

    def attach_inference_port(self, inference_port: InferencePort) -> None:
        """Wire the Inference Port used to estimate expected value.

        Kept separate from construction so the composition root can build the
        Executive before the port without an ordering constraint; the
        organism attaches it once both exist.
        """
        self._inference_port = inference_port

    def pending_plan_ids(self) -> list[str]:
        """Plans proposed but not yet committed or abandoned, oldest first."""
        return list(self._pending_plan_ids)

    def _should_continue_researching(self) -> bool:
        """Soft-stop check: has the last completed window shown diminishing returns?

        Distinct from Task #0's hard budget/search/depth caps — this is the
        Executive's own call about whether further research is still worth
        asking for. No completed window yet means no evidence of
        diminishing returns, so research is allowed to proceed.
        """
        if self._last_window_novel_rate is None:
            return True
        return self._last_window_novel_rate >= SOFT_STOP_MIN_NOVEL_RATE

    def _note_search_issued(self) -> None:
        self._searches_issued_in_window += 1
        if self._searches_issued_in_window >= SOFT_STOP_WINDOW_SEARCHES:
            self._last_window_novel_rate = round(
                self._novel_opportunities_in_window / self._searches_issued_in_window, 6
            )
            self._searches_issued_in_window = 0
            self._novel_opportunities_in_window = 0

    @staticmethod
    def _derive_research_request_id(*, deliberation_id: str, query: str, search_depth: int) -> str:
        """A deterministic, content-addressed request_id.

        `_on_kernel_started` (cold-start seeding) re-fires identically every
        time KERNEL_STARTED is dispatched — live once, then again on every
        future replay of that same historical event. A random uuid4() minted
        there would differ between the live run and its replay, breaking the
        later match against the Governor's ResearchSpendApprovedEvent /
        ResearchSpendDeniedEvent (which only ever echoes back whatever
        request_id it was actually sent — it doesn't re-mint). Deriving the
        id from the request's own already-deterministic inputs instead means
        replay reproduces the identical id, so this ledger's `pop(request_id)`
        below always finds its match. Two genuinely distinct calls that
        happen to share all three fields collide by design — out of scope
        for this task's callers (cold start's queries are all distinct).
        """
        digest = hashlib.sha256(f"{deliberation_id}:{query}:{search_depth}".encode()).hexdigest()[:32]
        return f"research-{digest}"

    def request_research(
        self,
        *,
        query: str,
        estimated_cost: float,
        search_depth: int,
        priority: int,
        rationale: str,
        deliberation_id: str,
    ) -> Optional[str]:
        """Request approval to research one query, gated through Task #0's Governor.

        Returns the request_id used to correlate the eventual approve/deny
        decision, or None if the soft-stop heuristic decided not to even ask
        (recorded as a decision either way). Never emits ResearchIntentEvent
        directly — that only happens in `_on_research_spend_approved`, once
        the Governor has actually granted the spend.
        """
        if not self._should_continue_researching():
            self.decision_record_store.append(
                DecisionRecord(
                    decision_id=str(uuid4()),
                    decision_type="research_soft_stopped",
                    subject_id=deliberation_id,
                    rationale=(
                        f"query={query!r} not requested: last_window_novel_rate="
                        f"{self._last_window_novel_rate} below minimum {SOFT_STOP_MIN_NOVEL_RATE}"
                    ),
                )
            )
            return None

        request_id = self._derive_research_request_id(
            deliberation_id=deliberation_id, query=query, search_depth=search_depth
        )
        self._pending_research_intents[request_id] = PendingResearchIntent(
            request_id=request_id,
            query=query,
            estimated_cost=estimated_cost,
            search_depth=search_depth,
            priority=priority,
            rationale=rationale,
            deliberation_id=deliberation_id,
        )
        self._note_search_issued()
        self._kernel.publish(
            ResearchSpendRequestedEvent(
                source_component="executive",
                request_id=request_id,
                deliberation_id=deliberation_id,
                category="research",
                estimated_cost=estimated_cost,
                search_depth=search_depth,
            )
        )
        return request_id

    def request_research_batch(self, candidates: list[ResearchCandidate]) -> list[Optional[str]]:
        """Rank competing research candidates and request each in ranked order.

        Priority/ranking of competing research intents when budget is
        scarce is the Executive's own call: reuses the same shape as
        `deliberate()`'s ranking (highest value first, oldest-enumerated
        first on ties) rather than a separate mechanism. Ranking here only
        decides which candidates get first claim on whatever Task #0's hard
        caps allow through — the caps themselves are still enforced solely
        by the Governor.
        """
        ranked = sorted(enumerate(candidates), key=lambda pair: (-pair[1].priority, pair[0]))
        request_ids: list[Optional[str]] = [None] * len(candidates)
        for original_index, candidate in ranked:
            request_ids[original_index] = self.request_research(
                query=candidate.query,
                estimated_cost=candidate.estimated_cost,
                search_depth=candidate.search_depth,
                priority=candidate.priority,
                rationale=candidate.rationale,
                deliberation_id=candidate.deliberation_id,
            )
        return request_ids

    def _on_research_spend_approved(self, event: ResearchSpendApprovedEvent) -> None:
        pending = self._pending_research_intents.pop(event.request_id, None)
        if pending is None:
            return
        self._kernel.publish(
            ResearchIntentEvent(
                source_component="executive",
                request_id=event.request_id,
                query=pending.query,
                estimated_cost=event.approved_cost,
                search_depth=pending.search_depth,
                priority=pending.priority,
                rationale=pending.rationale,
            )
        )
        self.decision_record_store.append(
            DecisionRecord(
                decision_id=str(uuid4()),
                decision_type="research_intent_emitted",
                subject_id=event.request_id,
                rationale=f"query={pending.query!r} approved_cost={event.approved_cost} reason={event.reason}",
            )
        )

    def _on_research_spend_denied(self, event: ResearchSpendDeniedEvent) -> None:
        pending = self._pending_research_intents.pop(event.request_id, None)
        if pending is None:
            return
        self.decision_record_store.append(
            DecisionRecord(
                decision_id=str(uuid4()),
                decision_type="research_intent_denied",
                subject_id=event.request_id,
                rationale=f"query={pending.query!r} denied: {event.reason}",
            )
        )

    def _on_kernel_started(self, event: KernelStartedEvent) -> None:
        """Cold-start research seeding (Charter §2/§6): with zero prior beliefs,
        derive initial research intents from the objective instead of sitting idle.

        Guarded by both conditions so a restart with existing history never
        re-seeds: `replay()` (which runs before KERNEL_STARTED, per
        Kernel.start()) would already have repopulated `_belief_confidence`
        and this decision-record marker from that history.
        """
        already_seeded = any(
            record.decision_type == "cold_start_research_seeded" for record in self.decision_record_store.read_all()
        )
        if already_seeded or self._belief_confidence:
            return

        candidates = [
            ResearchCandidate(
                query=query,
                estimated_cost=COLD_START_ESTIMATED_COST_PER_QUERY,
                search_depth=COLD_START_SEARCH_DEPTH,
                priority=priority,
                rationale="cold-start: discover venture space from objective, no prior beliefs",
                deliberation_id=COLD_START_DELIBERATION_ID,
            )
            for query, priority in COLD_START_SEED_QUERIES
        ]
        self.request_research_batch(candidates)
        self.decision_record_store.append(
            DecisionRecord(
                decision_id=str(uuid4()),
                decision_type="cold_start_research_seeded",
                subject_id=COLD_START_DELIBERATION_ID,
                rationale=f"issued {len(candidates)} seed queries derived from the objective",
            )
        )

    def deliberate(self, *, available_attention: float, available_capital: float) -> Optional[DeliberationResult]:
        """Run one deliberation pass over every pending candidate plan.

        Ranks the competing opportunities by Inference-Port-estimated expected
        value, allocates the shared attention and capital budgets across them
        in ranked order, commits to the single highest-value executable plan
        with an ``ExecutiveDecisionEvent``, and abandons every other candidate
        with a ``PlanAbandonedEvent``. Returns ``None`` when nothing is pending.

        This never reserves budget, approves, or executes — the caller passes
        in the currently available attention and capital, and the Executive
        only proposes a commitment. Enforcement stays with the Governor.
        """
        if self._inference_port is None:
            raise RuntimeError("deliberation requires an inference port; call attach_inference_port first")
        if not self._pending_plan_ids:
            return None

        # Step 1 + 2: build candidates, estimating expected value through the
        # Inference Port. Enumeration order is the FIFO tie-break for ranking.
        candidates = [
            self._build_candidate(sequence, plan_id)
            for sequence, plan_id in enumerate(self._pending_plan_ids)
        ]

        # Step 1: rank competing opportunities — highest estimated value first,
        # oldest-proposed first on ties, so ranking is fully deterministic.
        ranked = sorted(candidates, key=lambda c: (-c.estimated_value, c.sequence))

        # Step 3 + 4: allocate attention across, then capital within, the
        # available budgets. Walking in ranked order spends each scarce budget
        # on the most valuable opportunities first; a candidate that no longer
        # fits is left unfunded and therefore not executable.
        remaining_attention = available_attention
        remaining_capital = available_capital
        allocations: list[Allocation] = []
        funded_reasons: dict[str, str] = {}
        winner_plan_id: Optional[str] = None
        for candidate in ranked:
            attention_ok = candidate.attention_demand <= remaining_attention
            capital_ok = candidate.capital_demand <= remaining_capital
            funded = attention_ok and capital_ok
            if funded:
                remaining_attention -= candidate.attention_demand
                remaining_capital -= candidate.capital_demand
                # Step 5: the first funded candidate in value-descending order
                # is the highest-value executable plan — the winner.
                if winner_plan_id is None:
                    winner_plan_id = candidate.plan.plan_id
            else:
                funded_reasons[candidate.plan.plan_id] = self._shortfall_reason(attention_ok, capital_ok)
            allocations.append(
                Allocation(
                    plan_id=candidate.plan.plan_id,
                    opportunity_id=candidate.opportunity.opportunity_id,
                    estimated_value=candidate.estimated_value,
                    attention_allocated=candidate.attention_demand if funded else 0.0,
                    capital_allocated=candidate.capital_demand if funded else 0.0,
                    funded=funded,
                )
            )

        allocation_by_plan = {allocation.plan_id: allocation for allocation in allocations}

        # Step 6: commit to the winner. Step 7: abandon every other candidate.
        # Emit in ranked order for a deterministic, auditable event sequence.
        abandoned_plan_ids: list[str] = []
        for candidate in ranked:
            plan_id = candidate.plan.plan_id
            allocation = allocation_by_plan[plan_id]
            if plan_id == winner_plan_id:
                self._commit_plan(candidate, allocation, len(candidates))
            else:
                abandoned_plan_ids.append(plan_id)
                self._abandon_plan(candidate, allocation, winner_plan_id, funded_reasons.get(plan_id))

        self._pending_plan_ids.clear()
        return DeliberationResult(
            winning_plan_id=winner_plan_id,
            ranked_plan_ids=tuple(c.plan.plan_id for c in ranked),
            abandoned_plan_ids=tuple(abandoned_plan_ids),
            allocations=tuple(allocations),
        )

    def _build_candidate(self, sequence: int, plan_id: str) -> _Candidate:
        plan = self.plan_store.get(plan_id)
        opportunity = self.opportunity_store.get(plan.opportunity_id)
        estimated_value = self._estimate_expected_value(opportunity)
        return _Candidate(
            sequence=sequence,
            plan=plan,
            opportunity=opportunity,
            estimated_value=estimated_value,
            attention_demand=round(estimated_value * ATTENTION_DEMAND_FRACTION, 4),
            capital_demand=round(estimated_value * CAPITAL_DEMAND_FRACTION, 4),
        )

    def _estimate_expected_value(self, opportunity: Opportunity) -> float:
        """Estimate an opportunity's expected value through the Inference Port.

        The provider's judgment (its returned confidence) scales the
        opportunity's raw expected value, so the estimate genuinely flows
        through the swappable port rather than a hardcoded formula.
        """
        assert self._inference_port is not None  # guarded by deliberate()
        request = InferenceRequest(
            request_id=str(uuid4()),
            requester="executive",
            purpose=EV_ESTIMATION_PURPOSE,
            context={
                "opportunity_id": opportunity.opportunity_id,
                "raw_expected_value": str(opportunity.expected_value),
                "confidence": str(opportunity.confidence),
            },
            constraints=(),
        )
        response = self._inference_port.infer(request)
        return round(opportunity.expected_value * response.confidence, 4)

    @staticmethod
    def _shortfall_reason(attention_ok: bool, capital_ok: bool) -> str:
        if not attention_ok and not capital_ok:
            return "insufficient attention and capital allocation"
        if not attention_ok:
            return "insufficient attention allocation"
        return "insufficient capital allocation"

    def _commit_plan(self, candidate: _Candidate, allocation: Allocation, candidate_count: int) -> None:
        rationale = (
            f"highest-value executable plan among {candidate_count} candidate(s): "
            f"estimated_value={allocation.estimated_value} "
            f"attention_allocated={allocation.attention_allocated} "
            f"capital_allocated={allocation.capital_allocated}"
        )
        self._kernel.publish(
            ExecutiveDecisionEvent(
                source_component="executive",
                decision_id=str(uuid4()),
                plan_id=candidate.plan.plan_id,
                rationale=rationale,
            )
        )

    def _abandon_plan(
        self,
        candidate: _Candidate,
        allocation: Allocation,
        winner_plan_id: Optional[str],
        shortfall_reason: Optional[str],
    ) -> None:
        if not allocation.funded and shortfall_reason is not None:
            reason = f"{shortfall_reason}: estimated_value={allocation.estimated_value}"
        elif winner_plan_id is not None:
            reason = (
                f"not selected: estimated_value={allocation.estimated_value} "
                f"ranked below winning plan {winner_plan_id}"
            )
        else:
            reason = f"no executable plan selected: estimated_value={allocation.estimated_value}"
        self._kernel.publish(
            PlanAbandonedEvent(
                source_component="executive",
                plan_id=candidate.plan.plan_id,
                reason=reason,
            )
        )

    def _on_plan_selected(self, event: ExecutiveDecisionEvent) -> None:
        self.decision_record_store.append(
            DecisionRecord(
                decision_id=str(uuid4()),
                decision_type="plan_selected",
                subject_id=event.plan_id,
                rationale=event.rationale,
            )
        )

    def _on_plan_abandoned(self, event: PlanAbandonedEvent) -> None:
        self.decision_record_store.append(
            DecisionRecord(
                decision_id=str(uuid4()),
                decision_type="plan_abandoned",
                subject_id=event.plan_id,
                rationale=event.reason,
            )
        )


__all__ = [
    "Goal",
    "GoalStore",
    "Opportunity",
    "OpportunityStore",
    "OpportunityGroup",
    "OpportunityGroupStore",
    "OpportunityGenerationRecord",
    "OpportunityGenerationLedger",
    "OpportunityGenerator",
    "ResolvedSituation",
    "ResolvedSituationStore",
    "Plan",
    "PlanStore",
    "DecisionRecord",
    "DecisionRecordStore",
    "Allocation",
    "DeliberationResult",
    "PendingResearchIntent",
    "ResearchCandidate",
    "ResearchSoftStopState",
    "COLD_START_DELIBERATION_ID",
    "COLD_START_ESTIMATED_COST_PER_QUERY",
    "COLD_START_SEARCH_DEPTH",
    "COLD_START_SEED_QUERIES",
    "SOFT_STOP_WINDOW_SEARCHES",
    "SOFT_STOP_MIN_NOVEL_RATE",
    "Executive",
]
