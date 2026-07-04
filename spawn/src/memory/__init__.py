"""Memory & Ledger: records outcomes, episodic memory, financial ledger, learned heuristics.

Owns episodic memory, the financial ledger, prediction history, and learned
heuristics. Reacts to executed actions and resolves predictions against
their outcomes, running the Medium Learning Loop to revise heuristics from
accumulated prediction error, and periodically running the Slow Learning
Loop to consolidate accumulated heuristic history into durable long-term
knowledge. Never updates the Executive, Governor, Executor, or World Model
directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.events import (
    ActionFailedEvent,
    ActionSucceededEvent,
    EventType,
    KnowledgeRevisionCompletedEvent,
    KnowledgeRevisionStartedEvent,
    LearningIterationCompletedEvent,
    LearningIterationStartedEvent,
    LedgerEntryPostedEvent,
    OutcomeRecordedEvent,
    PlanProposedEvent,
    PredictionRecordedEvent,
    PredictionResolvedEvent,
)
from src.kernel import Kernel

# Nominal per-action cost. Attention and capital were already reserved by the
# Governor at plan-approval time; a successful action realizes that reservation
# as spend. A failed action consumes no additional resources beyond the attempt.
ATTENTION_COST_PER_ACTION = 1.0
CAPITAL_COST_PER_ACTION = 1.0


@dataclass(slots=True, kw_only=True, frozen=True)
class Outcome:
    """The result of a single executed action."""

    outcome_id: str
    action_id: str
    plan_id: str
    success: bool
    result: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class EpisodicMemoryEntry:
    """A durable, human-readable record of a single outcome."""

    memory_id: str
    outcome_id: str
    summary: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class LedgerEntry:
    """A single financial ledger movement caused by an executed action."""

    entry_id: str
    action_id: str
    delta_attention: float
    delta_capital: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class Heuristic:
    """A learned rule of thumb distilled from repeated outcomes."""

    heuristic_id: str
    description: str
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OutcomeStore:
    """Append-only store of outcomes, keyed by outcome_id."""

    def __init__(self) -> None:
        self._outcomes: list[Outcome] = []
        self._by_id: dict[str, Outcome] = {}

    def append(self, outcome: Outcome) -> None:
        self._outcomes.append(outcome)
        self._by_id[outcome.outcome_id] = outcome

    def get(self, outcome_id: str) -> Outcome:
        return self._by_id[outcome_id]

    def read_all(self) -> list[Outcome]:
        return list(self._outcomes)


class EpisodicMemoryStore:
    """Append-only store of episodic memory entries."""

    def __init__(self) -> None:
        self._entries: list[EpisodicMemoryEntry] = []

    def append(self, entry: EpisodicMemoryEntry) -> None:
        self._entries.append(entry)

    def read_all(self) -> list[EpisodicMemoryEntry]:
        return list(self._entries)


class FinancialLedger:
    """Append-only ledger of financial entries."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    def append(self, entry: LedgerEntry) -> None:
        self._entries.append(entry)

    def read_all(self) -> list[LedgerEntry]:
        return list(self._entries)


class HeuristicStore:
    """Append-only store of learned heuristics."""

    def __init__(self) -> None:
        self._heuristics: list[Heuristic] = []

    def append(self, heuristic: Heuristic) -> None:
        self._heuristics.append(heuristic)

    def read_all(self) -> list[Heuristic]:
        return list(self._heuristics)


@dataclass(slots=True, kw_only=True, frozen=True)
class PredictionRecord:
    """An immutable audit trail entry for one prediction lifecycle transition.

    One record is appended per transition (pending, then resolved) — never
    mutated — mirroring the Governor's Amendment/Escalation record shape,
    so the full history survives in PredictionLedger even though `status`
    only ever describes that single transition. This is raw experience for
    later learning loops to consume — it does not itself learn anything.
    """

    prediction_id: str
    plan_id: str
    predicted_value: float
    status: str
    created_at: datetime
    outcome_id: Optional[str] = None
    actual_value: Optional[float] = None
    prediction_error: Optional[float] = None
    resolved_at: Optional[datetime] = None


