import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import (
    ActionApprovedEvent,
    ActionAttemptedEvent,
    ActionFailedEvent,
    ActionSucceededEvent,
    ApprovalGrantedEvent,
    Event,
    EventType,
    PlanProposedEvent,
)
from src.executor import Action, ActionLog, ActionRecord, Executor, ToolRegistry
from src.kernel import Kernel


def publish_approval_granted(
    kernel: Kernel,
    *,
    plan_id: str = "plan-1",
    ordered_actions: tuple[str, ...] = ("investigate:opportunity-1", "act_on:opportunity-1"),
) -> None:
    kernel.publish(
        ApprovalGrantedEvent(
            source_component="governor",
            approval_id="approval-1",
            plan_id=plan_id,
            reason="within policy and budget",
            ordered_actions=ordered_actions,
        )
    )


class ActionModelTests(unittest.TestCase):
    def test_action_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        action = Action(
            action_id="action-1",
            plan_id="plan-1",
            action_type="investigate",
            parameters={"target": "opportunity-1"},
            created_at=now,
        )

        self.assertEqual(action.action_id, "action-1")
        self.assertEqual(action.plan_id, "plan-1")
        self.assertEqual(action.action_type, "investigate")
        self.assertEqual(action.parameters, {"target": "opportunity-1"})
        self.assertEqual(action.created_at, now)

    def test_action_is_immutable(self) -> None:
        action = Action(
            action_id="action-1",
            plan_id="plan-1",
            action_type="investigate",
            parameters={},
            created_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            action.action_type = "other"  # type: ignore[misc]


class ActionRecordModelTests(unittest.TestCase):
    def test_action_record_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        record = ActionRecord(
            record_id="record-1",
            action_id="action-1",
            status="succeeded",
            timestamp=now,
            result="ok",
            error=None,
        )

        self.assertEqual(record.record_id, "record-1")
        self.assertEqual(record.action_id, "action-1")
        self.assertEqual(record.status, "succeeded")
        self.assertEqual(record.timestamp, now)
        self.assertEqual(record.result, "ok")
        self.assertIsNone(record.error)

    def test_action_record_is_immutable(self) -> None:
        record = ActionRecord(
            record_id="record-1",
            action_id="action-1",
            status="succeeded",
            timestamp=datetime.now(timezone.utc),
            result="ok",
            error=None,
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.status = "failed"  # type: ignore[misc]


class ToolRegistryTests(unittest.TestCase):
    def test_register_and_get_tool(self) -> None:
        registry = ToolRegistry()
        tool = lambda action: "done"

        registry.register("investigate", tool)

        self.assertTrue(registry.is_registered("investigate"))
        self.assertIs(registry.get_tool("investigate"), tool)

    def test_is_registered_false_for_unknown_tool(self) -> None:
        registry = ToolRegistry()

        self.assertFalse(registry.is_registered("unknown"))

    def test_get_tool_raises_for_unknown_tool(self) -> None:
        registry = ToolRegistry()

        with self.assertRaises(KeyError):
            registry.get_tool("unknown")


class ActionLogTests(unittest.TestCase):
    def test_append_and_read_all(self) -> None:
        log = ActionLog()
        record = ActionRecord(
            record_id="record-1",
            action_id="action-1",
            status="succeeded",
            timestamp=datetime.now(timezone.utc),
            result="ok",
            error=None,
        )

        log.append(record)

        self.assertEqual(log.read_all(), [record])

    def test_read_all_returns_a_copy(self) -> None:
        log = ActionLog()
        record = ActionRecord(
            record_id="record-1",
            action_id="action-1",
            status="succeeded",
            timestamp=datetime.now(timezone.utc),
            result="ok",
            error=None,
        )
        log.append(record)

        snapshot = log.read_all()
        snapshot.append(record)

        self.assertEqual(len(log.read_all()), 1)

    def test_action_log_has_no_mutation_methods_other_than_append(self) -> None:
        log = ActionLog()

        self.assertFalse(hasattr(log, "update"))
        self.assertFalse(hasattr(log, "remove"))
        self.assertFalse(hasattr(log, "clear"))


class ExecutorOrderedExecutionTests(unittest.TestCase):
    def test_approved_plan_executes_actions_in_order(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        call_order: list[str] = []
        executor.tool_registry.register("investigate", lambda action: call_order.append("investigate") or "ok")
        executor.tool_registry.register("act_on", lambda action: call_order.append("act_on") or "ok")

        publish_approval_granted(kernel, plan_id="plan-1")

        self.assertEqual(call_order, ["investigate", "act_on"])
        records = executor.action_log.read_all()
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record.status == "succeeded" for record in records))

    def test_every_action_produces_an_action_record(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.tool_registry.register("investigate", lambda action: "result-a")
        executor.tool_registry.register("act_on", lambda action: "result-b")

        publish_approval_granted(kernel, plan_id="plan-1")

        records = executor.action_log.read_all()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].result, "result-a")
        self.assertEqual(records[1].result, "result-b")


