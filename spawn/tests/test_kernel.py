import json
import tempfile
import unittest
from pathlib import Path

from src.events import (
    BeliefCreatedEvent,
    Event,
    EventType,
    KernelStartingEvent,
    KernelStartedEvent,
    KernelStoppingEvent,
    KernelStoppedEvent,
    ObservationCreatedEvent,
)
from src.kernel import EventLog, Kernel, Scheduler, Subscriber


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


class KernelSchedulerDelegationTests(unittest.TestCase):
    def test_kernel_owns_a_scheduler(self) -> None:
        kernel = Kernel()

        self.assertIsInstance(kernel.scheduler, Scheduler)

    def test_publish_after_start_queues_on_scheduler_until_drained(self) -> None:
        kernel = Kernel()
        kernel.start()
        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        event = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        kernel.publish(event)

        self.assertEqual(kernel.scheduler.pending_count(), 1)
        self.assertEqual(received, [])

        kernel.run_until_idle()

        self.assertEqual(kernel.scheduler.pending_count(), 0)
        self.assertEqual(received, [event])

    def test_process_next_delegates_exactly_one_task_to_scheduler(self) -> None:
        kernel = Kernel()
        kernel.start()
        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)
        kernel.publish(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))
        kernel.publish(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))

        self.assertEqual(kernel.scheduler.pending_count(), 2)

        kernel.process_next()

        self.assertEqual(kernel.scheduler.pending_count(), 1)
        self.assertEqual(len(received), 1)

        kernel.process_next()

        self.assertEqual(kernel.scheduler.pending_count(), 0)
        self.assertEqual(len(received), 2)

    def test_run_until_idle_drains_scheduler_not_just_kernel_state(self) -> None:
        kernel = Kernel()
        kernel.start()
        kernel.publish(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))
        kernel.publish(Event(source_component="executive", event_type=EventType.PLAN_PROPOSED))

        self.assertGreater(kernel.scheduler.pending_count(), 0)

        kernel.run_until_idle()

        self.assertEqual(kernel.scheduler.pending_count(), 0)


class EventLogPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.log_path = Path(self._tmpdir.name) / "data" / "events" / "events.jsonl"

    def test_default_construction_still_works_and_is_isolated(self) -> None:
        log_a = EventLog()
        log_b = EventLog()

        log_a.append(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))

        self.assertEqual(log_a.latest_sequence(), 1)
        self.assertEqual(log_b.latest_sequence(), 0)
        self.assertEqual(log_b.read_all(), [])

    def test_log_survives_restart(self) -> None:
        first = EventLog(path=self.log_path)
        event_a = BeliefCreatedEvent(
            source_component="world_model", belief_id="belief-1", claim="0.5", confidence=0.6, provenance="sensor-1"
        )
        event_b = ObservationCreatedEvent(
            source_component="perception",
            observation_id="observation-1",
            sensor_id="sensor-1",
            normalized_value=0.4,
            confidence=0.8,
            raw_source_type="market_feed",
        )
        first.append(event_a)
        first.append(event_b)
        del first  # simulate process exit

        restarted = EventLog(path=self.log_path)

        self.assertEqual(restarted.latest_sequence(), 2)
        restored = [event for _, event in restarted.read_all()]
        self.assertEqual(restored, [event_a, event_b])

    def test_sequence_numbers_continue_after_restart(self) -> None:
        first = EventLog(path=self.log_path)
        first.append(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))
        first.append(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))
        del first

        restarted = EventLog(path=self.log_path)
        third_sequence = restarted.append(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))

        self.assertEqual(third_sequence, 3)
        self.assertEqual(restarted.latest_sequence(), 3)
        self.assertEqual([sequence for sequence, _ in restarted.read_all()], [1, 2, 3])

    def test_ordering_preserved_across_restart(self) -> None:
        first = EventLog(path=self.log_path)
        events = [
            Event(source_component=f"component-{i}", event_type=EventType.BELIEF_UPDATED) for i in range(5)
        ]
        for event in events:
            first.append(event)
        del first

        restarted = EventLog(path=self.log_path)
        restored = [event for _, event in restarted.read_all()]

        self.assertEqual([event.source_component for event in restored], [event.source_component for event in events])

    def test_no_entries_lost_across_restart(self) -> None:
        first = EventLog(path=self.log_path)
        for i in range(10):
            first.append(Event(source_component=f"component-{i}", event_type=EventType.BELIEF_UPDATED))
        del first

        restarted = EventLog(path=self.log_path)

        self.assertEqual(len(restarted.read_all()), 10)

    def test_no_entries_overwritten_by_later_appends(self) -> None:
        first = EventLog(path=self.log_path)
        original = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        first.append(original)
        del first

        restarted = EventLog(path=self.log_path)
        restarted.append(Event(source_component="executive", event_type=EventType.PLAN_PROPOSED))

        first_entry = restarted.read_all()[0]
        self.assertEqual(first_entry, (1, original))

    def test_multiple_instances_reading_same_file_see_identical_history(self) -> None:
        writer = EventLog(path=self.log_path)
        writer.append(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))
        writer.append(Event(source_component="executive", event_type=EventType.PLAN_PROPOSED))

        reader_a = EventLog(path=self.log_path)
        reader_b = EventLog(path=self.log_path)

        self.assertEqual(reader_a.read_all(), reader_b.read_all())
        self.assertEqual(reader_a.latest_sequence(), reader_b.latest_sequence())
        self.assertEqual(reader_a.read_all(), writer.read_all())

    def test_append_flushes_to_disk_immediately(self) -> None:
        log = EventLog(path=self.log_path)
        log.append(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))

        raw_lines = self.log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(raw_lines), 1)

    def test_storage_format_is_one_json_line_per_event(self) -> None:
        log = EventLog(path=self.log_path)
        log.append(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))
        log.append(Event(source_component="executive", event_type=EventType.PLAN_PROPOSED))

        raw_lines = self.log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(raw_lines), 2)
        for line in raw_lines:
            json.loads(line)  # must not raise

    def test_read_all_after_restart_returns_copy_not_shared_reference(self) -> None:
        first = EventLog(path=self.log_path)
        first.append(Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED))
        del first

        restarted = EventLog(path=self.log_path)
        snapshot = restarted.read_all()
        snapshot.append((99, Event(source_component="rogue", event_type=EventType.BELIEF_UPDATED)))

        self.assertEqual(len(restarted.read_all()), 1)


if __name__ == "__main__":
    unittest.main()