class PredictionLedger:
    """Append-only log of prediction lifecycle transitions.

    A prediction_id can appear more than once (pending, then resolved) —
    read_all() returns every transition ever recorded, in order.
    """

    def __init__(self) -> None:
        self._records: list[PredictionRecord] = []

    def append(self, record: PredictionRecord) -> None:
        self._records.append(record)

    def read_all(self) -> list[PredictionRecord]:
        return list(self._records)

    def history_for(self, prediction_id: str) -> list[PredictionRecord]:
        """All transitions recorded for a single prediction, in order."""
        return [record for record in self._records if record.prediction_id == prediction_id]


@dataclass(slots=True, kw_only=True, frozen=True)
class LearningIteration:
    """An immutable audit trail entry for one Medium Learning Loop pass.

    One record is appended per transition (started, then completed) — never
    mutated — mirroring PredictionRecord's shape, so the full history
    survives in LearningLedger even though `status` only ever describes
    that single transition.
    """

    iteration_id: str
    status: str
    predictions_considered: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    mean_prediction_error: Optional[float] = None
    heuristic_id: Optional[str] = None


class LearningLedger:
    """Append-only log of Medium Learning Loop iteration transitions.

    An iteration_id can appear more than once (started, then completed) —
    read_all() returns every transition ever recorded, in order.
    """

    def __init__(self) -> None:
        self._records: list[LearningIteration] = []

    def append(self, record: LearningIteration) -> None:
        self._records.append(record)

    def read_all(self) -> list[LearningIteration]:
        return list(self._records)

    def history_for(self, iteration_id: str) -> list[LearningIteration]:
        """All transitions recorded for a single iteration, in order."""
        return [record for record in self._records if record.iteration_id == iteration_id]


class MediumLearner:
    """Deterministic, stateless computation for the Medium Learning Loop.

    Owns no store of its own — MemoryLedger owns LearningLedger and
    HeuristicStore. Given the same resolved-prediction history, this
    always returns the same values, which is what makes replay and
    repeated runs over identical history produce identical heuristics.
    """

    def compute_mean_error(self, resolved_predictions: list[PredictionRecord]) -> float:
        """The mean prediction_error across every resolved prediction handed in."""
        errors = [record.prediction_error for record in resolved_predictions if record.prediction_error is not None]
        if not errors:
            return 0.0
        return sum(errors) / len(errors)

    def compute_confidence(self, predictions_considered: int) -> float:
        """More accumulated history yields higher confidence, capped short of certainty."""
        return min(0.99, predictions_considered / (predictions_considered + 5))

    def describe(self, *, mean_prediction_error: float, predictions_considered: int) -> str:
        return (
            f"calibration: mean prediction error {mean_prediction_error:.6f} "
            f"over {predictions_considered} resolved predictions"
        )


@dataclass(slots=True, kw_only=True, frozen=True)
class KnowledgeRevision:
    """An immutable audit trail entry for one Slow Learning Loop consolidation pass.

    Mirrors LearningIteration's shape-evolution pattern: one record is
    appended per transition (started, then completed) — never mutated —
    so the full history survives in KnowledgeLedger even though `status`
    only ever describes that single transition.
    """

    revision_id: str
    status: str
    heuristics_considered: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    consensus_confidence: Optional[float] = None
    knowledge_id: Optional[str] = None


class KnowledgeLedger:
    """Append-only log of Slow Learning Loop revision transitions.

    A revision_id can appear more than once (started, then completed) —
    read_all() returns every transition ever recorded, in order.
    """

    def __init__(self) -> None:
        self._records: list[KnowledgeRevision] = []

    def append(self, record: KnowledgeRevision) -> None:
        self._records.append(record)

    def read_all(self) -> list[KnowledgeRevision]:
        return list(self._records)

    def history_for(self, revision_id: str) -> list[KnowledgeRevision]:
        """All transitions recorded for a single revision, in order."""
        return [record for record in self._records if record.revision_id == revision_id]


