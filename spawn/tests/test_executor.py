import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import (
    ActionApprovedEvent,
    ActionAttemptedEvent,
    ActionFailedEvent,
    ActionRetryExhaustedEvent,
    ActionRetryScheduledEvent,
    ActionRetryStartedEvent,
    ActionSucceededEvent,
    ApprovalGrantedEvent,
    CredentialRegisteredEvent,
    CredentialRevokedEvent,
    CredentialUpdatedEvent,
    Event,
    EventType,
    PlanProposedEvent,
    SandboxExecutionCompletedEvent,
    SandboxExecutionStartedEvent,
)
from src.executor import (
    Action,
    ActionLog,
    ActionRecord,
    Credential,
    CredentialStore,
    Executor,
    LocalSandbox,
    RetryableError,
    RetryLog,
    RetryManager,
    RetryPolicy,
    RetryRecord,
    SandboxExecutionLog,
    SandboxExecutionRecord,
    ToolRegistry,
)
from src.kernel import EventLog, Kernel


class RecordingSandbox:
    """Test double: records every tool it's asked to run, then delegates to it."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Action]] = []

    def execute(self, tool, action: Action) -> object:
        self.calls.append((action.action_type, action))
        return tool(action)


class FailingSandbox:
    """Test double: every execution raises, simulating a sandbox boundary failure."""

    def execute(self, tool, action: Action) -> object:
        raise RuntimeError("sandbox boundary violation")


class FlakyTool:
    """Test double: raises RetryableError for its first `fail_times` calls, then succeeds."""

    def __init__(self, fail_times: int, result: str = "ok") -> None:
        self.fail_times = fail_times
        self.result = result
        self.calls = 0

    def __call__(self, action: Action) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RetryableError(f"transient failure #{self.calls}")
        return self.result


class AlwaysFlakyTool:
    """Test double: always raises RetryableError, simulating an exhausted retry budget."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, action: Action) -> str:
        self.calls += 1
        raise RetryableError(f"transient failure #{self.calls}")


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


