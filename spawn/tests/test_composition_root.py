import unittest

from src.events import EventType
from src.executive import Executive
from src.executor import Executor
from src.governor import Governor
from src.inference import InferencePort
from src.kernel import Kernel
from src.memory import MemoryLedger
from src.perception import Perception
from src.world_model import WorldModel

import main


class BuildOrganismTests(unittest.TestCase):
    def test_builds_exactly_one_shared_kernel(self) -> None:
        organism = main.build_organism()

        self.assertIsInstance(organism.kernel, Kernel)
        self.assertIs(organism.perception._kernel, organism.kernel)
        self.assertIs(organism.world_model._kernel, organism.kernel)
        self.assertIs(organism.executive._kernel, organism.kernel)
        self.assertIs(organism.governor._kernel, organism.kernel)
        self.assertIs(organism.executor._kernel, organism.kernel)
        self.assertIs(organism.memory_ledger._kernel, organism.kernel)
        self.assertIs(organism.inference_port._kernel, organism.kernel)

    def test_constructs_every_required_component_exactly_once(self) -> None:
        organism = main.build_organism()

        self.assertIsInstance(organism.perception, Perception)
        self.assertIsInstance(organism.world_model, WorldModel)
        self.assertIsInstance(organism.executive, Executive)
        self.assertIsInstance(organism.governor, Governor)
        self.assertIsInstance(organism.executor, Executor)
        self.assertIsInstance(organism.memory_ledger, MemoryLedger)
        self.assertIsInstance(organism.inference_port, InferencePort)

    def test_every_subscription_registered_exactly_once(self) -> None:
        organism = main.build_organism()

        subscriber_counts = {
            event_type: len(subscribers) for event_type, subscribers in organism.kernel._subscribers.items()
        }

        self.assertEqual(subscriber_counts.get(EventType.OBSERVATION_CREATED), 1)
        self.assertEqual(subscriber_counts.get(EventType.BELIEF_CREATED), 1)
        self.assertEqual(subscriber_counts.get(EventType.BELIEF_UPDATED), 1)
        # Governor (policy evaluation) and MemoryLedger (prediction recording)
        # both react to a proposed plan — the one deliberate fan-out in this wiring.
        self.assertEqual(subscriber_counts.get(EventType.PLAN_PROPOSED), 2)
        self.assertEqual(subscriber_counts.get(EventType.APPROVAL_GRANTED), 1)
        self.assertEqual(subscriber_counts.get(EventType.ACTION_SUCCEEDED), 1)
        self.assertEqual(subscriber_counts.get(EventType.ACTION_FAILED), 1)

        # No event type should ever have more than one subscriber in this wiring,
        # except the deliberate fan-out above.
        multi_subscriber_event_types = {EventType.PLAN_PROPOSED}
        for event_type, count in subscriber_counts.items():
            if event_type in multi_subscriber_event_types:
                continue
            self.assertLessEqual(count, 1, f"{event_type} has {count} subscribers, expected at most 1")

    def test_building_twice_yields_independent_kernels(self) -> None:
        first = main.build_organism()
        second = main.build_organism()

        self.assertIsNot(first.kernel, second.kernel)


class BootstrapCycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.organism = main.build_organism()
        main.configure_bootstrap(self.organism)
        self.organism.kernel.start()
        self.addCleanup(self.organism.kernel.stop)

    def test_one_observation_produces_a_belief(self) -> None:
        main.run_bootstrap_cycle(self.organism)

        beliefs = self.organism.world_model.belief_store.read_all()
        self.assertEqual(len(beliefs), 1)

    def test_one_observation_produces_an_approved_plan(self) -> None:
        main.run_bootstrap_cycle(self.organism)

        plans = self.organism.executive.plan_store.read_all()
        self.assertEqual(len(plans), 1)

        approvals = self.organism.governor.approval_log.read_all()
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0].decision, "approved")

    def test_one_observation_produces_two_successful_actions(self) -> None:
        main.run_bootstrap_cycle(self.organism)

        records = self.organism.executor.action_log.read_all()
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record.status == "succeeded" for record in records))

    def test_one_observation_produces_two_outcomes_and_ledger_entries(self) -> None:
        main.run_bootstrap_cycle(self.organism)

        outcomes = self.organism.memory_ledger.outcome_store.read_all()
        ledger_entries = self.organism.memory_ledger.financial_ledger.read_all()
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(len(ledger_entries), 2)
        self.assertTrue(all(outcome.success for outcome in outcomes))

    def test_full_cycle_emits_events_in_architectural_order(self) -> None:
        start_sequence = self.organism.kernel.event_log.latest_sequence() + 1

        main.run_bootstrap_cycle(self.organism)

        cascade = self.organism.kernel.event_log.read_from(start_sequence)
        event_types = [event.event_type for _, event in cascade]

        self.assertEqual(
            event_types,
            [
                EventType.OBSERVATION_CREATED,
                EventType.BELIEF_CREATED,
                EventType.OPPORTUNITY_IDENTIFIED,
                EventType.OPPORTUNITY_SCORED,
                EventType.PLAN_PROPOSED,
                EventType.POLICY_EVALUATED,
                EventType.BUDGET_CHECKED,
                EventType.APPROVAL_GRANTED,
                EventType.PREDICTION_RECORDED,
                EventType.ACTION_APPROVED,
                EventType.ACTION_ATTEMPTED,
                EventType.SANDBOX_EXECUTION_STARTED,
                EventType.SANDBOX_EXECUTION_COMPLETED,
                EventType.ACTION_SUCCEEDED,
                EventType.ACTION_APPROVED,
                EventType.ACTION_ATTEMPTED,
                EventType.SANDBOX_EXECUTION_STARTED,
                EventType.SANDBOX_EXECUTION_COMPLETED,
                EventType.ACTION_SUCCEEDED,
                EventType.OUTCOME_RECORDED,
                EventType.LEDGER_ENTRY_POSTED,
                EventType.OUTCOME_RECORDED,
                EventType.LEDGER_ENTRY_POSTED,
                EventType.PREDICTION_RESOLVED,
                EventType.LEARNING_ITERATION_STARTED,
                EventType.LEARNING_ITERATION_COMPLETED,
            ],
        )

    def test_full_cycle_shares_one_correlation_id_across_every_event(self) -> None:
        start_sequence = self.organism.kernel.event_log.latest_sequence() + 1

        main.run_bootstrap_cycle(self.organism)

        cascade = self.organism.kernel.event_log.read_from(start_sequence)
        correlation_ids = {event.correlation_id for _, event in cascade}

        self.assertEqual(len(cascade), 26)
        self.assertEqual(len(correlation_ids), 1)
        self.assertIsNotNone(next(iter(correlation_ids)))

    def test_two_independent_cycles_receive_different_correlation_ids(self) -> None:
        first_start = self.organism.kernel.event_log.latest_sequence() + 1
        main.run_bootstrap_cycle(self.organism)
        first_cascade = [event for _, event in self.organism.kernel.event_log.read_from(first_start)]

        second_start = self.organism.kernel.event_log.latest_sequence() + 1
        main.run_bootstrap_cycle(self.organism)
        second_cascade = [event for _, event in self.organism.kernel.event_log.read_from(second_start)]

        first_ids = {event.correlation_id for event in first_cascade}
        second_ids = {event.correlation_id for event in second_cascade}

        self.assertEqual(len(first_cascade), 26)
        self.assertEqual(len(second_cascade), 26)
        self.assertEqual(len(first_ids), 1)
        self.assertEqual(len(second_ids), 1)
        self.assertNotEqual(first_ids, second_ids)


class MainEntrypointTests(unittest.TestCase):
    def test_main_boots_the_organism_and_runs_one_full_cycle(self) -> None:
        organism = main.main()

        self.assertFalse(organism.kernel.is_running())
        self.assertEqual(len(organism.world_model.belief_store.read_all()), 1)
        self.assertEqual(len(organism.memory_ledger.outcome_store.read_all()), 2)


if __name__ == "__main__":
    unittest.main()