@dataclass(slots=True, kw_only=True, frozen=True)
class LongTermKnowledge:
    """A durable, consolidated piece of knowledge distilled from heuristic history."""

    knowledge_id: str
    summary: str
    consensus_confidence: float
    heuristics_considered: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LongTermKnowledgeStore:
    """Append-only store of durable, consolidated long-term knowledge."""

    def __init__(self) -> None:
        self._entries: list[LongTermKnowledge] = []

    def append(self, entry: LongTermKnowledge) -> None:
        self._entries.append(entry)

    def read_all(self) -> list[LongTermKnowledge]:
        return list(self._entries)


class SlowLearner:
    """Deterministic, stateless computation for the Slow Learning Loop.

    Owns no store of its own — MemoryLedger owns KnowledgeLedger and
    LongTermKnowledgeStore. Given the same heuristic history, this always
    returns the same values, which is what makes replay and repeated runs
    over identical history produce identical knowledge revisions.
    """

    CONSOLIDATION_INTERVAL = 3

    def should_consolidate(self, heuristics_considered: int) -> bool:
        """Periodic trigger: consolidate every CONSOLIDATION_INTERVAL accumulated heuristics."""
        return heuristics_considered > 0 and heuristics_considered % self.CONSOLIDATION_INTERVAL == 0

    def compute_consensus_confidence(self, heuristics: list[Heuristic]) -> float:
        """The mean confidence across every heuristic handed in."""
        confidences = [heuristic.confidence for heuristic in heuristics]
        if not confidences:
            return 0.0
        return sum(confidences) / len(confidences)

    def describe(self, *, consensus_confidence: float, heuristics_considered: int) -> str:
        return (
            f"knowledge consolidation: consensus confidence {consensus_confidence:.6f} "
            f"over {heuristics_considered} heuristics"
        )


