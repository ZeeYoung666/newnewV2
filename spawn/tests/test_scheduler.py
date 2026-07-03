import tempfile
import unittest
from pathlib import Path

from src.events import BeliefCreatedEvent, EventType
from src.kernel import EventLog, Kernel, Scheduler


class SchedulerFifoTests(unittest.TestCase):
    def test_fifo_execution_order(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule(lambda: order.append("a"))
        scheduler.schedule(lambda: order.append("b"))
        scheduler.schedule(lambda: order.append("c"))
        scheduler.run_until_idle()

        self.assertEqual(order, ["a", "b", "c"])

    def test_deterministic_ordering_across_many_tasks(self) -> None:
        scheduler = Scheduler()
        order: list[int] = []

        for i in range(20):
            scheduler.schedule(lambda i=i: order.append(i))
        scheduler.run_until_idle()

        self.assertEqual(order, list(range(20)))


class SchedulerCancellationTests(unittest.TestCase):
    def test_cancellation_prevents_execution(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule(lambda: order.append("a"))
        cancelled_id = scheduler.schedule(lambda: order.append("b"))
        scheduler.schedule(lambda: order.append("c"))

        cancelled = scheduler.cancel(cancelled_id)
        scheduler.run_until_idle()

        self.assertTrue(cancelled)
        self.assertEqual(order, ["a", "c"])

    def test_cancel_returns_false_for_unknown_task_id(self) -> None:
        scheduler = Scheduler()

        self.assertFalse(scheduler.cancel(999))

    def test_cancel_returns_false_for_already_executed_task(self) -> None:
        scheduler = Scheduler()
        task_id = scheduler.schedule(lambda: None)
        scheduler.run_next()

        self.assertFalse(scheduler.cancel(task_id))

    def test_cancelled_task_does_not_count_as_pending(self) -> None:
        scheduler = Scheduler()
        task_id = scheduler.schedule(lambda: None)

        scheduler.cancel(task_id)

        self.assertEqual(scheduler.pending_count(), 0)


class SchedulerNestedSchedulingTests(unittest.TestCase):
    def test_nested_scheduling_queues_rather_than_recurses(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        def first() -> None:
            order.append("first")
            scheduler.schedule(lambda: order.append("nested"))

        scheduler.schedule(first)
        scheduler.schedule(lambda: order.append("second"))
        scheduler.run_until_idle()

        # "nested" is scheduled during first()'s execution but must run only
        # after the already-queued "second" — proving it was appended to the
        # back of the queue, not executed immediately/recursively.
        self.assertEqual(order, ["first", "second", "nested"])

    def test_scheduling_during_execution_does_not_run_synchronously(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        def outer() -> None:
            order.append("outer-start")
            scheduler.schedule(lambda: order.append("inner"))
            order.append("outer-end")

        scheduler.schedule(outer)
        scheduler.run_next()  # runs only `outer`; the nested task must not run inline

        self.assertEqual(order, ["outer-start", "outer-end"])
        self.assertEqual(scheduler.pending_count(), 1)

        scheduler.run_next()
        self.assertEqual(order, ["outer-start", "outer-end", "inner"])


class SchedulerRunNextTests(unittest.TestCase):
    def test_run_next_executes_exactly_once_per_call(self) -> None:
        scheduler = Scheduler()
        calls = {"count": 0}
        scheduler.schedule(lambda: calls.__setitem__("count", calls["count"] + 1))

        ran_first = scheduler.run_next()
        ran_second = scheduler.run_next()

        self.assertTrue(ran_first)
        self.assertFalse(ran_second)
        self.assertEqual(calls["count"], 1)

    def test_run_next_on_empty_scheduler_returns_false(self) -> None:
        scheduler = Scheduler()

        self.assertFalse(scheduler.run_next())


class SchedulerPendingCountTests(unittest.TestCase):
    def test_pending_count_tracks_queue_state(self) -> None:
        scheduler = Scheduler()
        self.assertEqual(scheduler.pending_count(), 0)

        scheduler.schedule(lambda: None)
        scheduler.schedule(lambda: None)
        self.assertEqual(scheduler.pending_count(), 2)

        scheduler.run_next()
        self.assertEqual(scheduler.pending_count(), 1)

        scheduler.run_until_idle()
        self.assertEqual(scheduler.pending_count(), 0)

    def test_run_until_idle_drains_all_pending_work(self) -> None:
        scheduler = Scheduler()
        for _ in range(10):
            scheduler.schedule(lambda: None)

        scheduler.run_until_idle()

        self.assertEqual(scheduler.pending_count(), 0)


class SchedulerTimerTests(unittest.TestCase):
    def test_timer_does_not_run_before_its_due_time(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(5, lambda: order.append("timed"))

        scheduler.run_until_idle()
        self.assertEqual(order, [])

        scheduler.advance_time(4)
        scheduler.run_until_idle()
        self.assertEqual(order, [])

        scheduler.advance_time(5)
        scheduler.run_until_idle()
        self.assertEqual(order, ["timed"])

    def test_timer_runs_when_time_advances_past_due_time(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(3, lambda: order.append("timed"))
        scheduler.advance_time(10)
        scheduler.run_until_idle()

        self.assertEqual(order, ["timed"])

    def test_timers_due_at_same_time_run_fifo(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(7, lambda: order.append("a"))
        scheduler.schedule_at(7, lambda: order.append("b"))
        scheduler.schedule_at(7, lambda: order.append("c"))
        scheduler.advance_time(7)
        scheduler.run_until_idle()

        self.assertEqual(order, ["a", "b", "c"])

    def test_timers_run_in_due_time_order_regardless_of_scheduling_order(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(9, lambda: order.append("late"))
        scheduler.schedule_at(3, lambda: order.append("early"))
        scheduler.schedule_at(6, lambda: order.append("middle"))
        scheduler.advance_time(9)
        scheduler.run_until_idle()

        self.assertEqual(order, ["early", "middle", "late"])

    def test_single_advance_releases_mixed_due_times_in_time_then_fifo_order(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(5, lambda: order.append("t5-first"))
        scheduler.schedule_at(2, lambda: order.append("t2"))
        scheduler.schedule_at(5, lambda: order.append("t5-second"))
        scheduler.advance_time(5)
        scheduler.run_until_idle()

        self.assertEqual(order, ["t2", "t5-first", "t5-second"])

    def test_already_due_timer_joins_the_back_of_the_ready_queue(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.advance_time(10)
        scheduler.schedule(lambda: order.append("immediate"))
        scheduler.schedule_at(10, lambda: order.append("due-now"))
        scheduler.schedule_at(4, lambda: order.append("past-due"))
        scheduler.run_until_idle()

        self.assertEqual(order, ["immediate", "due-now", "past-due"])

    def test_immediate_scheduling_is_unchanged_alongside_pending_timers(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(100, lambda: order.append("timed"))
        scheduler.schedule(lambda: order.append("a"))
        scheduler.schedule(lambda: order.append("b"))
        scheduler.run_until_idle()

        # Immediate work drains without any time advance, and the parked
        # timer neither runs nor blocks the queue from going idle.
        self.assertEqual(order, ["a", "b"])
        self.assertEqual(scheduler.pending_count(), 0)
        self.assertEqual(scheduler.timer_count(), 1)

    def test_released_timers_run_before_work_scheduled_after_the_advance(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(5, lambda: order.append("timed"))
        scheduler.advance_time(5)
        scheduler.schedule(lambda: order.append("later-immediate"))
        scheduler.run_until_idle()

        self.assertEqual(order, ["timed", "later-immediate"])

    def test_advance_time_only_readies_work_and_never_executes_it(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(1, lambda: order.append("timed"))
        scheduler.advance_time(1)

        self.assertEqual(order, [])
        self.assertEqual(scheduler.pending_count(), 1)

    def test_advance_time_backwards_raises(self) -> None:
        scheduler = Scheduler()
        scheduler.advance_time(10)

        with self.assertRaises(ValueError):
            scheduler.advance_time(9)

    def test_advance_time_to_the_current_time_is_a_no_op(self) -> None:
        scheduler = Scheduler()
        scheduler.advance_time(10)
        scheduler.advance_time(10)

        self.assertEqual(scheduler.now, 10)

    def test_now_starts_at_zero_and_tracks_advances(self) -> None:
        scheduler = Scheduler()
        self.assertEqual(scheduler.now, 0)

        scheduler.advance_time(3)
        self.assertEqual(scheduler.now, 3)

    def test_cancelling_a_pending_timer_prevents_execution(self) -> None:
        scheduler = Scheduler()
        order: list[str] = []

        scheduler.schedule_at(5, lambda: order.append("kept"))
        cancelled_id = scheduler.schedule_at(5, lambda: order.append("cancelled"))

        self.assertTrue(scheduler.cancel(cancelled_id))
        self.assertEqual(scheduler.timer_count(), 1)

        scheduler.advance_time(5)
        scheduler.run_until_idle()

        self.assertEqual(order, ["kept"])

    def test_next_due_time_reports_the_earliest_pending_timer(self) -> None:
        scheduler = Scheduler()
        self.assertIsNone(scheduler.next_due_time())

        scheduler.schedule_at(8, lambda: None)
        scheduler.schedule_at(3, lambda: None)

        self.assertEqual(scheduler.next_due_time(), 3)

    def test_timer_and_immediate_task_ids_share_one_counter(self) -> None:
        scheduler = Scheduler()

        first = scheduler.schedule(lambda: None)
        second = scheduler.schedule_at(5, lambda: None)
        third = scheduler.schedule(lambda: None)

        self.assertEqual([first, second, third], [first, first + 1, first + 2])


class SchedulerTimerReplayTests(unittest.TestCase):
    """Timers fired through the Kernel leave an ordinary event log, so replay
    stays deterministic: the log records the order timers actually fired in,
    and replay re-dispatches that order without needing any clock at all.
    """

    def setUp(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.log_path = Path(tmpdir.name) / "events.jsonl"

    def _belief_event(self, belief_id: str) -> BeliefCreatedEvent:
        return BeliefCreatedEvent(
            source_component="test",
            belief_id=belief_id,
            claim=f"claim-{belief_id}",
            confidence=0.5,
            provenance="timer-test",
        )

    def _run_with_timers(self) -> Kernel:
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        kernel.start()
        kernel.scheduler.schedule_at(20, lambda: kernel.publish(self._belief_event("late")))
        kernel.scheduler.schedule_at(10, lambda: kernel.publish(self._belief_event("early-first")))
        kernel.scheduler.schedule_at(10, lambda: kernel.publish(self._belief_event("early-second")))
        kernel.publish(self._belief_event("immediate"))
        kernel.run_until_idle()
        kernel.scheduler.advance_time(10)
        kernel.run_until_idle()
        kernel.scheduler.advance_time(20)
        kernel.run_until_idle()
        kernel.stop()
        return kernel

    def _replayed_belief_order(self) -> list[str]:
        observed: list[str] = []
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        kernel.register_subscriber(
            EventType.BELIEF_CREATED,
            lambda event: observed.append(event.belief_id),  # type: ignore[attr-defined]
        )
        kernel.replay()
        return observed

    def test_log_records_timer_firing_order(self) -> None:
        self._run_with_timers()

        log = EventLog(path=self.log_path)
        belief_order = [
            event.belief_id  # type: ignore[attr-defined]
            for _, event in log.read_all()
            if event.event_type is EventType.BELIEF_CREATED
        ]

        self.assertEqual(belief_order, ["immediate", "early-first", "early-second", "late"])

    def test_replay_reproduces_timer_driven_event_order(self) -> None:
        self._run_with_timers()

        self.assertEqual(
            self._replayed_belief_order(),
            ["immediate", "early-first", "early-second", "late"],
        )

    def test_replay_of_timer_driven_log_is_deterministic_across_restarts(self) -> None:
        self._run_with_timers()

        first_replay = self._replayed_belief_order()
        second_replay = self._replayed_belief_order()

        self.assertEqual(first_replay, second_replay)
        self.assertEqual(len(first_replay), 4)


if __name__ == "__main__":
    unittest.main()
