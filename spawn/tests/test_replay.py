import tempfile
import unittest
from pathlib import Path

import main
from src.events import EventType
from src.kernel import EventLog, Kernel


def _boot_fresh(log_path: Path) -> main.Organism:
    """First-ever boot: fresh components, empty log, run one bootstrap cycle."""
    kernel = Kernel(event_log=EventLog(path=log_path))
    organism = main.build_organism(kernel=kernel)
    main.configure_bootstrap(organism)
    organism.kernel.start()
    main.run_bootstrap_cycle(organism)
    organism.kernel.stop()
    return organism


def _reboot(log_path: Path) -> main.Organism:
    """Simulate a crash + restart: fresh components, same persisted log, no new
    observation. Genesis config (constitution/budget/sensor/tools) is re-applied
    every boot since it is not itself event-sourced; everything downstream of it
    is reconstructed purely by replaying the persisted log.
    """
    kernel = Kernel(event_log=EventLog(path=log_path))
    organism = main.build_organism(kernel=kernel)
    main.configure_bootstrap(organism)
    organism.kernel.start()
    return organism


class ReplayOnStartTests(unittest.TestCase):
    def setUp(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.log_path = Path(tmpdir.name) / "events.jsonl"

    def test_empty_log_boots_successfully(self) -> None:
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        organism = main.build_organism(kernel=kernel)
        main.configure_bootstrap(organism)

        organism.kernel.start()

        self.assertTrue(organism.kernel.is_running())
        self.assertEqual(organism.world_model.belief_store.read_all(), [])
        self.assertEqual(organism.executor.action_log.read_all(), [])

    def test_existing_log_reconstructs_all_component_state(self) -> None:
        original = _boot_fresh(self.log_path)

        rebooted = _reboot(self.log_path)

        self.assertEqual(
            [(b.belief_id, b.confidence, b.claim) for b in rebooted.world_model.belief_store.read_all()],
            [(b.belief_id, b.confidence, b.claim) for b in original.world_model.belief_store.read_all()],
        )
        self.assertEqual(
            len(rebooted.executive.plan_store.read_all()), len(original.executive.plan_store.read_all())
        )
        self.assertEqual(
            len(rebooted.executive.decision_record_store.read_all()),
            len(original.executive.decision_record_store.read_all()),
        )
        self.assertEqual(
            [(a.decision, a.plan_id, a.reason) for a in rebooted.governor.approval_log.read_all()],
            [(a.decision, a.plan_id, a.reason) for a in original.governor.approval_log.read_all()],
        )
        self.assertEqual(
            [b.available_attention for b in rebooted.governor.budget_store.read_all()],
            [b.available_attention for b in original.governor.budget_store.read_all()],
        )
        self.assertEqual(
            [b.available_capital for b in rebooted.governor.budget_store.read_all()],
            [b.available_capital for b in original.governor.budget_store.read_all()],
        )
        # action_id is a fresh uuid4() minted inside the handler on every run
        # (original or replayed) rather than read from the event, so only the
        # observable outcome — status and result — is expected to match.
        self.assertEqual(
            [(r.status, r.result) for r in rebooted.executor.action_log.read_all()],
            [(r.status, r.result) for r in original.executor.action_log.read_all()],
        )
        self.assertEqual(
            [(o.success, o.result) for o in rebooted.memory_ledger.outcome_store.read_all()],
            [(o.success, o.result) for o in original.memory_ledger.outcome_store.read_all()],
        )
        self.assertEqual(
            [(e.delta_attention, e.delta_capital) for e in rebooted.memory_ledger.financial_ledger.read_all()],
            [(e.delta_attention, e.delta_capital) for e in original.memory_ledger.financial_ledger.read_all()],
        )

    def test_replay_preserves_original_event_order(self) -> None:
        _boot_fresh(self.log_path)

        replay_log = EventLog(path=self.log_path)
        original_order = [event.event_type for _, event in replay_log.read_all()]
        self.assertGreater(len(original_order), 0)

        observed_order: list[EventType] = []
        kernel = Kernel(event_log=replay_log)

        def record(event: object) -> None:
            observed_order.append(event.event_type)  # type: ignore[attr-defined]

        for event_type in set(original_order):
            kernel.register_subscriber(event_type, record)

        kernel.replay()

        self.assertEqual(observed_order, original_order)

    def test_replay_is_deterministic_across_multiple_restarts(self) -> None:
        _boot_fresh(self.log_path)

        second = _reboot(self.log_path)
        third = _reboot(self.log_path)

        self.assertEqual(
            [b.confidence for b in second.world_model.belief_store.read_all()],
            [b.confidence for b in third.world_model.belief_store.read_all()],
        )
        self.assertEqual(len(second.executor.action_log.read_all()), len(third.executor.action_log.read_all()))
        self.assertEqual(
            [b.available_capital for b in second.governor.budget_store.read_all()],
            [b.available_capital for b in third.governor.budget_store.read_all()],
        )
        self.assertEqual(
            len(second.memory_ledger.outcome_store.read_all()), len(third.memory_ledger.outcome_store.read_all())
        )

    def test_replay_does_not_append_duplicate_events(self) -> None:
        _boot_fresh(self.log_path)

        replay_log = EventLog(path=self.log_path)
        sequence_before_replay = replay_log.latest_sequence()

        kernel = Kernel(event_log=replay_log)
        main.build_organism(kernel=kernel)
        kernel.replay()

        self.assertEqual(replay_log.latest_sequence(), sequence_before_replay)
        self.assertEqual(len(replay_log.read_all()), sequence_before_replay)

    def test_replay_after_start_raises(self) -> None:
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        kernel.start()

        with self.assertRaises(RuntimeError):
            kernel.replay()

    def test_replay_twice_raises(self) -> None:
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        kernel.replay()

        with self.assertRaises(RuntimeError):
            kernel.replay()


if __name__ == "__main__":
    unittest.main()
