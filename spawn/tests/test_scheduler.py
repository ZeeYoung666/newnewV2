import unittest

from src.kernel import Scheduler


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


if __name__ == "__main__":
    unittest.main()
