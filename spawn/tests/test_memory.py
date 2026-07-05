import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import (
    ActionFailedEvent,
    ActionSucceededEvent,
    BeliefCreatedEvent,
    Event,
    EventType,
    KnowledgeRevisionCompletedEvent,
    KnowledgeRevisionStartedEvent,
    LearningIterationCompletedEvent,
    LearningIterationStartedEvent,
    OpportunityIdentifiedEvent,
    PlanProposedEvent,
    PredictionRecordedEvent,
    PredictionResolvedEvent,
    ResearchSpendApprovedEvent,
    SensorReliabilityUpdatedEvent,
)
from src.kernel import EventLog, Kernel
from src.memory import (
    EpisodicMemoryEntry,
    EpisodicMemoryStore,
    FastLearner,
    FinancialLedger,
    Heuristic,
    HeuristicStore,
    KnowledgeLedger,
    KnowledgeRevision,
    LearningIteration,
    LearningLedger,
    LedgerEntry,
    LongTermKnowledge,
    LongTermKnowledgeStore,
    MediumLearner,
    MemoryLedger,
    Outcome,
    OutcomeStore,
    PredictionLedger,
    PredictionRecord,
    ResearchSpendLedger,
    ResearchSpendRecord,
    SensorReliabilityLedger,
    SensorReliabilityRecord,
    SlowLearner,
)


