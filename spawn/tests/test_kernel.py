import unittest

from src.events import Event, EventType
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


if __name__ == "__main__":
    unittest.main()
