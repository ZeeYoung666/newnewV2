import unittest

from src.events import (
    Event,
    EventType,
    KernelStartingEvent,
    KernelStartedEvent,
    KernelStoppingEvent,
    KernelStoppedEvent,
)
from src.kernel import EventLog, Kernel, Subscriber


class KernelTests(unittest.TestCase):
    def test_subscribers_receive_matching_events(self) -> None:
        kernel = Kernel()
        received: list[Event] = []

        def subscriber(event: Event) -> None:
            received.append(event)

        kernel.register_subscriber(EventType.BELIEF_UPDATED, subscriber)
        kernel.publish(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_type, EventType.BELIEF_UPDATED)

    def test_multiple_subscribers_work_correctly(self) -> None:
        kernel = Kernel()
        received_a: list[Event] = []
        received_b: list[Event] = []

        kernel.register_subscriber(EventType.PLAN_PROPOSED, received_a.append)
        kernel.register_subscriber(EventType.PLAN_PROPOSED, received_b.append)

        event = Event(source_component="executive", event_type=EventType.PLAN_PROPOSED)
        kernel.publish(event)

        self.assertEqual(received_a, [event])
        self.assertEqual(received_b, [event])

    def test_publishing_with_no_subscribers_succeeds(self) -> None:
        kernel = Kernel()
        event = Event(source_component="governor", event_type=EventType.APPROVAL_GRANTED)

        kernel.publish(event)

    def test_unregistering_subscribers_works(self) -> None:
        kernel = Kernel()
        received: list[Event] = []

        def subscriber(event: Event) -> None:
            received.append(event)

        kernel.register_subscriber(EventType.ACTION_ATTEMPTED, subscriber)
        kernel.unregister_subscriber(EventType.ACTION_ATTEMPTED, subscriber)
        kernel.publish(Event(source_component="executor", event_type=EventType.ACTION_ATTEMPTED))

        self.assertEqual(received, [])

    def test_event_order_is_preserved(self) -> None:
        kernel = Kernel()
        received: list[Event] = []

        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        first = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        second = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)

        kernel.publish(first)
        kernel.publish(second)

        self.assertEqual(received, [first, second])

    def test_event_log_appends_in_order_and_assigns_increasing_sequences(self) -> None:
        event_log = EventLog()

        first = Event(source_component="perception", event_type=EventType.BELIEF_UPDATED)
        second = Event(source_component="world_model", event_type=EventType.PLAN_PROPOSED)

        event_log.append(first)
        event_log.append(second)

        stored = event_log.read_all()

        self.assertEqual([sequence for sequence, _ in stored], [1, 2])
        self.assertEqual([event for _, event in stored], [first, second])
        self.assertEqual(event_log.latest_sequence(), 2)

    def test_event_log_read_from_returns_suffix_without_mutating_entries(self) -> None:
        event_log = EventLog()
        first = Event(source_component="perception", event_type=EventType.BELIEF_UPDATED)
        second = Event(source_component="world_model", event_type=EventType.PLAN_PROPOSED)
        third = Event(source_component="executive", event_type=EventType.PLAN_SELECTED)

        event_log.append(first)
        event_log.append(second)
        event_log.append(third)

        suffix = event_log.read_from(2)
        self.assertEqual([sequence for sequence, _ in suffix], [2, 3])
        self.assertEqual([event for _, event in suffix], [second, third])

        original = event_log.read_all()
        self.assertEqual([event for _, event in original], [first, second, third])
        self.assertEqual([sequence for sequence, _ in original], [1, 2, 3])

    def test_kernel_writes_every_published_event_exactly_once(self) -> None:
        kernel = Kernel()
        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        first = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        second = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)

        kernel.publish(first)
        kernel.publish(second)

        self.assertEqual(received, [first, second])
        self.assertEqual([event for _, event in kernel.event_log.read_all()], [first, second])
        self.assertEqual(kernel.event_log.latest_sequence(), 2)

    def test_fifo_ordering_is_preserved_during_run_until_idle(self) -> None:
        kernel = Kernel()
        kernel.start()
        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        first = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        second = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)

        kernel.publish(first)
        kernel.publish(second)
        kernel.run_until_idle()

        self.assertEqual(received, [first, second])

    def test_nested_publishes_are_queued_and_processed_later(self) -> None:
        kernel = Kernel()
        kernel.start()
        received: list[Event] = []
        first = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        second = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)

        def subscriber(event: Event) -> None:
            received.append(event)
            if event is first:
                kernel.publish(second)

        kernel.register_subscriber(EventType.BELIEF_UPDATED, subscriber)
        kernel.publish(first)
        kernel.run_until_idle()

        self.assertEqual(received, [first, second])

    def test_stopping_the_kernel_prevents_further_processing(self) -> None:
        kernel = Kernel()
        kernel.start()
        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        event = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        kernel.publish(event)
        kernel.stop()
        kernel.run_until_idle()

        self.assertEqual(received, [])

    def test_start_emits_kernel_starting_and_kernel_started(self) -> None:
        kernel = Kernel()
        received: list[Event] = []
        kernel.register_subscriber(EventType.KERNEL_STARTING, received.append)
        kernel.register_subscriber(EventType.KERNEL_STARTED, received.append)

        kernel.start()

        self.assertEqual(len(received), 2)
        self.assertIsInstance(received[0], KernelStartingEvent)
        self.assertEqual(received[0].event_type, EventType.KERNEL_STARTING)
        self.assertIsInstance(received[1], KernelStartedEvent)
        self.assertEqual(received[1].event_type, EventType.KERNEL_STARTED)
        self.assertEqual([event for _, event in kernel.event_log.read_all()[-2:]], received)

    def test_stop_emits_kernel_stopping_and_kernel_stopped(self) -> None:
        kernel = Kernel()
        received: list[Event] = []
        kernel.register_subscriber(EventType.KERNEL_STOPPING, received.append)
        kernel.register_subscriber(EventType.KERNEL_STOPPED, received.append)

        kernel.start()
        kernel.stop()

        self.assertEqual(len(received), 2)
        self.assertIsInstance(received[0], KernelStoppingEvent)
        self.assertEqual(received[0].event_type, EventType.KERNEL_STOPPING)
        self.assertIsInstance(received[1], KernelStoppedEvent)
        self.assertEqual(received[1].event_type, EventType.KERNEL_STOPPED)
        self.assertEqual([event for _, event in kernel.event_log.read_all()[-2:]], received)

    def test_repeated_start_and_stop_do_not_emit_duplicate_lifecycle_events_on_no_state_change(self) -> None:
        kernel = Kernel()
        received: list[Event] = []
        kernel.register_subscriber(EventType.KERNEL_STARTING, received.append)
        kernel.register_subscriber(EventType.KERNEL_STARTED, received.append)
        kernel.register_subscriber(EventType.KERNEL_STOPPING, received.append)
        kernel.register_subscriber(EventType.KERNEL_STOPPED, received.append)

        kernel.start()
        kernel.start()
        kernel.stop()
        kernel.stop()

        self.assertEqual(len(received), 4)
        self.assertEqual(
            [event.event_type for event in received],
            [
                EventType.KERNEL_STARTING,
                EventType.KERNEL_STARTED,
                EventType.KERNEL_STOPPING,
                EventType.KERNEL_STOPPED,
            ],
        )


if __name__ == "__main__":
    unittest.main()
