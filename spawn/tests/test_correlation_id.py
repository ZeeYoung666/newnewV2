import unittest
from uuid import UUID, uuid4

from src.events import Event, EventType
from src.kernel import Kernel


class KernelCorrelationIdTests(unittest.TestCase):
    def test_root_publish_assigns_a_fresh_correlation_id(self) -> None:
        kernel = Kernel()
        event = Event(source_component="perception", event_type=EventType.OBSERVATION_CREATED)

        kernel.publish(event)

        self.assertIsInstance(event.correlation_id, UUID)

    def test_two_independent_root_publishes_get_different_correlation_ids(self) -> None:
        kernel = Kernel()
        first = Event(source_component="perception", event_type=EventType.OBSERVATION_CREATED)
        second = Event(source_component="perception", event_type=EventType.OBSERVATION_CREATED)

        kernel.publish(first)
        kernel.publish(second)

        self.assertNotEqual(first.correlation_id, second.correlation_id)

    def test_nested_publish_during_dispatch_inherits_the_active_correlation_id(self) -> None:
        kernel = Kernel()
        kernel.start()
        triggering = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        nested = Event(source_component="world_model", event_type=EventType.PLAN_PROPOSED)

        def subscriber(event: Event) -> None:
            if event is triggering:
                kernel.publish(nested)

        kernel.register_subscriber(EventType.BELIEF_UPDATED, subscriber)
        kernel.publish(triggering)
        kernel.run_until_idle()

        self.assertIsNotNone(triggering.correlation_id)
        self.assertEqual(nested.correlation_id, triggering.correlation_id)

    def test_cascade_still_shares_one_id_when_drain_happens_after_publish_returns(self) -> None:
        # Mirrors the real main.py path: after start(), publish() for a
        # non-lifecycle event does NOT auto-drain; the caller drains later
        # via a separate run_until_idle() call. The active id must survive
        # that gap.
        kernel = Kernel()
        kernel.start()
        triggering = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        nested = Event(source_component="world_model", event_type=EventType.PLAN_PROPOSED)

        def subscriber(event: Event) -> None:
            if event is triggering:
                kernel.publish(nested)

        kernel.register_subscriber(EventType.BELIEF_UPDATED, subscriber)
        kernel.publish(triggering)  # returns without draining; queue still has 1 pending task
        self.assertEqual(kernel.scheduler.pending_count(), 1)

        kernel.run_until_idle()  # caller drains separately, as main.run_bootstrap_cycle does

        self.assertEqual(nested.correlation_id, triggering.correlation_id)

    def test_publish_never_overwrites_a_preexisting_correlation_id(self) -> None:
        kernel = Kernel()
        preset_id = uuid4()
        event = Event(
            source_component="perception",
            event_type=EventType.OBSERVATION_CREATED,
            correlation_id=preset_id,
        )

        kernel.publish(event)

        self.assertEqual(event.correlation_id, preset_id)

    def test_active_correlation_id_clears_after_full_cascade_drains(self) -> None:
        kernel = Kernel()
        kernel.start()
        first = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        kernel.publish(first)
        kernel.run_until_idle()

        second = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        kernel.publish(second)
        kernel.run_until_idle()

        self.assertNotEqual(first.correlation_id, second.correlation_id)


if __name__ == "__main__":
    unittest.main()