class ExecutorEventEmissionTests(unittest.TestCase):
    def test_successful_action_emits_approved_attempted_and_succeeded(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.tool_registry.register("investigate", lambda action: "found-it")

        approved: list[Event] = []
        attempted: list[Event] = []
        succeeded: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_APPROVED, approved.append)
        kernel.register_subscriber(EventType.ACTION_ATTEMPTED, attempted.append)
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, succeeded.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        self.assertEqual(len(approved), 1)
        approved_event = approved[0]
        self.assertIsInstance(approved_event, ActionApprovedEvent)
        self.assertEqual(approved_event.plan_id, "plan-1")
        self.assertEqual(approved_event.action_type, "investigate")

        self.assertEqual(len(attempted), 1)
        attempted_event = attempted[0]
        self.assertIsInstance(attempted_event, ActionAttemptedEvent)
        self.assertEqual(attempted_event.action_id, approved_event.action_id)
        self.assertEqual(attempted_event.tool_name, "investigate")
        self.assertEqual(attempted_event.attempt, 1)

        self.assertEqual(len(succeeded), 1)
        succeeded_event = succeeded[0]
        self.assertIsInstance(succeeded_event, ActionSucceededEvent)
        self.assertEqual(succeeded_event.action_id, approved_event.action_id)
        self.assertEqual(succeeded_event.result, "found-it")

    def test_failing_action_records_failure_and_emits_action_failed(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)

        def failing_tool(action: Action) -> str:
            raise RuntimeError("boom")

        executor.tool_registry.register("risky", failing_tool)

        succeeded: list[Event] = []
        failed: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, succeeded.append)
        kernel.register_subscriber(EventType.ACTION_FAILED, failed.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("risky:target-1",))

        self.assertEqual(succeeded, [])
        self.assertEqual(len(failed), 1)
        failed_event = failed[0]
        self.assertIsInstance(failed_event, ActionFailedEvent)
        self.assertIn("boom", failed_event.error)

        records = executor.action_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "failed")
        self.assertIn("boom", records[0].error)
        self.assertIsNone(records[0].result)

    def test_unregistered_tool_is_recorded_and_emitted_as_failure(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)

        failed: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_FAILED, failed.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("unregistered_type:target-1",))

        self.assertEqual(len(failed), 1)
        records = executor.action_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "failed")
        self.assertIsNotNone(records[0].error)


class ExecutorAuthorityBoundaryTests(unittest.TestCase):
    def test_executor_never_executes_unapproved_plans(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.tool_registry.register("investigate", lambda action: "ok")

        kernel.publish(
            PlanProposedEvent(
                source_component="executive",
                plan_id="plan-1",
                opportunity_id="opportunity-1",
                rationale="test plan",
                expected_value=60.0,
                attention_cost=1.0,
                capital_cost=6.0,
                ordered_actions=("investigate:opportunity-1",),
            )
        )

        self.assertEqual(executor.action_log.read_all(), [])

    def test_executor_does_not_plan_or_approve(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)

        self.assertFalse(hasattr(executor, "propose_plan"))
        self.assertFalse(hasattr(executor, "approve"))


if __name__ == "__main__":
    unittest.main()
