import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import main
from src.kernel import EventLog, Kernel


class MainAcceptsExplicitKernelTests(unittest.TestCase):
    def test_main_uses_the_passed_kernel_instead_of_building_a_default(self) -> None:
        kernel = Kernel()
        organism = main.main(kernel=kernel)
        self.assertIs(organism.kernel, kernel)

    def test_main_with_no_kernel_still_gets_a_fresh_in_memory_default(self) -> None:
        # Regression guard: existing callers (main.main() with no args, used
        # directly by tests/test_composition_root.py) must keep getting an
        # isolated, historyless organism -- persistence is a CLI-only concern.
        first = main.main()
        second = main.main()
        self.assertIsNot(first.kernel, second.kernel)
        self.assertEqual(len(first.world_model.belief_store.read_all()), 4)
        self.assertEqual(len(second.world_model.belief_store.read_all()), 4)


class RebootDoesNotReseedColdStartTests(unittest.TestCase):
    def test_reboot_replays_history_without_reseeding_or_growing_the_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"

            kernel1 = Kernel(event_log=EventLog(path=log_path))
            organism1 = main.build_organism(kernel=kernel1)
            main.configure_bootstrap(organism1)
            organism1.kernel.start()
            organism1.kernel.stop()

            sequence_after_first_boot = organism1.kernel.event_log.latest_sequence()
            beliefs_after_first_boot = {b.belief_id for b in organism1.world_model.belief_store.read_all()}
            self.assertTrue(beliefs_after_first_boot)
            research_events_after_first_boot = self._count_research_events(log_path)
            self.assertGreater(research_events_after_first_boot, 0)

            kernel2 = Kernel(event_log=EventLog(path=log_path))
            organism2 = main.build_organism(kernel=kernel2)
            main.configure_bootstrap(organism2)
            organism2.kernel.start()
            organism2.kernel.stop()

            # A second boot always appends its own KERNEL_STARTING/STARTED/
            # STOPPING/STOPPED lifecycle events (4) -- that growth is
            # expected and not what this test is guarding against. What
            # must NOT grow is the research.* event count: cold-start
            # firing again would append a fresh
            # RESEARCH_SPEND_REQUESTED/APPROVED/INTENT_EMITTED/OBSERVATION_
            # CREATED/BELIEF_CREATED cascade, which the guard seeing the
            # replayed history must prevent.
            self.assertEqual(organism2.kernel.event_log.latest_sequence(), sequence_after_first_boot + 4)
            self.assertEqual(self._count_research_events(log_path), research_events_after_first_boot)
            # Prior beliefs are visibly present after reboot, not reset.
            self.assertEqual(
                {b.belief_id for b in organism2.world_model.belief_store.read_all()},
                beliefs_after_first_boot,
            )

    @staticmethod
    def _count_research_events(log_path: Path) -> int:
        return sum(1 for line in log_path.read_text(encoding="utf-8").splitlines() if '"research.' in line)

    def test_run_exploration_cycle_after_reboot_builds_on_prior_state_not_from_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"

            kernel1 = Kernel(event_log=EventLog(path=log_path))
            organism1 = main.build_organism(kernel=kernel1)
            main.configure_bootstrap(organism1)
            organism1.kernel.start()
            main.run_exploration_cycle(organism1)
            organism1.kernel.stop()
            beliefs_after_first_explore = len(organism1.world_model.belief_store.read_all())

            kernel2 = Kernel(event_log=EventLog(path=log_path))
            organism2 = main.build_organism(kernel=kernel2)
            main.configure_bootstrap(organism2)
            organism2.kernel.start()
            # Reboot alone (no new explore call yet) must already show the
            # prior beliefs reconstructed from replay.
            self.assertEqual(len(organism2.world_model.belief_store.read_all()), beliefs_after_first_explore)
            organism2.kernel.stop()


class CLISequentialExploreInvocationsTests(unittest.TestCase):
    """End-to-end acceptance check: two real `python main.py explore` subprocess
    invocations against the same --data-dir, exactly as a user would run it.
    """

    def _run_explore(self, data_dir: Path) -> subprocess.CompletedProcess:
        main_py = Path(main.__file__).resolve()
        return subprocess.run(
            [sys.executable, str(main_py), "explore", "--data-dir", str(data_dir)],
            cwd=str(main_py.parent),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_second_invocation_does_not_reseed_and_shows_persisted_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "aether_data"
            log_path = data_dir / "event_log.jsonl"

            first = self._run_explore(data_dir)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue(log_path.exists())

            lines_after_first = log_path.read_text(encoding="utf-8").splitlines()
            cold_start_lines_after_first = sum(1 for line in lines_after_first if "cold-start" in line)
            self.assertGreater(cold_start_lines_after_first, 0)

            second = self._run_explore(data_dir)
            self.assertEqual(second.returncode, 0, second.stderr)

            lines_after_second = log_path.read_text(encoding="utf-8").splitlines()
            cold_start_lines_after_second = sum(1 for line in lines_after_second if "cold-start" in line)

            # No new persisted event carries the cold-start rationale on the
            # second run: the guard saw the replayed history and skipped it.
            self.assertEqual(cold_start_lines_after_second, cold_start_lines_after_first)
            # The second run's own (new) exploration batch still appended
            # something -- the log isn't just replaying and doing nothing.
            self.assertGreater(len(lines_after_second), len(lines_after_first))

            # The second run's stdout shows replayed history (prior beliefs)
            # live via the event stream, not an empty/from-scratch process.
            self.assertIn("belief.created", second.stdout)
            self.assertIn("kernel.started", second.stdout)


if __name__ == "__main__":
    unittest.main()
