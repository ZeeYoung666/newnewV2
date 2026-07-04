import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import (
    ActionFailedEvent,
    ActionSucceededEvent,
    Event,
    EventType,
    LearningIterationCompletedEvent,
    LearningIterationStartedEvent,
    PlanProposedEvent,
    PredictionRecordedEvent,
    PredictionResolvedEvent,
)
from src.kernel import EventLog, Kernel
from src.memory import (
    EpisodicMemoryEntry,
    EpisodicMemoryStore,
    FinancialLedger,
    Heuristic,
    HeuristicStore,
    LearningIteration,
    LearningLedger,
    LedgerEntry,
    MediumLearner,
    MemoryLedger,
    Outcome,
    OutcomeStore,
    PredictionLedger,
    PredictionRecord,
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


if __name__ == "__main__":
    unittest.main()