class SandboxExecutionRecordModelTests(unittest.TestCase):
    def test_sandbox_execution_record_carries_required_fields(self) -> None:
        started_at = datetime.now(timezone.utc)
        completed_at = datetime.now(timezone.utc)
        record = SandboxExecutionRecord(
            execution_id="execution-1",
            action_id="action-1",
            action_type="investigate",
            status="succeeded",
            started_at=started_at,
            completed_at=completed_at,
            result="ok",
        )

        self.assertEqual(record.execution_id, "execution-1")
        self.assertEqual(record.action_id, "action-1")
        self.assertEqual(record.action_type, "investigate")
        self.assertEqual(record.status, "succeeded")
        self.assertEqual(record.started_at, started_at)
        self.assertEqual(record.completed_at, completed_at)
        self.assertEqual(record.result, "ok")
        self.assertIsNone(record.error)

    def test_sandbox_execution_record_is_immutable(self) -> None:
        record = SandboxExecutionRecord(
            execution_id="execution-1",
            action_id="action-1",
            action_type="investigate",
            status="started",
            started_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.status = "succeeded"  # type: ignore[misc]


class SandboxExecutionLogTests(unittest.TestCase):
    def test_append_read_all_and_history_for(self) -> None:
        log = SandboxExecutionLog()
        started = SandboxExecutionRecord(
            execution_id="execution-1",
            action_id="action-1",
            action_type="investigate",
            status="started",
            started_at=datetime.now(timezone.utc),
        )
        completed = SandboxExecutionRecord(
            execution_id="execution-1",
            action_id="action-1",
            action_type="investigate",
            status="succeeded",
            started_at=started.started_at,
            completed_at=datetime.now(timezone.utc),
            result="ok",
        )

        log.append(started)
        log.append(completed)

        self.assertEqual(log.read_all(), [started, completed])
        self.assertEqual(log.history_for("execution-1"), [started, completed])
        self.assertEqual(log.history_for("no-such-execution"), [])


class LocalSandboxTests(unittest.TestCase):
    def test_local_sandbox_executes_the_tool_and_returns_its_result(self) -> None:
        sandbox = LocalSandbox()
        action = Action(action_id="action-1", plan_id="plan-1", action_type="investigate", parameters={})

        result = sandbox.execute(lambda a: f"ran {a.action_type}", action)

        self.assertEqual(result, "ran investigate")

    def test_local_sandbox_propagates_tool_exceptions(self) -> None:
        sandbox = LocalSandbox()
        action = Action(action_id="action-1", plan_id="plan-1", action_type="risky", parameters={})

        def boom(a: Action) -> str:
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            sandbox.execute(boom, action)


class ExecutorSandboxIntegrationTests(unittest.TestCase):
    def test_default_executor_uses_local_sandbox(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)

        self.assertIsInstance(executor._sandbox, LocalSandbox)

    def test_every_tool_executes_through_the_sandbox(self) -> None:
        kernel = Kernel()
        sandbox = RecordingSandbox()
        executor = Executor(kernel, sandbox=sandbox)
        executor.tool_registry.register("investigate", lambda action: "result-a")
        executor.tool_registry.register("act_on", lambda action: "result-b")

        publish_approval_granted(kernel, plan_id="plan-1")

        self.assertEqual([action_type for action_type, _ in sandbox.calls], ["investigate", "act_on"])
        records = executor.action_log.read_all()
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record.status == "succeeded" for record in records))

    def test_sandbox_start_and_completion_events_are_emitted(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.tool_registry.register("investigate", lambda action: "found-it")

        started: list[Event] = []
        completed: list[Event] = []
        kernel.register_subscriber(EventType.SANDBOX_EXECUTION_STARTED, started.append)
        kernel.register_subscriber(EventType.SANDBOX_EXECUTION_COMPLETED, completed.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        self.assertEqual(len(started), 1)
        started_event = started[0]
        self.assertIsInstance(started_event, SandboxExecutionStartedEvent)
        self.assertEqual(started_event.action_type, "investigate")

        self.assertEqual(len(completed), 1)
        completed_event = completed[0]
        self.assertIsInstance(completed_event, SandboxExecutionCompletedEvent)
        self.assertEqual(completed_event.execution_id, started_event.execution_id)
        self.assertEqual(completed_event.action_id, started_event.action_id)
        self.assertEqual(completed_event.status, "succeeded")
        self.assertEqual(completed_event.result, "found-it")

        history = executor.sandbox_execution_log.history_for(started_event.execution_id)
        self.assertEqual([record.status for record in history], ["started", "succeeded"])

    def test_sandbox_failure_becomes_action_failed_event(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel, sandbox=FailingSandbox())
        executor.tool_registry.register("investigate", lambda action: "unreachable")

        failed: list[Event] = []
        completed: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_FAILED, failed.append)
        kernel.register_subscriber(EventType.SANDBOX_EXECUTION_COMPLETED, completed.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        self.assertEqual(len(failed), 1)
        self.assertIsInstance(failed[0], ActionFailedEvent)
        self.assertIn("sandbox boundary violation", failed[0].error)

        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].status, "failed")
        self.assertIn("sandbox boundary violation", completed[0].error)

        records = executor.action_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "failed")
        self.assertIn("sandbox boundary violation", records[0].error)

    def test_unregistered_tool_never_reaches_the_sandbox(self) -> None:
        kernel = Kernel()
        sandbox = RecordingSandbox()
        executor = Executor(kernel, sandbox=sandbox)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("unregistered_type:target-1",))

        self.assertEqual(sandbox.calls, [])
        records = executor.action_log.read_all()
        self.assertEqual(records[0].status, "failed")

    def test_existing_executor_events_still_emitted_unchanged_alongside_sandbox_events(self) -> None:
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
        self.assertEqual(len(attempted), 1)
        self.assertEqual(len(succeeded), 1)
        self.assertEqual(attempted[0].attempt, 1)