class MemoryLedger:
    """Records outcomes, episodic memory, and ledger entries for every executed action."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.outcome_store = OutcomeStore()
        self.episodic_memory_store = EpisodicMemoryStore()
        self.financial_ledger = FinancialLedger()
        self.heuristic_store = HeuristicStore()
        self.prediction_ledger = PredictionLedger()
        self.learning_ledger = LearningLedger()
        self.medium_learner = MediumLearner()
        self.knowledge_ledger = KnowledgeLedger()
        self.long_term_knowledge_store = LongTermKnowledgeStore()
        self.slow_learner = SlowLearner()
        self._pending_predictions: dict[str, PredictionRecord] = {}
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, self._on_action_succeeded)
        kernel.register_subscriber(EventType.ACTION_FAILED, self._on_action_failed)
        kernel.register_subscriber(EventType.PLAN_PROPOSED, self._on_plan_proposed)
        kernel.register_subscriber(EventType.PREDICTION_RECORDED, self._on_prediction_recorded)
        kernel.register_subscriber(EventType.OUTCOME_RECORDED, self._on_outcome_recorded_for_prediction)
        kernel.register_subscriber(EventType.PREDICTION_RESOLVED, self._on_prediction_resolved)
        kernel.register_subscriber(EventType.LEARNING_ITERATION_STARTED, self._on_learning_iteration_started)
        kernel.register_subscriber(EventType.LEARNING_ITERATION_COMPLETED, self._on_learning_iteration_completed)
        kernel.register_subscriber(EventType.KNOWLEDGE_REVISION_STARTED, self._on_knowledge_revision_started)
        kernel.register_subscriber(EventType.KNOWLEDGE_REVISION_COMPLETED, self._on_knowledge_revision_completed)
        kernel.register_snapshot_source(
            "memory.outcomes", Outcome, self.outcome_store.read_all, self._restore_outcomes
        )
        kernel.register_snapshot_source(
            "memory.episodic_entries",
            EpisodicMemoryEntry,
            self.episodic_memory_store.read_all,
            self._restore_episodic_entries,
        )
        kernel.register_snapshot_source(
            "memory.ledger_entries", LedgerEntry, self.financial_ledger.read_all, self._restore_ledger_entries
        )
        kernel.register_snapshot_source(
            "memory.predictions", PredictionRecord, self.prediction_ledger.read_all, self._restore_predictions
        )
        kernel.register_snapshot_source(
            "memory.learning_iterations",
            LearningIteration,
            self.learning_ledger.read_all,
            self._restore_learning_iterations,
        )
        kernel.register_snapshot_source(
            "memory.heuristics", Heuristic, self.heuristic_store.read_all, self._restore_heuristics
        )
        kernel.register_snapshot_source(
            "memory.knowledge_revisions",
            KnowledgeRevision,
            self.knowledge_ledger.read_all,
            self._restore_knowledge_revisions,
        )
        kernel.register_snapshot_source(
            "memory.long_term_knowledge",
            LongTermKnowledge,
            self.long_term_knowledge_store.read_all,
            self._restore_long_term_knowledge,
        )

    def _restore_outcomes(self, outcomes: list[Outcome]) -> None:
        for outcome in outcomes:
            self.outcome_store.append(outcome)

    def _restore_episodic_entries(self, entries: list[EpisodicMemoryEntry]) -> None:
        for entry in entries:
            self.episodic_memory_store.append(entry)

    def _restore_ledger_entries(self, entries: list[LedgerEntry]) -> None:
        for entry in entries:
            self.financial_ledger.append(entry)

    def _restore_learning_iterations(self, records: list[LearningIteration]) -> None:
        for record in records:
            self.learning_ledger.append(record)

    def _restore_heuristics(self, heuristics: list[Heuristic]) -> None:
        for heuristic in heuristics:
            self.heuristic_store.append(heuristic)

    def _restore_predictions(self, records: list[PredictionRecord]) -> None:
        for record in records:
            self.prediction_ledger.append(record)
        latest_by_plan: dict[str, PredictionRecord] = {}
        for record in records:
            latest_by_plan[record.plan_id] = record
        self._pending_predictions = {
            plan_id: record for plan_id, record in latest_by_plan.items() if record.status == "pending"
        }

    def _restore_knowledge_revisions(self, records: list[KnowledgeRevision]) -> None:
        for record in records:
            self.knowledge_ledger.append(record)

    def _restore_long_term_knowledge(self, entries: list[LongTermKnowledge]) -> None:
        for entry in entries:
            self.long_term_knowledge_store.append(entry)

    def _on_plan_proposed(self, event: PlanProposedEvent) -> None:
        """Record a prediction before execution: the plan's expected value.

        Publishes PredictionRecordedEvent, which is what actually stores it
        (via this component's own subscriber), so recording is
        replay-correct. Whether the plan is ever approved or executed is
        unknown at this point; an unmatched prediction simply stays pending.
        """
        self._kernel.publish(
            PredictionRecordedEvent(
                source_component="memory_ledger",
                prediction_id=str(uuid4()),
                plan_id=event.plan_id,
                predicted_value=event.expected_value,
            )
        )

    def _on_prediction_recorded(self, event: PredictionRecordedEvent) -> None:
        record = PredictionRecord(
            prediction_id=event.prediction_id,
            plan_id=event.plan_id,
            predicted_value=event.predicted_value,
            status="pending",
            created_at=event.timestamp,
        )
        self.prediction_ledger.append(record)
        self._pending_predictions[event.plan_id] = record

    def _on_outcome_recorded_for_prediction(self, event: OutcomeRecordedEvent) -> None:
        """Resolve the plan's pending prediction against its first arriving outcome.

        A plan may execute several actions (several outcomes); the pending
        entry is claimed (popped) synchronously, right here, so a second
        outcome for the same plan finds nothing pending and is ignored —
        this must happen before publishing, not inside the subscriber for
        the resolution event, since the Kernel's FIFO scheduler would
        otherwise dispatch a second plan outcome before the first
        resolution event and double-resolve.
        """
        pending = self._pending_predictions.pop(event.plan_id, None)
        if pending is None:
            return
        actual_value = pending.predicted_value if event.success else 0.0
        prediction_error = actual_value - pending.predicted_value
        self._kernel.publish(
            PredictionResolvedEvent(
                source_component="memory_ledger",
                prediction_id=pending.prediction_id,
                plan_id=event.plan_id,
                outcome_id=event.outcome_id,
                predicted_value=pending.predicted_value,
                actual_value=actual_value,
                prediction_error=prediction_error,
            )
        )

    def _on_prediction_resolved(self, event: PredictionResolvedEvent) -> None:
        proposed = self.prediction_ledger.history_for(event.prediction_id)[0]
        self.prediction_ledger.append(
            PredictionRecord(
                prediction_id=event.prediction_id,
                plan_id=event.plan_id,
                predicted_value=event.predicted_value,
                status="resolved",
                created_at=proposed.created_at,
                outcome_id=event.outcome_id,
                actual_value=event.actual_value,
                prediction_error=event.prediction_error,
                resolved_at=event.timestamp,
            )
        )

        # Every newly resolved prediction is one "per outcome" tick of the
        # Medium Learning Loop: publishing here (rather than mutating
        # directly) is what keeps the loop replay-correct.
        resolved_predictions = [record for record in self.prediction_ledger.read_all() if record.status == "resolved"]
        self._kernel.publish(
            LearningIterationStartedEvent(
                source_component="memory_ledger",
                iteration_id=str(uuid4()),
                predictions_considered=len(resolved_predictions),
            )
        )

    def _on_learning_iteration_started(self, event: LearningIterationStartedEvent) -> None:
        self.learning_ledger.append(
            LearningIteration(
                iteration_id=event.iteration_id,
                status="started",
                predictions_considered=event.predictions_considered,
                started_at=event.timestamp,
            )
        )

        resolved_predictions = [record for record in self.prediction_ledger.read_all() if record.status == "resolved"]
        mean_prediction_error = self.medium_learner.compute_mean_error(resolved_predictions)
        self._kernel.publish(
            LearningIterationCompletedEvent(
                source_component="memory_ledger",
                iteration_id=event.iteration_id,
                predictions_considered=event.predictions_considered,
                mean_prediction_error=mean_prediction_error,
                heuristic_id=str(uuid4()),
            )
        )

    def _on_learning_iteration_completed(self, event: LearningIterationCompletedEvent) -> None:
        proposed = self.learning_ledger.history_for(event.iteration_id)[0]
        self.learning_ledger.append(
            LearningIteration(
                iteration_id=event.iteration_id,
                status="completed",
                predictions_considered=event.predictions_considered,
                started_at=proposed.started_at,
                completed_at=event.timestamp,
                mean_prediction_error=event.mean_prediction_error,
                heuristic_id=event.heuristic_id,
            )
        )
        self.heuristic_store.append(
            Heuristic(
                heuristic_id=event.heuristic_id,
                description=self.medium_learner.describe(
                    mean_prediction_error=event.mean_prediction_error,
                    predictions_considered=event.predictions_considered,
                ),
                confidence=self.medium_learner.compute_confidence(event.predictions_considered),
                created_at=event.timestamp,
            )
        )

        # Every completed Medium Learning iteration is one tick of the Slow
        # Learning Loop's periodic check: publishing here (rather than
        # mutating directly) is what keeps consolidation replay-correct.
        heuristics_considered = len(self.heuristic_store.read_all())
        if self.slow_learner.should_consolidate(heuristics_considered):
            self._kernel.publish(
                KnowledgeRevisionStartedEvent(
                    source_component="memory_ledger",
                    revision_id=str(uuid4()),
                    heuristics_considered=heuristics_considered,
                )
            )

    def _on_knowledge_revision_started(self, event: KnowledgeRevisionStartedEvent) -> None:
        self.knowledge_ledger.append(
            KnowledgeRevision(
                revision_id=event.revision_id,
                status="started",
                heuristics_considered=event.heuristics_considered,
                started_at=event.timestamp,
            )
        )

        consensus_confidence = self.slow_learner.compute_consensus_confidence(self.heuristic_store.read_all())
        self._kernel.publish(
            KnowledgeRevisionCompletedEvent(
                source_component="memory_ledger",
                revision_id=event.revision_id,
                heuristics_considered=event.heuristics_considered,
                consensus_confidence=consensus_confidence,
                knowledge_id=str(uuid4()),
            )
        )

    def _on_knowledge_revision_completed(self, event: KnowledgeRevisionCompletedEvent) -> None:
        proposed = self.knowledge_ledger.history_for(event.revision_id)[0]
        self.knowledge_ledger.append(
            KnowledgeRevision(
                revision_id=event.revision_id,
                status="completed",
                heuristics_considered=event.heuristics_considered,
                started_at=proposed.started_at,
                completed_at=event.timestamp,
                consensus_confidence=event.consensus_confidence,
                knowledge_id=event.knowledge_id,
            )
        )
        self.long_term_knowledge_store.append(
            LongTermKnowledge(
                knowledge_id=event.knowledge_id,
                summary=self.slow_learner.describe(
                    consensus_confidence=event.consensus_confidence,
                    heuristics_considered=event.heuristics_considered,
                ),
                consensus_confidence=event.consensus_confidence,
                heuristics_considered=event.heuristics_considered,
                created_at=event.timestamp,
            )
        )

    def _on_action_succeeded(self, event: ActionSucceededEvent) -> None:
        self._record(
            action_id=event.action_id,
            plan_id=event.plan_id,
            success=True,
            result=event.result,
            delta_attention=-ATTENTION_COST_PER_ACTION,
            delta_capital=-CAPITAL_COST_PER_ACTION,
        )

    def _on_action_failed(self, event: ActionFailedEvent) -> None:
        self._record(
            action_id=event.action_id,
            plan_id=event.plan_id,
            success=False,
            result=event.error,
            delta_attention=0.0,
            delta_capital=0.0,
        )

    def _record(
        self,
        *,
        action_id: str,
        plan_id: str,
        success: bool,
        result: str,
        delta_attention: float,
        delta_capital: float,
    ) -> None:
        outcome = Outcome(
            outcome_id=str(uuid4()), action_id=action_id, plan_id=plan_id, success=success, result=result
        )
        self.outcome_store.append(outcome)
        self._kernel.publish(
            OutcomeRecordedEvent(
                source_component="memory_ledger",
                outcome_id=outcome.outcome_id,
                action_id=action_id,
                plan_id=plan_id,
                success=success,
                result=result,
            )
        )

        status = "succeeded" if success else "failed"
        self.episodic_memory_store.append(
            EpisodicMemoryEntry(
                memory_id=str(uuid4()),
                outcome_id=outcome.outcome_id,
                summary=f"action {action_id} {status}: {result}",
            )
        )

        ledger_entry = LedgerEntry(
            entry_id=str(uuid4()), action_id=action_id, delta_attention=delta_attention, delta_capital=delta_capital
        )
        self.financial_ledger.append(ledger_entry)
        self._kernel.publish(
            LedgerEntryPostedEvent(
                source_component="memory_ledger",
                entry_id=ledger_entry.entry_id,
                action_id=action_id,
                delta_attention=delta_attention,
                delta_capital=delta_capital,
            )
        )


__all__ = [
    "Outcome",
    "EpisodicMemoryEntry",
    "LedgerEntry",
    "Heuristic",
    "PredictionRecord",
    "LearningIteration",
    "OutcomeStore",
    "EpisodicMemoryStore",
    "FinancialLedger",
    "HeuristicStore",
    "PredictionLedger",
    "LearningLedger",
    "MediumLearner",
    "MemoryLedger",
]