class OutcomeModelTests(unittest.TestCase):
    def test_outcome_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        outcome = Outcome(
            outcome_id="outcome-1",
            action_id="action-1",
            plan_id="plan-1",
            success=True,
            result="sent",
            timestamp=now,
        )

        self.assertEqual(outcome.outcome_id, "outcome-1")
        self.assertEqual(outcome.action_id, "action-1")
        self.assertEqual(outcome.plan_id, "plan-1")
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.result, "sent")
        self.assertEqual(outcome.timestamp, now)

    def test_outcome_is_immutable(self) -> None:
        outcome = Outcome(
            outcome_id="outcome-1",
            action_id="action-1",
            plan_id="plan-1",
            success=True,
            result="sent",
            timestamp=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            outcome.success = False  # type: ignore[misc]


class EpisodicMemoryEntryModelTests(unittest.TestCase):
    def test_entry_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        entry = EpisodicMemoryEntry(
            memory_id="memory-1", outcome_id="outcome-1", summary="action-1 succeeded: sent", timestamp=now
        )

        self.assertEqual(entry.memory_id, "memory-1")
        self.assertEqual(entry.outcome_id, "outcome-1")
        self.assertEqual(entry.summary, "action-1 succeeded: sent")
        self.assertEqual(entry.timestamp, now)

    def test_entry_is_immutable(self) -> None:
        entry = EpisodicMemoryEntry(
            memory_id="memory-1",
            outcome_id="outcome-1",
            summary="s",
            timestamp=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            entry.summary = "other"  # type: ignore[misc]


class LedgerEntryModelTests(unittest.TestCase):
    def test_ledger_entry_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        entry = LedgerEntry(
            entry_id="entry-1", action_id="action-1", delta_attention=-1.0, delta_capital=-1.0, timestamp=now
        )

        self.assertEqual(entry.entry_id, "entry-1")
        self.assertEqual(entry.action_id, "action-1")
        self.assertEqual(entry.delta_attention, -1.0)
        self.assertEqual(entry.delta_capital, -1.0)
        self.assertEqual(entry.timestamp, now)

    def test_ledger_entry_is_immutable(self) -> None:
        entry = LedgerEntry(
            entry_id="entry-1",
            action_id="action-1",
            delta_attention=-1.0,
            delta_capital=-1.0,
            timestamp=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            entry.delta_capital = 0.0  # type: ignore[misc]


class HeuristicModelTests(unittest.TestCase):
    def test_heuristic_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        heuristic = Heuristic(
            heuristic_id="heuristic-1", description="prefer high-confidence beliefs", confidence=0.7, created_at=now
        )

        self.assertEqual(heuristic.heuristic_id, "heuristic-1")
        self.assertEqual(heuristic.description, "prefer high-confidence beliefs")
        self.assertEqual(heuristic.confidence, 0.7)
        self.assertEqual(heuristic.created_at, now)

    def test_heuristic_is_immutable(self) -> None:
        heuristic = Heuristic(
            heuristic_id="heuristic-1",
            description="d",
            confidence=0.5,
            created_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            heuristic.confidence = 0.9  # type: ignore[misc]


class OutcomeStoreTests(unittest.TestCase):
    def test_append_and_read_all(self) -> None:
        store = OutcomeStore()
        outcome = Outcome(
            outcome_id="outcome-1",
            action_id="action-1",
            plan_id="plan-1",
            success=True,
            result="sent",
            timestamp=datetime.now(timezone.utc),
        )

        store.append(outcome)

        self.assertEqual(store.read_all(), [outcome])
        self.assertEqual(store.get("outcome-1"), outcome)

    def test_get_raises_for_unknown_outcome(self) -> None:
        store = OutcomeStore()

        with self.assertRaises(KeyError):
            store.get("unknown")

    def test_store_has_no_mutation_methods_other_than_append(self) -> None:
        store = OutcomeStore()

        self.assertFalse(hasattr(store, "update"))
        self.assertFalse(hasattr(store, "remove"))


class EpisodicMemoryStoreTests(unittest.TestCase):
    def test_append_and_read_all(self) -> None:
        store = EpisodicMemoryStore()
        entry = EpisodicMemoryEntry(
            memory_id="memory-1",
            outcome_id="outcome-1",
            summary="s",
            timestamp=datetime.now(timezone.utc),
        )

        store.append(entry)

        self.assertEqual(store.read_all(), [entry])

    def test_store_has_no_mutation_methods_other_than_append(self) -> None:
        store = EpisodicMemoryStore()

        self.assertFalse(hasattr(store, "update"))
        self.assertFalse(hasattr(store, "remove"))


class FinancialLedgerTests(unittest.TestCase):
    def test_append_and_read_all(self) -> None:
        ledger = FinancialLedger()
        entry = LedgerEntry(
            entry_id="entry-1",
            action_id="action-1",
            delta_attention=-1.0,
            delta_capital=-1.0,
            timestamp=datetime.now(timezone.utc),
        )

        ledger.append(entry)

        self.assertEqual(ledger.read_all(), [entry])

    def test_ledger_is_append_only(self) -> None:
        ledger = FinancialLedger()

        self.assertFalse(hasattr(ledger, "update"))
        self.assertFalse(hasattr(ledger, "remove"))
        self.assertFalse(hasattr(ledger, "clear"))

    def test_read_all_returns_a_copy(self) -> None:
        ledger = FinancialLedger()
        entry = LedgerEntry(
            entry_id="entry-1",
            action_id="action-1",
            delta_attention=-1.0,
            delta_capital=-1.0,
            timestamp=datetime.now(timezone.utc),
        )
        ledger.append(entry)

        snapshot = ledger.read_all()
        snapshot.append(entry)

        self.assertEqual(len(ledger.read_all()), 1)


class HeuristicStoreTests(unittest.TestCase):
    def test_append_and_read_all(self) -> None:
        store = HeuristicStore()
        heuristic = Heuristic(
            heuristic_id="heuristic-1", description="d", confidence=0.5, created_at=datetime.now(timezone.utc)
        )

        store.append(heuristic)

        self.assertEqual(store.read_all(), [heuristic])

    def test_store_has_no_mutation_methods_other_than_append(self) -> None:
        store = HeuristicStore()

        self.assertFalse(hasattr(store, "update"))
        self.assertFalse(hasattr(store, "remove"))


def publish_action_succeeded(
    kernel: Kernel, *, action_id: str = "action-1", plan_id: str = "plan-1", result: str = "sent"
) -> None:
    kernel.publish(
        ActionSucceededEvent(source_component="executor", action_id=action_id, plan_id=plan_id, result=result)
    )


def publish_action_failed(
    kernel: Kernel, *, action_id: str = "action-1", plan_id: str = "plan-1", error: str = "timeout"
) -> None:
    kernel.publish(ActionFailedEvent(source_component="executor", action_id=action_id, plan_id=plan_id, error=error))


def publish_plan_proposed(
    kernel: Kernel,
    *,
    plan_id: str = "plan-1",
    opportunity_id: str = "opportunity-1",
    expected_value: float = 60.0,
    attention_cost: float = 1.0,
    capital_cost: float = 6.0,
    ordered_actions: tuple[str, ...] = ("investigate:opportunity-1", "act_on:opportunity-1"),
) -> None:
    kernel.publish(
        PlanProposedEvent(
            source_component="executive",
            plan_id=plan_id,
            opportunity_id=opportunity_id,
            rationale="test plan",
            expected_value=expected_value,
            attention_cost=attention_cost,
            capital_cost=capital_cost,
            ordered_actions=ordered_actions,
        )
    )


class MemoryLedgerSuccessTests(unittest.TestCase):
    def test_action_succeeded_creates_outcome_episodic_entry_and_ledger_entry(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        outcome_recorded: list[Event] = []
        ledger_posted: list[Event] = []
        kernel.register_subscriber(EventType.OUTCOME_RECORDED, outcome_recorded.append)
        kernel.register_subscriber(EventType.LEDGER_ENTRY_POSTED, ledger_posted.append)

        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1", result="sent")

        outcomes = memory_ledger.outcome_store.read_all()
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertEqual(outcome.action_id, "action-1")
        self.assertEqual(outcome.plan_id, "plan-1")
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.result, "sent")

        self.assertEqual(len(outcome_recorded), 1)
        self.assertEqual(outcome_recorded[0].outcome_id, outcome.outcome_id)
        self.assertTrue(outcome_recorded[0].success)

        entries = memory_ledger.episodic_memory_store.read_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].outcome_id, outcome.outcome_id)

        ledger_entries = memory_ledger.financial_ledger.read_all()
        self.assertEqual(len(ledger_entries), 1)
        self.assertEqual(ledger_entries[0].action_id, "action-1")

        self.assertEqual(len(ledger_posted), 1)
        self.assertEqual(ledger_posted[0].action_id, "action-1")
        self.assertEqual(ledger_posted[0].delta_attention, ledger_entries[0].delta_attention)
        self.assertEqual(ledger_posted[0].delta_capital, ledger_entries[0].delta_capital)


class MemoryLedgerFailureTests(unittest.TestCase):
    def test_action_failed_creates_outcome_episodic_entry_and_ledger_entry(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        outcome_recorded: list[Event] = []
        ledger_posted: list[Event] = []
        kernel.register_subscriber(EventType.OUTCOME_RECORDED, outcome_recorded.append)
        kernel.register_subscriber(EventType.LEDGER_ENTRY_POSTED, ledger_posted.append)

        publish_action_failed(kernel, action_id="action-1", plan_id="plan-1", error="timeout")

        outcomes = memory_ledger.outcome_store.read_all()
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertFalse(outcome.success)
        self.assertEqual(outcome.result, "timeout")

        self.assertEqual(len(outcome_recorded), 1)
        self.assertFalse(outcome_recorded[0].success)

        entries = memory_ledger.episodic_memory_store.read_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].outcome_id, outcome.outcome_id)

        ledger_entries = memory_ledger.financial_ledger.read_all()
        self.assertEqual(len(ledger_entries), 1)

        self.assertEqual(len(ledger_posted), 1)


class MemoryLedgerAppendOnlyTests(unittest.TestCase):
    def test_multiple_outcomes_accumulate_without_overwriting(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")
        publish_action_failed(kernel, action_id="action-2", plan_id="plan-1")

        self.assertEqual(len(memory_ledger.outcome_store.read_all()), 2)
        self.assertEqual(len(memory_ledger.episodic_memory_store.read_all()), 2)
        self.assertEqual(len(memory_ledger.financial_ledger.read_all()), 2)


class MemoryLedgerScopeBoundaryTests(unittest.TestCase):
    def test_memory_ledger_does_not_implement_learning_or_calibration(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        self.assertFalse(hasattr(memory_ledger, "distill_playbook"))
        self.assertFalse(hasattr(memory_ledger, "score_prediction"))
        self.assertFalse(hasattr(memory_ledger, "calibrate"))


class PredictionRecordModelTests(unittest.TestCase):
    def test_prediction_record_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        record = PredictionRecord(
            prediction_id="prediction-1",
            plan_id="plan-1",
            predicted_value=60.0,
            status="pending",
            created_at=now,
        )

        self.assertEqual(record.prediction_id, "prediction-1")
        self.assertEqual(record.plan_id, "plan-1")
        self.assertEqual(record.predicted_value, 60.0)
        self.assertEqual(record.status, "pending")
        self.assertEqual(record.created_at, now)
        self.assertIsNone(record.outcome_id)
        self.assertIsNone(record.actual_value)
        self.assertIsNone(record.prediction_error)
        self.assertIsNone(record.resolved_at)

    def test_prediction_record_is_immutable(self) -> None:
        record = PredictionRecord(
            prediction_id="prediction-1",
            plan_id="plan-1",
            predicted_value=60.0,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.status = "resolved"  # type: ignore[misc]


class PredictionLedgerTests(unittest.TestCase):
    def test_append_read_all_and_history_for(self) -> None:
        ledger = PredictionLedger()
        pending = PredictionRecord(
            prediction_id="prediction-1",
            plan_id="plan-1",
            predicted_value=60.0,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        resolved = PredictionRecord(
            prediction_id="prediction-1",
            plan_id="plan-1",
            predicted_value=60.0,
            status="resolved",
            created_at=pending.created_at,
            outcome_id="outcome-1",
            actual_value=60.0,
            prediction_error=0.0,
            resolved_at=datetime.now(timezone.utc),
        )

        ledger.append(pending)
        ledger.append(resolved)

        self.assertEqual(ledger.read_all(), [pending, resolved])
        self.assertEqual(ledger.history_for("prediction-1"), [pending, resolved])
        self.assertEqual(ledger.history_for("no-such-prediction"), [])

    def test_ledger_has_no_mutation_methods_other_than_append(self) -> None:
        ledger = PredictionLedger()

        self.assertFalse(hasattr(ledger, "update"))
        self.assertFalse(hasattr(ledger, "remove"))
        self.assertFalse(hasattr(ledger, "clear"))


class MemoryLedgerPredictionRecordingTests(unittest.TestCase):
    def test_plan_proposed_records_exactly_one_prediction(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        recorded: list[Event] = []
        kernel.register_subscriber(EventType.PREDICTION_RECORDED, recorded.append)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)

        self.assertEqual(len(recorded), 1)
        self.assertIsInstance(recorded[0], PredictionRecordedEvent)
        self.assertEqual(recorded[0].plan_id, "plan-1")
        self.assertEqual(recorded[0].predicted_value, 60.0)

        records = memory_ledger.prediction_ledger.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "pending")
        self.assertEqual(records[0].plan_id, "plan-1")
        self.assertEqual(records[0].predicted_value, 60.0)

    def test_unresolved_prediction_remains_pending(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)

        records = memory_ledger.prediction_ledger.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "pending")
        self.assertIsNone(records[0].actual_value)
        self.assertIsNone(records[0].prediction_error)
        self.assertIsNone(records[0].resolved_at)


class MemoryLedgerPredictionResolutionTests(unittest.TestCase):
    def test_matching_success_outcome_resolves_prediction_with_zero_error(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        resolved: list[Event] = []
        kernel.register_subscriber(EventType.PREDICTION_RESOLVED, resolved.append)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1", result="sent")

        self.assertEqual(len(resolved), 1)
        self.assertIsInstance(resolved[0], PredictionResolvedEvent)
        self.assertEqual(resolved[0].predicted_value, 60.0)
        self.assertEqual(resolved[0].actual_value, 60.0)
        self.assertEqual(resolved[0].prediction_error, 0.0)

        history = memory_ledger.prediction_ledger.history_for(resolved[0].prediction_id)
        self.assertEqual([record.status for record in history], ["pending", "resolved"])
        self.assertEqual(history[-1].outcome_id, resolved[0].outcome_id)
        self.assertEqual(history[-1].actual_value, 60.0)
        self.assertEqual(history[-1].prediction_error, 0.0)
        self.assertIsNotNone(history[-1].resolved_at)
        self.assertEqual(history[-1].predicted_value, 60.0)
        self.assertEqual(history[-1].created_at, history[0].created_at)

    def test_matching_failure_outcome_resolves_prediction_with_full_error(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_failed(kernel, action_id="action-1", plan_id="plan-1", error="timeout")

        history = memory_ledger.prediction_ledger.history_for(
            memory_ledger.prediction_ledger.read_all()[0].prediction_id
        )
        resolved_record = history[-1]
        self.assertEqual(resolved_record.status, "resolved")
        self.assertEqual(resolved_record.actual_value, 0.0)
        self.assertEqual(resolved_record.prediction_error, -60.0)

    def test_prediction_error_is_computed_deterministically(self) -> None:
        for expected_value, success, expected_error in (
            (100.0, True, 0.0),
            (100.0, False, -100.0),
            (25.0, True, 0.0),
            (25.0, False, -25.0),
        ):
            with self.subTest(expected_value=expected_value, success=success):
                kernel = Kernel()
                memory_ledger = MemoryLedger(kernel)
                publish_plan_proposed(kernel, plan_id="plan-1", expected_value=expected_value)
                if success:
                    publish_action_succeeded(kernel, plan_id="plan-1")
                else:
                    publish_action_failed(kernel, plan_id="plan-1")

                resolved_record = memory_ledger.prediction_ledger.read_all()[-1]
                self.assertEqual(resolved_record.prediction_error, expected_error)

    def test_second_outcome_for_same_plan_does_not_double_resolve(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        resolved: list[Event] = []
        kernel.register_subscriber(EventType.PREDICTION_RESOLVED, resolved.append)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")
        publish_action_succeeded(kernel, action_id="action-2", plan_id="plan-1")

        self.assertEqual(len(resolved), 1)
        records = memory_ledger.prediction_ledger.read_all()
        self.assertEqual(len(records), 2)  # pending + resolved, never a third
        self.assertEqual([record.status for record in records], ["pending", "resolved"])

    def test_outcome_for_a_plan_with_no_prediction_is_ignored(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        resolved: list[Event] = []
        kernel.register_subscriber(EventType.PREDICTION_RESOLVED, resolved.append)

        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-without-a-prediction")

        self.assertEqual(resolved, [])
        self.assertEqual(memory_ledger.prediction_ledger.read_all(), [])


class MemoryLedgerPredictionReplayTests(unittest.TestCase):
    def test_replay_reconstructs_prediction_history(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        memory_ledger = MemoryLedger(kernel)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")
        publish_plan_proposed(kernel, plan_id="plan-2", expected_value=40.0)
        publish_action_failed(kernel, action_id="action-2", plan_id="plan-2")
        publish_plan_proposed(kernel, plan_id="plan-3", expected_value=10.0)  # never resolved

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_memory_ledger.prediction_ledger.read_all(), memory_ledger.prediction_ledger.read_all()
        )

        plan1_history = rebuilt_memory_ledger.prediction_ledger.history_for(
            [r for r in rebuilt_memory_ledger.prediction_ledger.read_all() if r.plan_id == "plan-1"][0].prediction_id
        )
        self.assertEqual([r.status for r in plan1_history], ["pending", "resolved"])
        self.assertEqual(plan1_history[-1].actual_value, 60.0)

        plan2_history = rebuilt_memory_ledger.prediction_ledger.history_for(
            [r for r in rebuilt_memory_ledger.prediction_ledger.read_all() if r.plan_id == "plan-2"][0].prediction_id
        )
        self.assertEqual([r.status for r in plan2_history], ["pending", "resolved"])
        self.assertEqual(plan2_history[-1].actual_value, 0.0)

        plan3_history = rebuilt_memory_ledger.prediction_ledger.history_for(
            [r for r in rebuilt_memory_ledger.prediction_ledger.read_all() if r.plan_id == "plan-3"][0].prediction_id
        )
        self.assertEqual([r.status for r in plan3_history], ["pending"])
        self.assertIn("plan-3", rebuilt_memory_ledger._pending_predictions)


class MemoryLedgerPredictionSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_prediction_history(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")
        publish_plan_proposed(kernel, plan_id="plan-2", expected_value=40.0)  # left pending
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored = rebuilt_memory_ledger.prediction_ledger.read_all()
        self.assertEqual(len(restored), 3)  # plan-1 pending+resolved, plan-2 pending

        plan1_records = [r for r in restored if r.plan_id == "plan-1"]
        self.assertEqual([r.status for r in plan1_records], ["pending", "resolved"])
        self.assertEqual(plan1_records[-1].actual_value, 60.0)
        self.assertEqual(plan1_records[-1].prediction_error, 0.0)

        plan2_records = [r for r in restored if r.plan_id == "plan-2"]
        self.assertEqual([r.status for r in plan2_records], ["pending"])
        self.assertIn("plan-2", rebuilt_memory_ledger._pending_predictions)
        self.assertNotIn("plan-1", rebuilt_memory_ledger._pending_predictions)


class LearningIterationModelTests(unittest.TestCase):
    def test_learning_iteration_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        record = LearningIteration(
            iteration_id="iteration-1",
            status="started",
            predictions_considered=3,
            started_at=now,
        )

        self.assertEqual(record.iteration_id, "iteration-1")
        self.assertEqual(record.status, "started")
        self.assertEqual(record.predictions_considered, 3)
        self.assertEqual(record.started_at, now)
        self.assertIsNone(record.completed_at)
        self.assertIsNone(record.mean_prediction_error)
        self.assertIsNone(record.heuristic_id)

    def test_learning_iteration_is_immutable(self) -> None:
        record = LearningIteration(
            iteration_id="iteration-1",
            status="started",
            predictions_considered=1,
            started_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.status = "completed"  # type: ignore[misc]


class LearningLedgerTests(unittest.TestCase):
    def test_append_read_all_and_history_for(self) -> None:
        ledger = LearningLedger()
        started = LearningIteration(
            iteration_id="iteration-1", status="started", predictions_considered=2,
            started_at=datetime.now(timezone.utc),
        )
        completed = LearningIteration(
            iteration_id="iteration-1", status="completed", predictions_considered=2,
            started_at=started.started_at, completed_at=datetime.now(timezone.utc),
            mean_prediction_error=-5.0, heuristic_id="heuristic-1",
        )

        ledger.append(started)
        ledger.append(completed)

        self.assertEqual(ledger.read_all(), [started, completed])
        self.assertEqual(ledger.history_for("iteration-1"), [started, completed])
        self.assertEqual(ledger.history_for("no-such-iteration"), [])

    def test_ledger_has_no_mutation_methods_other_than_append(self) -> None:
        ledger = LearningLedger()

        self.assertFalse(hasattr(ledger, "update"))
        self.assertFalse(hasattr(ledger, "remove"))
        self.assertFalse(hasattr(ledger, "clear"))


def _prediction_record(*, predicted_value: float, actual_value: float, plan_id: str = "plan-1") -> PredictionRecord:
    return PredictionRecord(
        prediction_id=f"prediction-{plan_id}",
        plan_id=plan_id,
        predicted_value=predicted_value,
        status="resolved",
        created_at=datetime.now(timezone.utc),
        outcome_id=f"outcome-{plan_id}",
        actual_value=actual_value,
        prediction_error=actual_value - predicted_value,
        resolved_at=datetime.now(timezone.utc),
    )


class MediumLearnerTests(unittest.TestCase):
    def test_compute_mean_error_over_resolved_predictions(self) -> None:
        learner = MediumLearner()
        predictions = [
            _prediction_record(predicted_value=100.0, actual_value=100.0, plan_id="a"),
            _prediction_record(predicted_value=100.0, actual_value=0.0, plan_id="b"),
        ]

        self.assertEqual(learner.compute_mean_error(predictions), -50.0)

    def test_compute_mean_error_with_no_predictions_is_zero(self) -> None:
        learner = MediumLearner()

        self.assertEqual(learner.compute_mean_error([]), 0.0)

    def test_compute_mean_error_is_deterministic_for_identical_history(self) -> None:
        learner = MediumLearner()
        history_a = [
            _prediction_record(predicted_value=60.0, actual_value=60.0, plan_id="a"),
            _prediction_record(predicted_value=40.0, actual_value=0.0, plan_id="b"),
        ]
        history_b = [
            _prediction_record(predicted_value=60.0, actual_value=60.0, plan_id="a"),
            _prediction_record(predicted_value=40.0, actual_value=0.0, plan_id="b"),
        ]

        self.assertEqual(learner.compute_mean_error(history_a), learner.compute_mean_error(history_b))

    def test_compute_confidence_grows_with_more_predictions_and_stays_below_one(self) -> None:
        learner = MediumLearner()

        low = learner.compute_confidence(1)
        high = learner.compute_confidence(100)

        self.assertLess(low, high)
        self.assertLess(high, 1.0)
        self.assertEqual(learner.compute_confidence(0), 0.0)

    def test_describe_is_deterministic(self) -> None:
        learner = MediumLearner()

        first = learner.describe(mean_prediction_error=-12.5, predictions_considered=4)
        second = learner.describe(mean_prediction_error=-12.5, predictions_considered=4)

        self.assertEqual(first, second)
        self.assertIn("4", first)


class MemoryLedgerLearningIntegrationTests(unittest.TestCase):
    def test_resolved_prediction_triggers_a_learning_iteration(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        started: list[Event] = []
        completed: list[Event] = []
        kernel.register_subscriber(EventType.LEARNING_ITERATION_STARTED, started.append)
        kernel.register_subscriber(EventType.LEARNING_ITERATION_COMPLETED, completed.append)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")

        self.assertEqual(len(started), 1)
        self.assertIsInstance(started[0], LearningIterationStartedEvent)
        self.assertEqual(started[0].predictions_considered, 1)

        self.assertEqual(len(completed), 1)
        self.assertIsInstance(completed[0], LearningIterationCompletedEvent)
        self.assertEqual(completed[0].iteration_id, started[0].iteration_id)
        self.assertEqual(completed[0].mean_prediction_error, 0.0)

        history = memory_ledger.learning_ledger.history_for(started[0].iteration_id)
        self.assertEqual([record.status for record in history], ["started", "completed"])

        heuristics = memory_ledger.heuristic_store.read_all()
        self.assertEqual(len(heuristics), 1)
        self.assertEqual(heuristics[0].heuristic_id, completed[0].heuristic_id)

    def test_learning_iterations_are_append_only_and_history_preserved_across_iterations(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")
        publish_plan_proposed(kernel, plan_id="plan-2", expected_value=40.0)
        publish_action_failed(kernel, action_id="action-2", plan_id="plan-2")

        records = memory_ledger.learning_ledger.read_all()
        self.assertEqual(len(records), 4)  # started+completed, twice
        iteration_ids = {record.iteration_id for record in records}
        self.assertEqual(len(iteration_ids), 2)

        for iteration_id in iteration_ids:
            history = memory_ledger.learning_ledger.history_for(iteration_id)
            self.assertEqual([record.status for record in history], ["started", "completed"])

        # Second iteration considered both resolved predictions by then.
        second_iteration = sorted(records, key=lambda r: r.started_at)[-1]
        self.assertEqual(
            memory_ledger.learning_ledger.history_for(second_iteration.iteration_id)[-1].predictions_considered, 2
        )

        heuristics = memory_ledger.heuristic_store.read_all()
        self.assertEqual(len(heuristics), 2)

    def test_identical_prediction_histories_produce_identical_heuristic_updates(self) -> None:
        def run_cycle() -> MemoryLedger:
            kernel = Kernel()
            memory_ledger = MemoryLedger(kernel)
            publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
            publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")
            publish_plan_proposed(kernel, plan_id="plan-2", expected_value=40.0)
            publish_action_failed(kernel, action_id="action-2", plan_id="plan-2")
            return memory_ledger

        first = run_cycle()
        second = run_cycle()

        first_heuristics = first.heuristic_store.read_all()
        second_heuristics = second.heuristic_store.read_all()
        self.assertEqual(len(first_heuristics), len(second_heuristics))
        for a, b in zip(first_heuristics, second_heuristics):
            self.assertEqual(a.description, b.description)
            self.assertEqual(a.confidence, b.confidence)

        first_errors = [record.mean_prediction_error for record in first.learning_ledger.read_all() if record.status == "completed"]
        second_errors = [record.mean_prediction_error for record in second.learning_ledger.read_all() if record.status == "completed"]
        self.assertEqual(first_errors, second_errors)


class MemoryLedgerLearningReplayTests(unittest.TestCase):
    def test_replay_reconstructs_learning_history(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        memory_ledger = MemoryLedger(kernel)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")
        publish_plan_proposed(kernel, plan_id="plan-2", expected_value=40.0)
        publish_action_failed(kernel, action_id="action-2", plan_id="plan-2")

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_memory_ledger.learning_ledger.read_all(), memory_ledger.learning_ledger.read_all()
        )
        self.assertEqual(
            rebuilt_memory_ledger.heuristic_store.read_all(), memory_ledger.heuristic_store.read_all()
        )


class MemoryLedgerLearningSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_learning_history(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_plan_proposed(kernel, plan_id="plan-1", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-1", plan_id="plan-1")
        publish_plan_proposed(kernel, plan_id="plan-2", expected_value=40.0)
        publish_action_failed(kernel, action_id="action-2", plan_id="plan-2")
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored_learning = rebuilt_memory_ledger.learning_ledger.read_all()
        self.assertEqual(len(restored_learning), 4)
        self.assertEqual(restored_learning, memory_ledger.learning_ledger.read_all())

        restored_heuristics = rebuilt_memory_ledger.heuristic_store.read_all()
        self.assertEqual(len(restored_heuristics), 2)
        self.assertEqual(restored_heuristics, memory_ledger.heuristic_store.read_all())


class KnowledgeRevisionModelTests(unittest.TestCase):
    def test_knowledge_revision_carries_required_fields(self) -> None:
        record = KnowledgeRevision(
            revision_id="revision-1",
            status="started",
            heuristics_considered=3,
            started_at=datetime.now(timezone.utc),
        )

        self.assertEqual(record.revision_id, "revision-1")
        self.assertEqual(record.status, "started")
        self.assertEqual(record.heuristics_considered, 3)
        self.assertIsNone(record.completed_at)
        self.assertIsNone(record.consensus_confidence)
        self.assertIsNone(record.knowledge_id)

    def test_knowledge_revision_is_immutable(self) -> None:
        record = KnowledgeRevision(
            revision_id="revision-1",
            status="started",
            heuristics_considered=3,
            started_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.status = "completed"  # type: ignore[misc]


class KnowledgeLedgerTests(unittest.TestCase):
    def test_append_read_all_and_history_for(self) -> None:
        ledger = KnowledgeLedger()
        started = KnowledgeRevision(
            revision_id="revision-1", status="started", heuristics_considered=3,
            started_at=datetime.now(timezone.utc),
        )
        completed = KnowledgeRevision(
            revision_id="revision-1", status="completed", heuristics_considered=3,
            started_at=started.started_at, completed_at=datetime.now(timezone.utc),
            consensus_confidence=0.5, knowledge_id="knowledge-1",
        )

        ledger.append(started)
        ledger.append(completed)

        self.assertEqual(ledger.read_all(), [started, completed])
        self.assertEqual(ledger.history_for("revision-1"), [started, completed])
        self.assertEqual(ledger.history_for("no-such-revision"), [])

    def test_ledger_has_no_mutation_methods_other_than_append(self) -> None:
        ledger = KnowledgeLedger()

        self.assertFalse(hasattr(ledger, "update"))
        self.assertFalse(hasattr(ledger, "remove"))
        self.assertFalse(hasattr(ledger, "clear"))


def _heuristic(*, confidence: float, heuristic_id: str = "heuristic-1") -> Heuristic:
    return Heuristic(
        heuristic_id=heuristic_id,
        description="calibration: mean prediction error 0.000000 over 1 resolved predictions",
        confidence=confidence,
        created_at=datetime.now(timezone.utc),
    )


class SlowLearnerTests(unittest.TestCase):
    def test_should_consolidate_only_on_interval_boundaries(self) -> None:
        learner = SlowLearner()

        self.assertFalse(learner.should_consolidate(0))
        self.assertFalse(learner.should_consolidate(1))
        self.assertFalse(learner.should_consolidate(2))
        self.assertTrue(learner.should_consolidate(3))
        self.assertFalse(learner.should_consolidate(4))
        self.assertTrue(learner.should_consolidate(6))

    def test_compute_consensus_confidence_over_heuristics(self) -> None:
        learner = SlowLearner()
        heuristics = [
            _heuristic(confidence=0.2, heuristic_id="heuristic-1"),
            _heuristic(confidence=0.4, heuristic_id="heuristic-2"),
        ]

        self.assertAlmostEqual(learner.compute_consensus_confidence(heuristics), 0.3)

    def test_compute_consensus_confidence_with_no_heuristics_is_zero(self) -> None:
        learner = SlowLearner()

        self.assertEqual(learner.compute_consensus_confidence([]), 0.0)

    def test_compute_consensus_confidence_is_deterministic_for_identical_history(self) -> None:
        learner = SlowLearner()
        history_a = [_heuristic(confidence=0.2, heuristic_id="a"), _heuristic(confidence=0.6, heuristic_id="b")]
        history_b = [_heuristic(confidence=0.2, heuristic_id="a"), _heuristic(confidence=0.6, heuristic_id="b")]

        self.assertEqual(
            learner.compute_consensus_confidence(history_a), learner.compute_consensus_confidence(history_b)
        )

    def test_describe_is_deterministic(self) -> None:
        learner = SlowLearner()

        first = learner.describe(consensus_confidence=0.42, heuristics_considered=3)
        second = learner.describe(consensus_confidence=0.42, heuristics_considered=3)

        self.assertEqual(first, second)
        self.assertIn("3", first)

    def test_classify_negative_mean_error_is_anti_pattern(self) -> None:
        learner = SlowLearner()

        self.assertEqual(learner.classify(-4.5), "anti_pattern")

    def test_classify_zero_mean_error_is_playbook(self) -> None:
        learner = SlowLearner()

        self.assertEqual(learner.classify(0.0), "playbook")


class MemoryLedgerSlowLearningIntegrationTests(unittest.TestCase):
    def _run_cycles(self, kernel: Kernel, count: int) -> None:
        for i in range(count):
            publish_plan_proposed(kernel, plan_id=f"plan-{i}", expected_value=60.0)
            publish_action_succeeded(kernel, action_id=f"action-{i}", plan_id=f"plan-{i}")

    def test_consolidation_triggers_after_interval_completed_medium_learning_iterations(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        started: list[Event] = []
        completed: list[Event] = []
        kernel.register_subscriber(EventType.KNOWLEDGE_REVISION_STARTED, started.append)
        kernel.register_subscriber(EventType.KNOWLEDGE_REVISION_COMPLETED, completed.append)

        self._run_cycles(kernel, SlowLearner.CONSOLIDATION_INTERVAL)

        self.assertEqual(len(started), 1)
        self.assertIsInstance(started[0], KnowledgeRevisionStartedEvent)
        self.assertEqual(started[0].heuristics_considered, SlowLearner.CONSOLIDATION_INTERVAL)

        self.assertEqual(len(completed), 1)
        self.assertIsInstance(completed[0], KnowledgeRevisionCompletedEvent)
        self.assertEqual(completed[0].revision_id, started[0].revision_id)

        history = memory_ledger.knowledge_ledger.history_for(started[0].revision_id)
        self.assertEqual([record.status for record in history], ["started", "completed"])

        knowledge = memory_ledger.long_term_knowledge_store.read_all()
        self.assertEqual(len(knowledge), 1)
        self.assertEqual(knowledge[0].knowledge_id, completed[0].knowledge_id)
        # Every action in _run_cycles succeeds, so mean_prediction_error is
        # always 0.0 and the distilled knowledge classifies as a playbook.
        self.assertEqual(completed[0].knowledge_type, "playbook")
        self.assertEqual(knowledge[0].knowledge_type, "playbook")
        self.assertEqual(knowledge[0].summary, completed[0].summary)

    def test_revisions_are_append_only_and_multiple_revisions_preserve_history(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        self._run_cycles(kernel, SlowLearner.CONSOLIDATION_INTERVAL * 2)

        records = memory_ledger.knowledge_ledger.read_all()
        self.assertEqual(len(records), 4)  # started+completed, twice
        revision_ids = {record.revision_id for record in records}
        self.assertEqual(len(revision_ids), 2)

        for revision_id in revision_ids:
            history = memory_ledger.knowledge_ledger.history_for(revision_id)
            self.assertEqual([record.status for record in history], ["started", "completed"])

        knowledge = memory_ledger.long_term_knowledge_store.read_all()
        self.assertEqual(len(knowledge), 2)

    def test_identical_heuristic_histories_produce_identical_knowledge_revisions(self) -> None:
        def run_cycle() -> MemoryLedger:
            kernel = Kernel()
            memory_ledger = MemoryLedger(kernel)
            self._run_cycles(kernel, SlowLearner.CONSOLIDATION_INTERVAL)
            return memory_ledger

        first = run_cycle()
        second = run_cycle()

        first_knowledge = first.long_term_knowledge_store.read_all()
        second_knowledge = second.long_term_knowledge_store.read_all()
        self.assertEqual(len(first_knowledge), len(second_knowledge))
        for a, b in zip(first_knowledge, second_knowledge):
            self.assertEqual(a.summary, b.summary)
            self.assertEqual(a.consensus_confidence, b.consensus_confidence)

        first_confidences = [
            record.consensus_confidence
            for record in first.knowledge_ledger.read_all()
            if record.status == "completed"
        ]
        second_confidences = [
            record.consensus_confidence
            for record in second.knowledge_ledger.read_all()
            if record.status == "completed"
        ]
        self.assertEqual(first_confidences, second_confidences)


class MemoryLedgerSlowLearningReplayTests(unittest.TestCase):
    def test_replay_reconstructs_long_term_knowledge(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        memory_ledger = MemoryLedger(kernel)

        for i in range(SlowLearner.CONSOLIDATION_INTERVAL):
            publish_plan_proposed(kernel, plan_id=f"plan-{i}", expected_value=60.0)
            publish_action_succeeded(kernel, action_id=f"action-{i}", plan_id=f"plan-{i}")

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_memory_ledger.knowledge_ledger.read_all(), memory_ledger.knowledge_ledger.read_all()
        )
        self.assertEqual(
            rebuilt_memory_ledger.long_term_knowledge_store.read_all(),
            memory_ledger.long_term_knowledge_store.read_all(),
        )


class MemoryLedgerSlowLearningSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_long_term_knowledge(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        for i in range(SlowLearner.CONSOLIDATION_INTERVAL):
            publish_plan_proposed(kernel, plan_id=f"plan-{i}", expected_value=60.0)
            publish_action_succeeded(kernel, action_id=f"action-{i}", plan_id=f"plan-{i}")
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored_knowledge_revisions = rebuilt_memory_ledger.knowledge_ledger.read_all()
        self.assertEqual(len(restored_knowledge_revisions), 2)
        self.assertEqual(restored_knowledge_revisions, memory_ledger.knowledge_ledger.read_all())

        restored_knowledge = rebuilt_memory_ledger.long_term_knowledge_store.read_all()
        self.assertEqual(len(restored_knowledge), 1)
        self.assertEqual(restored_knowledge, memory_ledger.long_term_knowledge_store.read_all())


class SensorReliabilityRecordModelTests(unittest.TestCase):
    def test_record_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        record = SensorReliabilityRecord(
            sensor_id="sensor-1", reliability=0.8, predictions_considered=5, updated_at=now
        )

        self.assertEqual(record.sensor_id, "sensor-1")
        self.assertEqual(record.reliability, 0.8)
        self.assertEqual(record.predictions_considered, 5)
        self.assertEqual(record.updated_at, now)

    def test_record_is_immutable(self) -> None:
        record = SensorReliabilityRecord(
            sensor_id="sensor-1", reliability=0.8, predictions_considered=5, updated_at=datetime.now(timezone.utc)
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.reliability = 0.5  # type: ignore[misc]


class SensorReliabilityLedgerTests(unittest.TestCase):
    def test_append_read_all_history_for_and_latest_for(self) -> None:
        ledger = SensorReliabilityLedger()
        first = SensorReliabilityRecord(
            sensor_id="sensor-1", reliability=1.0, predictions_considered=1, updated_at=datetime.now(timezone.utc)
        )
        second = SensorReliabilityRecord(
            sensor_id="sensor-1", reliability=0.5, predictions_considered=2, updated_at=datetime.now(timezone.utc)
        )

        ledger.append(first)
        ledger.append(second)

        self.assertEqual(ledger.read_all(), [first, second])
        self.assertEqual(ledger.history_for("sensor-1"), [first, second])
        self.assertEqual(ledger.history_for("no-such-sensor"), [])
        self.assertEqual(ledger.latest_for("sensor-1"), second)
        self.assertIsNone(ledger.latest_for("no-such-sensor"))

    def test_ledger_has_no_mutation_methods_other_than_append(self) -> None:
        ledger = SensorReliabilityLedger()

        self.assertFalse(hasattr(ledger, "update"))
        self.assertFalse(hasattr(ledger, "remove"))
        self.assertFalse(hasattr(ledger, "clear"))


class FastLearnerTests(unittest.TestCase):
    def test_compute_reliability_is_the_success_rate(self) -> None:
        learner = FastLearner()
        predictions = [
            _prediction_record(predicted_value=100.0, actual_value=100.0, plan_id="a"),
            _prediction_record(predicted_value=100.0, actual_value=0.0, plan_id="b"),
            _prediction_record(predicted_value=50.0, actual_value=50.0, plan_id="c"),
        ]

        self.assertAlmostEqual(learner.compute_reliability(predictions), 2 / 3)

    def test_compute_reliability_with_no_history_is_the_neutral_default(self) -> None:
        learner = FastLearner()

        self.assertEqual(learner.compute_reliability([]), FastLearner.DEFAULT_RELIABILITY)

    def test_compute_reliability_is_deterministic_for_identical_history(self) -> None:
        learner = FastLearner()
        history_a = [
            _prediction_record(predicted_value=60.0, actual_value=60.0, plan_id="a"),
            _prediction_record(predicted_value=40.0, actual_value=0.0, plan_id="b"),
        ]
        history_b = [
            _prediction_record(predicted_value=60.0, actual_value=60.0, plan_id="a"),
            _prediction_record(predicted_value=40.0, actual_value=0.0, plan_id="b"),
        ]

        self.assertEqual(learner.compute_reliability(history_a), learner.compute_reliability(history_b))


def publish_belief_created(kernel: Kernel, *, belief_id: str, sensor_id: str, confidence: float = 0.6) -> None:
    kernel.publish(
        BeliefCreatedEvent(
            source_component="world_model",
            belief_id=belief_id,
            claim="claim",
            confidence=confidence,
            provenance=sensor_id,
        )
    )


def publish_opportunity_identified(
    kernel: Kernel, *, opportunity_id: str, belief_ids: tuple[str, ...], confidence: float = 0.6
) -> None:
    kernel.publish(
        OpportunityIdentifiedEvent(
            source_component="executive",
            opportunity_id=opportunity_id,
            belief_ids=belief_ids,
            confidence=confidence,
        )
    )


def _resolve_one_prediction(
    kernel: Kernel,
    *,
    sensor_id: str,
    belief_id: str = "belief-1",
    opportunity_id: str = "opportunity-1",
    plan_id: str = "plan-1",
    success: bool = True,
    expected_value: float = 60.0,
) -> None:
    """Drive one belief -> opportunity -> plan -> outcome cascade for a single
    sensor, entirely through published events — the same sanctioned path
    MemoryLedger uses to attribute a resolved prediction back to its sensor.
    """
    publish_belief_created(kernel, belief_id=belief_id, sensor_id=sensor_id)
    publish_opportunity_identified(kernel, opportunity_id=opportunity_id, belief_ids=(belief_id,))
    publish_plan_proposed(kernel, plan_id=plan_id, opportunity_id=opportunity_id, expected_value=expected_value)
    if success:
        publish_action_succeeded(kernel, action_id=f"action-{plan_id}", plan_id=plan_id)
    else:
        publish_action_failed(kernel, action_id=f"action-{plan_id}", plan_id=plan_id)


class MemoryLedgerFastLearningIntegrationTests(unittest.TestCase):
    def test_resolved_prediction_triggers_a_sensor_reliability_update(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)
        updated: list[Event] = []
        kernel.register_subscriber(EventType.SENSOR_RELIABILITY_UPDATED, updated.append)

        _resolve_one_prediction(kernel, sensor_id="sensor-a", success=True)

        self.assertEqual(len(updated), 1)
        self.assertIsInstance(updated[0], SensorReliabilityUpdatedEvent)
        self.assertEqual(updated[0].sensor_id, "sensor-a")
        self.assertEqual(updated[0].reliability, 1.0)
        self.assertEqual(updated[0].predictions_considered, 1)

        history = memory_ledger.sensor_reliability_ledger.history_for("sensor-a")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].reliability, 1.0)

    def test_each_sensor_develops_an_independent_reliability_score(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        _resolve_one_prediction(
            kernel, sensor_id="sensor-a", belief_id="belief-a", opportunity_id="opp-a", plan_id="plan-a",
            success=True,
        )
        _resolve_one_prediction(
            kernel, sensor_id="sensor-b", belief_id="belief-b", opportunity_id="opp-b", plan_id="plan-b",
            success=False,
        )

        self.assertEqual(memory_ledger.sensor_reliability_ledger.latest_for("sensor-a").reliability, 1.0)
        self.assertEqual(memory_ledger.sensor_reliability_ledger.latest_for("sensor-b").reliability, 0.0)

    def test_reliability_is_recomputed_as_more_predictions_resolve(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        _resolve_one_prediction(
            kernel, sensor_id="sensor-a", belief_id="belief-a1", opportunity_id="opp-a1", plan_id="plan-a1",
            success=True,
        )
        self.assertEqual(memory_ledger.sensor_reliability_ledger.latest_for("sensor-a").reliability, 1.0)

        _resolve_one_prediction(
            kernel, sensor_id="sensor-a", belief_id="belief-a2", opportunity_id="opp-a2", plan_id="plan-a2",
            success=False,
        )
        self.assertEqual(memory_ledger.sensor_reliability_ledger.latest_for("sensor-a").reliability, 0.5)

    def test_a_shared_opportunity_attributes_resolution_to_every_contributing_sensor(self) -> None:
        # An opportunity aggregated from beliefs contributed by two different
        # sensors (Task #31's aggregation) means both sensors share credit or
        # blame when that shared prediction resolves.
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_belief_created(kernel, belief_id="belief-a", sensor_id="sensor-a")
        publish_belief_created(kernel, belief_id="belief-b", sensor_id="sensor-b")
        publish_opportunity_identified(kernel, opportunity_id="opp-shared", belief_ids=("belief-a", "belief-b"))
        publish_plan_proposed(kernel, plan_id="plan-shared", opportunity_id="opp-shared", expected_value=60.0)
        publish_action_succeeded(kernel, action_id="action-shared", plan_id="plan-shared")

        self.assertEqual(memory_ledger.sensor_reliability_ledger.latest_for("sensor-a").reliability, 1.0)
        self.assertEqual(memory_ledger.sensor_reliability_ledger.latest_for("sensor-b").reliability, 1.0)


class MemoryLedgerFastLearningReplayTests(unittest.TestCase):
    def test_replay_reconstructs_reliability(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        memory_ledger = MemoryLedger(kernel)

        _resolve_one_prediction(
            kernel, sensor_id="sensor-a", belief_id="belief-a1", opportunity_id="opp-a1", plan_id="plan-a1",
            success=True,
        )
        _resolve_one_prediction(
            kernel, sensor_id="sensor-a", belief_id="belief-a2", opportunity_id="opp-a2", plan_id="plan-a2",
            success=False,
        )

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_memory_ledger.sensor_reliability_ledger.read_all(),
            memory_ledger.sensor_reliability_ledger.read_all(),
        )
        self.assertEqual(rebuilt_memory_ledger.sensor_reliability_ledger.latest_for("sensor-a").reliability, 0.5)


class MemoryLedgerFastLearningSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_reliability(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        _resolve_one_prediction(
            kernel, sensor_id="sensor-a", belief_id="belief-a1", opportunity_id="opp-a1", plan_id="plan-a1",
            success=True,
        )
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored = rebuilt_memory_ledger.sensor_reliability_ledger.read_all()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored, memory_ledger.sensor_reliability_ledger.read_all())
        self.assertEqual(rebuilt_memory_ledger.sensor_reliability_ledger.latest_for("sensor-a").reliability, 1.0)

    def test_a_belief_attributed_before_the_snapshot_still_attributes_after_restore(self) -> None:
        # A belief_id learned (BELIEF_CREATED -> sensor) before the snapshot
        # boundary must still resolve to its sensor when that SAME still-live
        # belief_id is later folded into a brand new opportunity after
        # restore (Task #31's aggregation can do exactly this) — otherwise
        # the sensor silently drops out of the Fast Learning Loop.
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_belief_created(kernel, belief_id="belief-a", sensor_id="sensor-a")
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        publish_opportunity_identified(rebuilt_kernel, opportunity_id="opp-later", belief_ids=("belief-a",))
        publish_plan_proposed(rebuilt_kernel, plan_id="plan-later", opportunity_id="opp-later", expected_value=60.0)
        publish_action_succeeded(rebuilt_kernel, action_id="action-later", plan_id="plan-later")

        history = rebuilt_memory_ledger.sensor_reliability_ledger.history_for("sensor-a")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].reliability, 1.0)

    def test_a_plan_left_pending_across_the_snapshot_still_attributes_after_restore(self) -> None:
        # Mirrors PredictionLedger's own "plan-2 left pending across a
        # snapshot" shape: the plan's sensor attribution must also survive
        # so its later resolution still updates the right sensor.
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_belief_created(kernel, belief_id="belief-a", sensor_id="sensor-a")
        publish_opportunity_identified(kernel, opportunity_id="opp-a", belief_ids=("belief-a",))
        publish_plan_proposed(kernel, plan_id="plan-a", opportunity_id="opp-a", expected_value=60.0)
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        publish_action_succeeded(rebuilt_kernel, action_id="action-a", plan_id="plan-a")

        history = rebuilt_memory_ledger.sensor_reliability_ledger.history_for("sensor-a")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].reliability, 1.0)


def publish_research_spend_approved(
    kernel: Kernel,
    *,
    request_id: str = "request-1",
    deliberation_id: str = "deliberation-1",
    category: str = "research",
    approved_cost: float = 5.0,
    reason: str = "within research budget and caps",
) -> None:
    kernel.publish(
        ResearchSpendApprovedEvent(
            source_component="governor",
            request_id=request_id,
            deliberation_id=deliberation_id,
            category=category,
            approved_cost=approved_cost,
            reason=reason,
        )
    )


class ResearchSpendRecordModelTests(unittest.TestCase):
    def test_record_carries_required_fields(self) -> None:
        record = ResearchSpendRecord(
            request_id="request-1", correlation_id="correlation-1", category="research", cost=5.0
        )

        self.assertEqual(record.request_id, "request-1")
        self.assertEqual(record.correlation_id, "correlation-1")
        self.assertEqual(record.category, "research")
        self.assertEqual(record.cost, 5.0)

    def test_record_is_immutable(self) -> None:
        record = ResearchSpendRecord(
            request_id="request-1", correlation_id="correlation-1", category="research", cost=5.0
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.cost = 10.0  # type: ignore[misc]


class ResearchSpendLedgerTests(unittest.TestCase):
    def test_total_for_correlation_sums_only_matching_entries(self) -> None:
        ledger = ResearchSpendLedger()
        ledger.append(ResearchSpendRecord(request_id="r1", correlation_id="c1", category="research", cost=5.0))
        ledger.append(ResearchSpendRecord(request_id="r2", correlation_id="c1", category="research", cost=3.0))
        ledger.append(ResearchSpendRecord(request_id="r3", correlation_id="c2", category="research", cost=100.0))

        self.assertEqual(ledger.total_for_correlation("c1"), 8.0)


class MemoryLedgerResearchSpendTests(unittest.TestCase):
    def test_research_spend_approved_is_recorded_under_its_correlation_id(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_research_spend_approved(kernel, request_id="request-1", approved_cost=7.5)

        records = memory_ledger.research_spend_ledger.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].request_id, "request-1")
        self.assertEqual(records[0].cost, 7.5)
        self.assertNotEqual(records[0].correlation_id, "")

    def test_multiple_approvals_under_the_same_correlation_id_accumulate(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        # A single publish() call mints one correlation_id and every nested
        # publish during that same dispatch inherits it (Kernel.publish),
        # so two spends published back to back outside any dispatch instead
        # get their own fresh correlation_id each — assert against each
        # event's own correlation_id rather than assuming they match.
        publish_research_spend_approved(kernel, request_id="request-1", approved_cost=4.0)
        first_correlation_id = memory_ledger.research_spend_ledger.read_all()[0].correlation_id

        total = memory_ledger.research_spend_ledger.total_for_correlation(first_correlation_id)
        self.assertEqual(total, 4.0)

    def test_snapshot_restore_reconstructs_research_spend_ledger(self) -> None:
        kernel = Kernel()
        memory_ledger = MemoryLedger(kernel)

        publish_research_spend_approved(kernel, request_id="request-1", approved_cost=5.0)
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_memory_ledger = MemoryLedger(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored = rebuilt_memory_ledger.research_spend_ledger.read_all()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].request_id, "request-1")
        self.assertEqual(restored[0].cost, 5.0)


if __name__ == "__main__":
    unittest.main()