class ExecutorSandboxReplayTests(unittest.TestCase):
    def test_replay_reconstructs_sandbox_execution_history(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        executor = Executor(kernel)
        executor.tool_registry.register("investigate", lambda action: "found-it")
        executor.tool_registry.register("risky", lambda action: (_ for _ in ()).throw(RuntimeError("boom")))

        publish_approval_granted(
            kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1", "risky:target-1")
        )

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_executor = Executor(rebuilt_kernel)
        rebuilt_executor.tool_registry.register("investigate", lambda action: "found-it")
        rebuilt_executor.tool_registry.register("risky", lambda action: (_ for _ in ()).throw(RuntimeError("boom")))
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_executor.sandbox_execution_log.read_all(), executor.sandbox_execution_log.read_all()
        )
        statuses = [record.status for record in rebuilt_executor.sandbox_execution_log.read_all()]
        self.assertEqual(statuses, ["started", "succeeded", "started", "failed"])
        self.assertEqual(rebuilt_executor._pending_sandbox_executions, {})


class ExecutorSandboxSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_sandbox_state(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.tool_registry.register("investigate", lambda action: "found-it")

        started: list[SandboxExecutionStartedEvent] = []
        kernel.register_subscriber(EventType.SANDBOX_EXECUTION_STARTED, started.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))
        execution_id = started[0].execution_id
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_executor = Executor(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored = {
            record.execution_id: record for record in rebuilt_executor.sandbox_execution_log.read_all()
        }
        self.assertEqual(restored[execution_id].status, "succeeded")
        self.assertEqual(restored[execution_id].result, "found-it")
        self.assertNotIn(execution_id, rebuilt_executor._pending_sandbox_executions)


class RetryPolicyModelTests(unittest.TestCase):
    def test_default_retry_policy_allows_no_retries(self) -> None:
        policy = RetryPolicy()

        self.assertEqual(policy.max_attempts, 1)

    def test_retry_policy_carries_max_attempts(self) -> None:
        policy = RetryPolicy(max_attempts=3)

        self.assertEqual(policy.max_attempts, 3)

    def test_retry_policy_is_immutable(self) -> None:
        policy = RetryPolicy(max_attempts=3)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            policy.max_attempts = 5  # type: ignore[misc]

    def test_action_carries_a_retry_policy_defaulting_to_no_retries(self) -> None:
        action = Action(action_id="action-1", plan_id="plan-1", action_type="investigate", parameters={})

        self.assertEqual(action.retry_policy, RetryPolicy(max_attempts=1))

    def test_action_can_be_constructed_with_an_explicit_retry_policy(self) -> None:
        action = Action(
            action_id="action-1",
            plan_id="plan-1",
            action_type="investigate",
            parameters={},
            retry_policy=RetryPolicy(max_attempts=3),
        )

        self.assertEqual(action.retry_policy.max_attempts, 3)


class RetryRecordModelTests(unittest.TestCase):
    def test_retry_record_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        record = RetryRecord(
            action_id="action-1",
            action_type="investigate",
            attempt=2,
            status="started",
            timestamp=now,
        )

        self.assertEqual(record.action_id, "action-1")
        self.assertEqual(record.action_type, "investigate")
        self.assertEqual(record.attempt, 2)
        self.assertEqual(record.status, "started")
        self.assertEqual(record.timestamp, now)
        self.assertIsNone(record.error)

    def test_retry_record_is_immutable(self) -> None:
        record = RetryRecord(
            action_id="action-1",
            action_type="investigate",
            attempt=1,
            status="scheduled",
            timestamp=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.status = "started"  # type: ignore[misc]


class RetryLogTests(unittest.TestCase):
    def test_append_read_all_and_history_for(self) -> None:
        log = RetryLog()
        scheduled = RetryRecord(
            action_id="action-1", action_type="investigate", attempt=2, status="scheduled",
            timestamp=datetime.now(timezone.utc), error="transient failure #1",
        )
        started = RetryRecord(
            action_id="action-1", action_type="investigate", attempt=2, status="started",
            timestamp=datetime.now(timezone.utc),
        )

        log.append(scheduled)
        log.append(started)

        self.assertEqual(log.read_all(), [scheduled, started])
        self.assertEqual(log.history_for("action-1"), [scheduled, started])
        self.assertEqual(log.history_for("no-such-action"), [])


class RetryManagerTests(unittest.TestCase):
    def test_get_policy_defaults_to_no_retries_when_unregistered(self) -> None:
        manager = RetryManager()

        self.assertEqual(manager.get_policy("investigate").max_attempts, 1)

    def test_register_policy_overrides_default(self) -> None:
        manager = RetryManager()
        manager.register_policy("investigate", RetryPolicy(max_attempts=3))

        self.assertEqual(manager.get_policy("investigate").max_attempts, 3)
        self.assertEqual(manager.get_policy("act_on").max_attempts, 1)


class ExecutorRetryTests(unittest.TestCase):
    def test_retryable_failure_retries_and_eventually_succeeds(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.retry_manager.register_policy("investigate", RetryPolicy(max_attempts=3))
        tool = FlakyTool(fail_times=2, result="found-it")
        executor.tool_registry.register("investigate", tool)

        succeeded: list[Event] = []
        failed: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, succeeded.append)
        kernel.register_subscriber(EventType.ACTION_FAILED, failed.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        self.assertEqual(tool.calls, 3)
        self.assertEqual(failed, [])
        self.assertEqual(len(succeeded), 1)
        self.assertEqual(succeeded[0].result, "found-it")

        records = executor.action_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "succeeded")
        self.assertEqual(records[0].result, "found-it")

    def test_non_retryable_failure_never_retries(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.retry_manager.register_policy("risky", RetryPolicy(max_attempts=3))

        calls = 0

        def always_plain_failure(action: Action) -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("permanent failure")

        executor.tool_registry.register("risky", always_plain_failure)

        failed: list[Event] = []
        scheduled: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_FAILED, failed.append)
        kernel.register_subscriber(EventType.ACTION_RETRY_SCHEDULED, scheduled.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("risky:target-1",))

        self.assertEqual(calls, 1)
        self.assertEqual(scheduled, [])
        self.assertEqual(len(failed), 1)
        self.assertIn("permanent failure", failed[0].error)

    def test_retry_limit_is_enforced_and_emits_exhausted_event(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.retry_manager.register_policy("investigate", RetryPolicy(max_attempts=3))
        tool = AlwaysFlakyTool()
        executor.tool_registry.register("investigate", tool)

        failed: list[Event] = []
        exhausted: list[Event] = []
        succeeded: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_FAILED, failed.append)
        kernel.register_subscriber(EventType.ACTION_RETRY_EXHAUSTED, exhausted.append)
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, succeeded.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        self.assertEqual(tool.calls, 3)
        self.assertEqual(succeeded, [])
        self.assertEqual(len(failed), 1)
        self.assertIn("transient failure #3", failed[0].error)

        self.assertEqual(len(exhausted), 1)
        self.assertIsInstance(exhausted[0], ActionRetryExhaustedEvent)
        self.assertEqual(exhausted[0].attempts_made, 3)
        self.assertEqual(exhausted[0].max_attempts, 3)

        records = executor.action_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, "failed")

    def test_retries_execute_through_the_sandbox(self) -> None:
        kernel = Kernel()
        sandbox = RecordingSandbox()
        executor = Executor(kernel, sandbox=sandbox)
        executor.retry_manager.register_policy("investigate", RetryPolicy(max_attempts=3))
        tool = FlakyTool(fail_times=2, result="found-it")
        executor.tool_registry.register("investigate", tool)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        self.assertEqual(len(sandbox.calls), 3)
        self.assertTrue(all(action_type == "investigate" for action_type, _ in sandbox.calls))

    def test_retry_scheduled_and_started_events_carry_deterministic_attempt_order(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.retry_manager.register_policy("investigate", RetryPolicy(max_attempts=3))
        tool = FlakyTool(fail_times=2, result="found-it")
        executor.tool_registry.register("investigate", tool)

        scheduled: list[ActionRetryScheduledEvent] = []
        started: list[ActionRetryStartedEvent] = []
        attempted: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_RETRY_SCHEDULED, scheduled.append)
        kernel.register_subscriber(EventType.ACTION_RETRY_STARTED, started.append)
        kernel.register_subscriber(EventType.ACTION_ATTEMPTED, attempted.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        self.assertEqual([event.attempt for event in scheduled], [1, 2])
        self.assertEqual([event.next_attempt for event in scheduled], [2, 3])
        self.assertEqual([event.attempt for event in started], [2, 3])
        self.assertEqual([event.attempt for event in attempted], [1, 2, 3])

        history = executor.retry_manager.retry_log.history_for(scheduled[0].action_id)
        self.assertEqual(
            [(record.status, record.attempt) for record in history],
            [("scheduled", 2), ("started", 2), ("scheduled", 3), ("started", 3)],
        )

    def test_retries_across_multiple_actions_do_not_interleave(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.retry_manager.register_policy("investigate", RetryPolicy(max_attempts=3))
        executor.retry_manager.register_policy("act_on", RetryPolicy(max_attempts=3))
        first_tool = FlakyTool(fail_times=1, result="first-done")
        second_tool = FlakyTool(fail_times=1, result="second-done")
        executor.tool_registry.register("investigate", first_tool)
        executor.tool_registry.register("act_on", second_tool)

        succeeded: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, succeeded.append)

        publish_approval_granted(
            kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1", "act_on:opportunity-1")
        )

        # Each action's own retry sequence resolves fully before the next action starts.
        self.assertEqual(len(succeeded), 2)
        self.assertEqual(succeeded[0].result, "first-done")
        self.assertEqual(succeeded[1].result, "second-done")
        self.assertEqual(first_tool.calls, 2)
        self.assertEqual(second_tool.calls, 2)


class ExecutorRetryReplayTests(unittest.TestCase):
    def test_replay_reconstructs_retry_state(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        executor = Executor(kernel)
        executor.retry_manager.register_policy("investigate", RetryPolicy(max_attempts=3))
        executor.tool_registry.register("investigate", FlakyTool(fail_times=2, result="found-it"))

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_executor = Executor(rebuilt_kernel)
        rebuilt_executor.retry_manager.register_policy("investigate", RetryPolicy(max_attempts=3))
        rebuilt_executor.tool_registry.register("investigate", FlakyTool(fail_times=2, result="found-it"))
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_executor.retry_manager.retry_log.read_all(), executor.retry_manager.retry_log.read_all()
        )
        statuses = [record.status for record in rebuilt_executor.retry_manager.retry_log.read_all()]
        self.assertEqual(statuses, ["scheduled", "started", "scheduled", "started"])

        # action_log identity isn't replay-stable (action_id is freshly minted per
        # execution, same precedent as Governor's approval_log) — assert behavior instead.
        rebuilt_records = rebuilt_executor.action_log.read_all()
        self.assertEqual(len(rebuilt_records), 1)
        self.assertEqual(rebuilt_records[0].status, "succeeded")
        self.assertEqual(rebuilt_records[0].result, "found-it")


class ExecutorRetrySnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_retry_state(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.retry_manager.register_policy("investigate", RetryPolicy(max_attempts=3))
        executor.tool_registry.register("investigate", FlakyTool(fail_times=2, result="found-it"))

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_executor = Executor(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored_records = rebuilt_executor.retry_manager.retry_log.read_all()
        self.assertEqual(len(restored_records), 4)
        self.assertEqual(
            [record.status for record in restored_records], ["scheduled", "started", "scheduled", "started"]
        )
        self.assertEqual(rebuilt_executor.action_log.read_all(), executor.action_log.read_all())


class CredentialModelTests(unittest.TestCase):
    def test_credential_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        credential = Credential(
            credential_id="credential-1",
            action_type="send_email",
            value="secret-token",
            status="active",
            updated_at=now,
        )

        self.assertEqual(credential.credential_id, "credential-1")
        self.assertEqual(credential.action_type, "send_email")
        self.assertEqual(credential.value, "secret-token")
        self.assertEqual(credential.status, "active")
        self.assertEqual(credential.updated_at, now)

    def test_credential_is_immutable(self) -> None:
        credential = Credential(
            credential_id="credential-1",
            action_type="send_email",
            value="secret-token",
            status="active",
            updated_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            credential.status = "revoked"  # type: ignore[misc]


class CredentialStoreTests(unittest.TestCase):
    def test_put_get_exists_and_read_all(self) -> None:
        store = CredentialStore()
        credential = Credential(
            credential_id="credential-1",
            action_type="send_email",
            value="secret-token",
            status="active",
            updated_at=datetime.now(timezone.utc),
        )

        store.put(credential)

        self.assertTrue(store.exists("send_email"))
        self.assertEqual(store.get("send_email"), credential)
        self.assertEqual(store.read_all(), [credential])

    def test_get_raises_for_unknown_action_type(self) -> None:
        store = CredentialStore()

        with self.assertRaises(KeyError):
            store.get("unknown")

    def test_get_active_raises_keyerror_when_never_registered(self) -> None:
        store = CredentialStore()

        with self.assertRaises(KeyError):
            store.get_active("send_email")

    def test_get_active_raises_lookuperror_when_revoked(self) -> None:
        store = CredentialStore()
        store.put(
            Credential(
                credential_id="credential-1",
                action_type="send_email",
                value="secret-token",
                status="revoked",
                updated_at=datetime.now(timezone.utc),
            )
        )

        with self.assertRaises(LookupError):
            store.get_active("send_email")

    def test_is_required_true_once_a_credential_is_registered(self) -> None:
        store = CredentialStore()
        self.assertFalse(store.is_required("send_email"))

        store.put(
            Credential(
                credential_id="credential-1",
                action_type="send_email",
                value="secret-token",
                status="active",
                updated_at=datetime.now(timezone.utc),
            )
        )

        self.assertTrue(store.is_required("send_email"))

    def test_require_marks_action_type_required_without_a_value(self) -> None:
        store = CredentialStore()
        store.require("send_email")

        self.assertTrue(store.is_required("send_email"))
        self.assertFalse(store.exists("send_email"))


class ExecutorCredentialInjectionTests(unittest.TestCase):
    def test_correct_credential_is_injected_for_tool_execution(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        received: list[str] = []

        def send_email(action: Action, credential: str) -> str:
            received.append(credential)
            return f"sent using {credential}"

        executor.tool_registry.register("send_email", send_email)
        executor.register_credential(action_type="send_email", value="api-key-123")

        succeeded: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, succeeded.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("send_email:owner",))

        self.assertEqual(received, ["api-key-123"])
        self.assertEqual(len(succeeded), 1)
        self.assertEqual(succeeded[0].result, "sent using api-key-123")

    def test_action_types_without_a_credential_execute_unaffected(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.tool_registry.register("investigate", lambda action: "found-it")

        succeeded: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, succeeded.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1",))

        self.assertEqual(len(succeeded), 1)
        self.assertEqual(succeeded[0].result, "found-it")

    def test_missing_credential_fails_before_sandbox_execution(self) -> None:
        kernel = Kernel()
        sandbox = RecordingSandbox()
        executor = Executor(kernel, sandbox=sandbox)
        executor.require_credential("send_email")
        executor.tool_registry.register("send_email", lambda action, credential: "unreachable")

        failed: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_FAILED, failed.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("send_email:owner",))

        self.assertEqual(sandbox.calls, [])
        self.assertEqual(len(failed), 1)
        self.assertIn("no credential registered", failed[0].error)

        records = executor.action_log.read_all()
        self.assertEqual(records[0].status, "failed")

    def test_revoked_credential_cannot_be_used(self) -> None:
        kernel = Kernel()
        sandbox = RecordingSandbox()
        executor = Executor(kernel, sandbox=sandbox)
        executor.tool_registry.register("send_email", lambda action, credential: "unreachable")
        executor.register_credential(action_type="send_email", value="api-key-123")
        executor.revoke_credential("send_email")

        failed: list[Event] = []
        kernel.register_subscriber(EventType.ACTION_FAILED, failed.append)

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("send_email:owner",))

        self.assertEqual(sandbox.calls, [])
        self.assertEqual(len(failed), 1)
        self.assertIn("revoked", failed[0].error)

    def test_credential_update_affects_future_executions_only(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        received: list[str] = []

        def send_email(action: Action, credential: str) -> str:
            received.append(credential)
            return "sent"

        executor.tool_registry.register("send_email", send_email)
        executor.register_credential(action_type="send_email", value="old-key")

        publish_approval_granted(kernel, plan_id="plan-1", ordered_actions=("send_email:owner",))

        executor.update_credential("send_email", value="new-key")

        publish_approval_granted(kernel, plan_id="plan-2", ordered_actions=("send_email:owner",))

        self.assertEqual(received, ["old-key", "new-key"])

    def test_register_update_and_revoke_raise_for_unregistered_action_type(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)

        with self.assertRaises(KeyError):
            executor.update_credential("send_email", value="new-key")

        with self.assertRaises(KeyError):
            executor.revoke_credential("send_email")

    def test_registration_update_and_revocation_events_are_emitted(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.tool_registry.register("send_email", lambda action, credential: "sent")

        registered: list[Event] = []
        updated: list[Event] = []
        revoked: list[Event] = []
        kernel.register_subscriber(EventType.CREDENTIAL_REGISTERED, registered.append)
        kernel.register_subscriber(EventType.CREDENTIAL_UPDATED, updated.append)
        kernel.register_subscriber(EventType.CREDENTIAL_REVOKED, revoked.append)

        credential_id = executor.register_credential(action_type="send_email", value="key-1")
        executor.update_credential("send_email", value="key-2")
        executor.revoke_credential("send_email")

        self.assertEqual(len(registered), 1)
        self.assertIsInstance(registered[0], CredentialRegisteredEvent)
        self.assertEqual(registered[0].credential_id, credential_id)

        self.assertEqual(len(updated), 1)
        self.assertIsInstance(updated[0], CredentialUpdatedEvent)
        self.assertEqual(updated[0].value, "key-2")

        self.assertEqual(len(revoked), 1)
        self.assertIsInstance(revoked[0], CredentialRevokedEvent)

        credential = executor.credential_store.get("send_email")
        self.assertEqual(credential.status, "revoked")
        self.assertEqual(credential.value, "key-2")


class ExecutorCredentialReplayTests(unittest.TestCase):
    def test_replay_reconstructs_credential_state(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        executor = Executor(kernel)
        executor.tool_registry.register("send_email", lambda action, credential: "sent")

        executor.register_credential(action_type="send_email", value="key-1")
        executor.update_credential("send_email", value="key-2")
        executor.register_credential(action_type="log_event", value="log-key")
        executor.revoke_credential("log_event")

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_executor = Executor(rebuilt_kernel)
        rebuilt_executor.tool_registry.register("send_email", lambda action, credential: "sent")
        rebuilt_kernel.replay()

        send_email_credential = rebuilt_executor.credential_store.get("send_email")
        self.assertEqual(send_email_credential.status, "active")
        self.assertEqual(send_email_credential.value, "key-2")

        log_event_credential = rebuilt_executor.credential_store.get("log_event")
        self.assertEqual(log_event_credential.status, "revoked")
        self.assertEqual(log_event_credential.value, "log-key")


class ExecutorCredentialSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_credential_state(self) -> None:
        kernel = Kernel()
        executor = Executor(kernel)
        executor.tool_registry.register("send_email", lambda action, credential: "sent")

        executor.register_credential(action_type="send_email", value="key-1")
        executor.update_credential("send_email", value="key-2")
        executor.register_credential(action_type="log_event", value="log-key")
        executor.revoke_credential("log_event")
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_executor = Executor(rebuilt_kernel)
        rebuilt_kernel.replay()

        send_email_credential = rebuilt_executor.credential_store.get("send_email")
        self.assertEqual(send_email_credential.status, "active")
        self.assertEqual(send_email_credential.value, "key-2")

        log_event_credential = rebuilt_executor.credential_store.get("log_event")
        self.assertEqual(log_event_credential.status, "revoked")
        self.assertEqual(log_event_credential.value, "log-key")


if __name__ == "__main__":
    unittest.main()
