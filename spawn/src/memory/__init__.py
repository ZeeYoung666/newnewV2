"""Memory & Ledger: records outcomes, episodic memory, financial ledger, learned heuristics.

Owns episodic memory, the financial ledger, and learned heuristics. Reacts to
executed actions; does not update the Executive, score predictions, or learn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from src.events import (
    ActionFailedEvent,
    ActionSucceededEvent,
    EventType,
    LedgerEntryPostedEvent,
    OutcomeRecordedEvent,
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


class MemoryLedger:
    """Records outcomes, episodic memory, and ledger entries for every executed action."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.outcome_store = OutcomeStore()
        self.episodic_memory_store = EpisodicMemoryStore()
        self.financial_ledger = FinancialLedger()
        self.heuristic_store = HeuristicStore()
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, self._on_action_succeeded)
        kernel.register_subscriber(EventType.ACTION_FAILED, self._on_action_failed)
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

    def _restore_outcomes(self, outcomes: list[Outcome]) -> None:
        for outcome in outcomes:
            self.outcome_store.append(outcome)

    def _restore_episodic_entries(self, entries: list[EpisodicMemoryEntry]) -> None:
        for entry in entries:
            self.episodic_memory_store.append(entry)

    def _restore_ledger_entries(self, entries: list[LedgerEntry]) -> None:
        for entry in entries:
            self.financial_ledger.append(entry)

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
    "OutcomeStore",
    "EpisodicMemoryStore",
    "FinancialLedger",
    "HeuristicStore",
    "MemoryLedger",
]
