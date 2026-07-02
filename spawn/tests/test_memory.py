import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import ActionFailedEvent, ActionSucceededEvent, Event, EventType
from src.kernel import Kernel
from src.memory import (
    EpisodicMemoryEntry,
    EpisodicMemoryStore,
    FinancialLedger,
    Heuristic,
    HeuristicStore,
    LedgerEntry,
    MemoryLedger,
    Outcome,
    OutcomeStore,
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


if __name__ == "__main__":
    unittest.main()
