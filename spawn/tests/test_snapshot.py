import tempfile
import unittest
from pathlib import Path

import main
from src.kernel import EventLog, Kernel


def _boot_fresh(log_path: Path) -> main.Organism:
    kernel = Kernel(event_log=EventLog(path=log_path))
    organism = main.build_organism(kernel=kernel)
    main.configure_bootstrap(organism)
    organism.kernel.start()
    main.run_bootstrap_cycle(organism)
    return organism


def _reboot(log_path: Path) -> main.Organism:
    kernel = Kernel(event_log=EventLog(path=log_path))
    organism = main.build_organism(kernel=kernel)
    main.configure_bootstrap(organism)
    organism.kernel.start()
    return organism


def _state_signature(organism: main.Organism) -> tuple:
    """A comparable snapshot of every store this task's snapshotting covers.

    Excludes opportunity_id/plan_id/action_id: each is a fresh uuid4() minted
    inside its owning component's dispatch handler on every dispatch — live
    or replayed — rather than read back from a persisted event, so it is
    never expected to match across separate replay passes (see the identical
    exclusion, with the same rationale, in tests/test_replay.py).
    """
    return (
        [(b.belief_id, b.confidence, b.claim) for b in organism.world_model.belief_store.read_all()],
        [o.expected_value for o in organism.executive.opportunity_store.read_all()],
        [(p.expected_value, p.attention_cost, p.capital_cost) for p in organism.executive.plan_store.read_all()],
        len(organism.executive.decision_record_store.read_all()),
        [
            (b.budget_id, b.available_attention, b.available_capital)
            for b in organism.governor.budget_store.read_all()
        ],
        [a.decision for a in organism.governor.approval_log.read_all()],
        [(r.status, r.result) for r in organism.executor.action_log.read_all()],
        [(o.success, o.result) for o in organism.memory_ledger.outcome_store.read_all()],
        [(e.delta_attention, e.delta_capital) for e in organism.memory_ledger.financial_ledger.read_all()],
    )


class SnapshotCreationTests(unittest.TestCase):
    def test_snapshot_creation_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            organism = _boot_fresh(Path(tmpdir) / "events.jsonl")

            sequence = organism.kernel.create_snapshot()
            record = organism.kernel.snapshot_store.load()

            self.assertEqual(sequence, organism.kernel.event_log.latest_sequence())
            self.assertIsNotNone(record)
            self.assertEqual(record["sequence"], sequence)
            self.assertIn("world_model.beliefs", record["sources"])
            # 3 from the Executive's cold-start research seeding (Task #1),
            # now real beliefs via Perception (Task #2.6), plus 1 from
            # _boot_fresh's explicit bootstrap observation.
            self.assertEqual(len(record["sources"]["world_model.beliefs"]), 4)


class SnapshotAssistedRestartTests(unittest.TestCase):
    def test_restart_restores_from_latest_snapshot_plus_remaining_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"
            organism = _boot_fresh(log_path)
            organism.kernel.create_snapshot()
            main.run_bootstrap_cycle(organism)  # second cycle happens after the snapshot

            rebooted = _reboot(log_path)

            self.assertEqual(_state_signature(rebooted), _state_signature(organism))

    def test_replay_after_snapshot_only_dispatches_the_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"
            organism = _boot_fresh(log_path)
            snapshot_sequence = organism.kernel.create_snapshot()
            main.run_bootstrap_cycle(organism)
            total_events = organism.kernel.event_log.latest_sequence()

            rebooted_kernel = Kernel(event_log=EventLog(path=log_path))
            dispatched: list = []
            for event_type in {event.event_type for _, event in rebooted_kernel.event_log.read_all()}:
                rebooted_kernel.register_subscriber(event_type, dispatched.append)
            rebooted_kernel.replay()

            tail_length = total_events - snapshot_sequence
            self.assertEqual(len(dispatched), tail_length)
            self.assertLess(tail_length, total_events)

    def test_snapshot_assisted_replay_matches_full_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with_snapshot_log = Path(tmpdir) / "with_snapshot.jsonl"
            without_snapshot_log = Path(tmpdir) / "without_snapshot.jsonl"

            with_snapshot = _boot_fresh(with_snapshot_log)
            with_snapshot.kernel.create_snapshot()
            main.run_bootstrap_cycle(with_snapshot)

            without_snapshot = _boot_fresh(without_snapshot_log)
            main.run_bootstrap_cycle(without_snapshot)

            rebooted_with_snapshot = _reboot(with_snapshot_log)
            rebooted_without_snapshot = _reboot(without_snapshot_log)

            self.assertEqual(_state_signature(rebooted_with_snapshot), _state_signature(rebooted_without_snapshot))

    def test_multiple_restarts_remain_deterministic_with_a_snapshot_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"
            organism = _boot_fresh(log_path)
            organism.kernel.create_snapshot()
            main.run_bootstrap_cycle(organism)

            second = _reboot(log_path)
            third = _reboot(log_path)

            self.assertEqual(_state_signature(second), _state_signature(third))


if __name__ == "__main__":
    unittest.main()
