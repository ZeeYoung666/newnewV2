"""Executor: translates approved plans into actions and dispatches them through tools.

Owns the tool registry and action log. The Executor executes only — it never
plans and never approves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol
from uuid import uuid4

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
    EventType,
    SandboxExecutionCompletedEvent,
    SandboxExecutionStartedEvent,
)
from src.kernel import Kernel

Tool = Callable[["Action"], object]
CredentialedTool = Callable[["Action", str], object]


def _bind_credential(tool: CredentialedTool, value: str) -> Tool:
    """Wrap a credentialed tool into the plain `Tool` shape the Sandbox expects.

    The credential value is bound into this one closure, scoped to a single
    execution — the Sandbox only ever sees the resulting callable, never
    the credential itself, and never anything persisted.
    """
    return lambda action: tool(action, value)


class RetryableError(Exception):
    """Raised by a tool to mark a failure as transient and retry-eligible.

    Any other exception type is treated as permanent: it is never retried,
    no matter what the action's RetryPolicy allows. Retryability is decided
    solely by this marker, never by inspecting the error message or type.
    """


@dataclass(slots=True, kw_only=True, frozen=True)
class RetryPolicy:
    """Deterministic retry budget: how many attempts an action gets in total.

    `max_attempts=1` (the default) means no retries — the existing,
    unchanged behavior for any action whose type has no policy registered.
    """

    max_attempts: int = 1


@dataclass(slots=True, kw_only=True, frozen=True)
class Action:
    """A single unit of work translated from an approved plan step."""

    action_id: str
    plan_id: str
    action_type: str
    parameters: dict[str, str]
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class ActionRecord:
    """An immutable audit trail entry for a single execution attempt."""

    record_id: str
    action_id: str
    status: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result: Optional[str] = None
    error: Optional[str] = None


class ToolRegistry:
    """Maps action types to the tool callables that execute them."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, action_type: str, tool: Tool) -> None:
        self._tools[action_type] = tool

    def get_tool(self, action_type: str) -> Tool:
        return self._tools[action_type]

    def is_registered(self, action_type: str) -> bool:
        return action_type in self._tools


class ActionLog:
    """Append-only log of action records."""

    def __init__(self) -> None:
        self._records: list[ActionRecord] = []

    def append(self, record: ActionRecord) -> None:
        self._records.append(record)

    def read_all(self) -> list[ActionRecord]:
        return list(self._records)


@dataclass(slots=True, kw_only=True, frozen=True)
class SandboxExecutionRecord:
    """An immutable audit trail entry for one sandboxed tool invocation.

    One record is appended per transition (started, then succeeded or
    failed) — never mutated — mirroring the Governor's Amendment/Escalation
    record shape, so the full history survives in SandboxExecutionLog even
    though `status` only ever describes that single transition.
    """

    execution_id: str
    action_id: str
    action_type: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None


class SandboxExecutionLog:
    """Append-only log of sandbox execution lifecycle transitions.

    An execution_id can appear more than once (started, then succeeded or
    failed) — read_all() returns every transition ever recorded, in order.
    """

    def __init__(self) -> None:
        self._records: list[SandboxExecutionRecord] = []

    def append(self, record: SandboxExecutionRecord) -> None:
        self._records.append(record)

    def read_all(self) -> list[SandboxExecutionRecord]:
        return list(self._records)

    def history_for(self, execution_id: str) -> list[SandboxExecutionRecord]:
        """All transitions recorded for a single execution, in order."""
        return [record for record in self._records if record.execution_id == execution_id]


class Sandbox(Protocol):
    """Controlled execution boundary a tool invocation runs through.

    Receives only the tool callable and the action being run — never plan,
    approval, or any other component's state — so it can never make a
    decision based on anything but the call it was asked to make.
    """

    def execute(self, tool: Tool, action: "Action") -> object:
        """Run `tool(action)` inside the sandbox boundary, returning its result or raising."""
        ...


class LocalSandbox:
    """Default deterministic sandbox: runs the tool in-process, synchronously.

    No isolation beyond a controlled call boundary — real process/container
    isolation is a future extension behind this same interface.
    """

    def execute(self, tool: Tool, action: "Action") -> object:
        return tool(action)


@dataclass(slots=True, kw_only=True, frozen=True)
class RetryRecord:
    """An immutable audit trail entry for one retry lifecycle transition.

    One record is appended per transition (scheduled, started, then
    succeeded or exhausted) — never mutated — mirroring SandboxExecutionRecord's
    shape, so the full history survives in RetryLog.
    """

    action_id: str
    action_type: str
    attempt: int
    status: str
    timestamp: datetime
    error: Optional[str] = None


class RetryLog:
    """Append-only log of retry lifecycle transitions.

    An action_id can appear more than once (scheduled, started, ... for
    each attempt) — read_all() returns every transition ever recorded, in
    order.
    """

    def __init__(self) -> None:
        self._records: list[RetryRecord] = []

    def append(self, record: RetryRecord) -> None:
        self._records.append(record)

    def read_all(self) -> list[RetryRecord]:
        return list(self._records)

    def history_for(self, action_id: str) -> list[RetryRecord]:
        """All transitions recorded for a single action, in order."""
        return [record for record in self._records if record.action_id == action_id]


class RetryManager:
    """Owns retry policy registration and retry attempt bookkeeping for the Executor.

    Attempt state is derived, event-sourced data: it is populated only by
    the Executor's own subscribers for the retry lifecycle events, never
    mutated directly outside of them, so replay and snapshot restore
    reconstruct it with no special-cased code.
    """

    def __init__(self) -> None:
        self._policies: dict[str, RetryPolicy] = {}
        self.retry_log = RetryLog()
        self._attempts: dict[str, int] = {}

    def register_policy(self, action_type: str, policy: RetryPolicy) -> None:
        self._policies[action_type] = policy

    def get_policy(self, action_type: str) -> RetryPolicy:
        return self._policies.get(action_type, RetryPolicy())

    def attempts_made(self, action_id: str) -> int:
        """The highest attempt number recorded as started for this action (1 if none)."""
        return self._attempts.get(action_id, 1)

    def apply_started(self, record: RetryRecord) -> None:
        self.retry_log.append(record)
        self._attempts[record.action_id] = record.attempt

    def apply_transition(self, record: RetryRecord) -> None:
        self.retry_log.append(record)

    def restore(self, records: list[RetryRecord]) -> None:
        for record in records:
            self.retry_log.append(record)
        self._attempts = {}
        for record in records:
            if record.status == "started":
                self._attempts[record.action_id] = record.attempt


@dataclass(slots=True, kw_only=True, frozen=True)
class Credential:
    """Immutable credential value scoped to a single action type.

    Owned exclusively by the Executor; never exposed to the Sandbox, the
    ToolRegistry, or any other component.
    """

    credential_id: str
    action_type: str
    value: str
    status: str
    updated_at: datetime


class CredentialStore:
    """Current-state store of credentials, keyed by action_type.

    Owned exclusively by the Executor. Mutated only inside the Executor's
    subscribers for the credential lifecycle events (registered, updated,
    revoked) — the public registration API only publishes, so replay and
    snapshot restore reconstruct this store with no special-cased code.
    Once a credential is registered for an action_type, that action_type
    requires an active credential for every execution from then on,
    including after revocation. `require()` lets an action_type be marked
    as credential-required before any value is ever registered — bootstrap
    configuration, like a ToolRegistry registration, not event-sourced.
    """

    def __init__(self) -> None:
        self._credentials: dict[str, Credential] = {}
        self._required_action_types: set[str] = set()

    def require(self, action_type: str) -> None:
        self._required_action_types.add(action_type)

    def is_required(self, action_type: str) -> bool:
        return action_type in self._required_action_types or action_type in self._credentials

    def put(self, credential: Credential) -> None:
        self._credentials[credential.action_type] = credential

    def exists(self, action_type: str) -> bool:
        return action_type in self._credentials

    def get(self, action_type: str) -> Credential:
        return self._credentials[action_type]

    def get_active(self, action_type: str) -> Credential:
        """Return the currently active credential for an action_type.

        Raises KeyError if no credential was ever registered for it, or
        LookupError if the registered credential has since been revoked.
        """
        credential = self._credentials[action_type]
        if credential.status != "active":
            raise LookupError(f"credential for action_type '{action_type}' is revoked")
        return credential

    def read_all(self) -> list[Credential]:
        return list(self._credentials.values())


def _parse_ordered_action(ordered_action: str) -> tuple[str, dict[str, str]]:
    action_type, _, target = ordered_action.partition(":")
    parameters = {"target": target} if target else {}
    return action_type, parameters


class Executor:
    """Dispatches approved plans as ordered actions through registered tools."""

    def __init__(self, kernel: Kernel, sandbox: Optional[Sandbox] = None) -> None:
        self._kernel = kernel
        self._sandbox = sandbox if sandbox is not None else LocalSandbox()
        self.tool_registry = ToolRegistry()
        self.action_log = ActionLog()
        self.sandbox_execution_log = SandboxExecutionLog()
        self.retry_manager = RetryManager()
        self.credential_store = CredentialStore()
        self._pending_sandbox_executions: dict[str, SandboxExecutionRecord] = {}
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, self._on_approval_granted)
        kernel.register_subscriber(EventType.SANDBOX_EXECUTION_STARTED, self._on_sandbox_execution_started)
        kernel.register_subscriber(EventType.SANDBOX_EXECUTION_COMPLETED, self._on_sandbox_execution_completed)
        kernel.register_subscriber(EventType.ACTION_RETRY_SCHEDULED, self._on_action_retry_scheduled)
        kernel.register_subscriber(EventType.ACTION_RETRY_STARTED, self._on_action_retry_started)
        kernel.register_subscriber(EventType.ACTION_RETRY_EXHAUSTED, self._on_action_retry_exhausted)
        kernel.register_subscriber(EventType.CREDENTIAL_REGISTERED, self._on_credential_registered)
        kernel.register_subscriber(EventType.CREDENTIAL_UPDATED, self._on_credential_updated)
        kernel.register_subscriber(EventType.CREDENTIAL_REVOKED, self._on_credential_revoked)
        kernel.register_snapshot_source(
            "executor.actions", ActionRecord, self.action_log.read_all, self._restore_actions
        )
        kernel.register_snapshot_source(
            "executor.sandbox_executions",
            SandboxExecutionRecord,
            self.sandbox_execution_log.read_all,
            self._restore_sandbox_executions,
        )
        kernel.register_snapshot_source(
            "executor.retries", RetryRecord, self.retry_manager.retry_log.read_all, self.retry_manager.restore
        )
        kernel.register_snapshot_source(
            "executor.credentials", Credential, self.credential_store.read_all, self._restore_credentials
        )

    def _restore_actions(self, records: list[ActionRecord]) -> None:
        for record in records:
            self.action_log.append(record)

    def _restore_sandbox_executions(self, records: list[SandboxExecutionRecord]) -> None:
        for record in records:
            self.sandbox_execution_log.append(record)
        latest_by_id: dict[str, SandboxExecutionRecord] = {}
        for record in records:
            latest_by_id[record.execution_id] = record
        self._pending_sandbox_executions = {
            execution_id: record
            for execution_id, record in latest_by_id.items()
            if record.status == "started"
        }

    def _restore_credentials(self, records: list[Credential]) -> None:
        for record in records:
            self.credential_store.put(record)

    def require_credential(self, action_type: str) -> None:
        """Declare that executing action_type requires an active credential.

        Bootstrap configuration, like a ToolRegistry registration — not
        event-sourced, since no credential value exists yet to source.
        """
        self.credential_store.require(action_type)

    def register_credential(self, *, action_type: str, value: str) -> str:
        """Register a new active credential for an action_type.

        From this point on, executing that action_type requires an active
        credential. Publishes CredentialRegisteredEvent, which is what
        actually stores it (via this Executor's own subscriber), so
        registration is replay-correct. Returns the new credential_id.
        """
        credential_id = str(uuid4())
        self._kernel.publish(
            CredentialRegisteredEvent(
                source_component="executor", credential_id=credential_id, action_type=action_type, value=value
            )
        )
        return credential_id

    def update_credential(self, action_type: str, *, value: str) -> None:
        """Replace the active credential's value for an action_type.

        Raises KeyError if no credential was ever registered for it. Only
        affects executions from this point forward.
        """
        current = self.credential_store.get(action_type)
        self._kernel.publish(
            CredentialUpdatedEvent(
                source_component="executor",
                credential_id=current.credential_id,
                action_type=action_type,
                value=value,
            )
        )

    def revoke_credential(self, action_type: str) -> None:
        """Revoke the active credential for an action_type.

        Raises KeyError if no credential was ever registered for it.
        """
        current = self.credential_store.get(action_type)
        self._kernel.publish(
            CredentialRevokedEvent(
                source_component="executor", credential_id=current.credential_id, action_type=action_type
            )
        )

    def _on_credential_registered(self, event: CredentialRegisteredEvent) -> None:
        self.credential_store.put(
            Credential(
                credential_id=event.credential_id,
                action_type=event.action_type,
                value=event.value,
                status="active",
                updated_at=event.timestamp,
            )
        )

    def _on_credential_updated(self, event: CredentialUpdatedEvent) -> None:
        self.credential_store.put(
            Credential(
                credential_id=event.credential_id,
                action_type=event.action_type,
                value=event.value,
                status="active",
                updated_at=event.timestamp,
            )
        )

    def _on_credential_revoked(self, event: CredentialRevokedEvent) -> None:
        current = self.credential_store.get(event.action_type)
        self.credential_store.put(
            Credential(
                credential_id=event.credential_id,
                action_type=event.action_type,
                value=current.value,
                status="revoked",
                updated_at=event.timestamp,
            )
        )

    def _on_approval_granted(self, event: ApprovalGrantedEvent) -> None:
        for ordered_action in event.ordered_actions:
            self._execute_action(plan_id=event.plan_id, ordered_action=ordered_action)

    def _execute_action(self, *, plan_id: str, ordered_action: str) -> None:
        action_type, parameters = _parse_ordered_action(ordered_action)
        policy = self.retry_manager.get_policy(action_type)
        action = Action(
            action_id=str(uuid4()),
            plan_id=plan_id,
            action_type=action_type,
            parameters=parameters,
            retry_policy=policy,
        )
        self._kernel.publish(
            ActionApprovedEvent(
                source_component="executor",
                action_id=action.action_id,
                plan_id=plan_id,
                action_type=action_type,
            )
        )
        self._kernel.publish(
            ActionAttemptedEvent(
                source_component="executor",
                action_id=action.action_id,
                tool_name=action_type,
                attempt=1,
            )
        )

        try:
            tool = self.tool_registry.get_tool(action_type)
        except KeyError:
            self._record_failure(action, f"no tool registered for action_type '{action_type}'")
            return

        if self.credential_store.is_required(action_type):
            try:
                credential = self.credential_store.get_active(action_type)
            except KeyError:
                self._record_failure(action, f"no credential registered for action_type '{action_type}'")
                return
            except LookupError as exc:
                self._record_failure(action, str(exc))
                return
            tool = _bind_credential(tool, credential.value)

        attempt = 1
        while True:
            succeeded, outcome = self._run_in_sandbox(action, tool)
            if succeeded:
                self._record_success(action, outcome)
                return

            exc = outcome
            error = str(exc)
            retryable = isinstance(exc, RetryableError)
            if retryable and attempt < policy.max_attempts:
                next_attempt = attempt + 1
                self._kernel.publish(
                    ActionRetryScheduledEvent(
                        source_component="executor",
                        action_id=action.action_id,
                        plan_id=plan_id,
                        action_type=action_type,
                        attempt=attempt,
                        next_attempt=next_attempt,
                        error=error,
                    )
                )
                self._kernel.publish(
                    ActionRetryStartedEvent(
                        source_component="executor",
                        action_id=action.action_id,
                        plan_id=plan_id,
                        action_type=action_type,
                        attempt=next_attempt,
                    )
                )
                self._kernel.publish(
                    ActionAttemptedEvent(
                        source_component="executor",
                        action_id=action.action_id,
                        tool_name=action_type,
                        attempt=next_attempt,
                    )
                )
                attempt = next_attempt
                continue

            self._record_failure(action, error)
            if retryable and policy.max_attempts > 1:
                self._kernel.publish(
                    ActionRetryExhaustedEvent(
                        source_component="executor",
                        action_id=action.action_id,
                        plan_id=plan_id,
                        action_type=action_type,
                        attempts_made=attempt,
                        max_attempts=policy.max_attempts,
                        error=error,
                    )
                )
            return

    def _run_in_sandbox(self, action: Action, tool: Tool) -> tuple[bool, object]:
        """Run one attempt of `tool` through the sandbox.

        Returns `(True, result)` on success or `(False, exception)` on
        failure, publishing the sandbox lifecycle events either way.
        """
        execution_id = str(uuid4())
        self._kernel.publish(
            SandboxExecutionStartedEvent(
                source_component="executor",
                execution_id=execution_id,
                action_id=action.action_id,
                action_type=action.action_type,
            )
        )

        try:
            result = self._sandbox.execute(tool, action)
        except Exception as exc:  # noqa: BLE001 - any sandbox/tool failure is recorded, not propagated
            self._kernel.publish(
                SandboxExecutionCompletedEvent(
                    source_component="executor",
                    execution_id=execution_id,
                    action_id=action.action_id,
                    action_type=action.action_type,
                    status="failed",
                    error=str(exc),
                )
            )
            return False, exc

        self._kernel.publish(
            SandboxExecutionCompletedEvent(
                source_component="executor",
                execution_id=execution_id,
                action_id=action.action_id,
                action_type=action.action_type,
                status="succeeded",
                result=str(result),
            )
        )
        return True, result

    def _on_action_retry_scheduled(self, event: ActionRetryScheduledEvent) -> None:
        self.retry_manager.apply_transition(
            RetryRecord(
                action_id=event.action_id,
                action_type=event.action_type,
                attempt=event.next_attempt,
                status="scheduled",
                timestamp=event.timestamp,
                error=event.error,
            )
        )

    def _on_action_retry_started(self, event: ActionRetryStartedEvent) -> None:
        self.retry_manager.apply_started(
            RetryRecord(
                action_id=event.action_id,
                action_type=event.action_type,
                attempt=event.attempt,
                status="started",
                timestamp=event.timestamp,
            )
        )

    def _on_action_retry_exhausted(self, event: ActionRetryExhaustedEvent) -> None:
        self.retry_manager.apply_transition(
            RetryRecord(
                action_id=event.action_id,
                action_type=event.action_type,
                attempt=event.attempts_made,
                status="exhausted",
                timestamp=event.timestamp,
                error=event.error,
            )
        )

    def _on_sandbox_execution_started(self, event: SandboxExecutionStartedEvent) -> None:
        record = SandboxExecutionRecord(
            execution_id=event.execution_id,
            action_id=event.action_id,
            action_type=event.action_type,
            status="started",
            started_at=event.timestamp,
        )
        self.sandbox_execution_log.append(record)
        self._pending_sandbox_executions[event.execution_id] = record

    def _on_sandbox_execution_completed(self, event: SandboxExecutionCompletedEvent) -> None:
        pending = self._pending_sandbox_executions.pop(event.execution_id)
        self.sandbox_execution_log.append(
            SandboxExecutionRecord(
                execution_id=event.execution_id,
                action_id=event.action_id,
                action_type=event.action_type,
                status=event.status,
                started_at=pending.started_at,
                completed_at=event.timestamp,
                result=event.result,
                error=event.error,
            )
        )

    def _record_success(self, action: Action, result: object) -> None:
        self.action_log.append(
            ActionRecord(record_id=str(uuid4()), action_id=action.action_id, status="succeeded", result=str(result))
        )
        self._kernel.publish(
            ActionSucceededEvent(
                source_component="executor", action_id=action.action_id, plan_id=action.plan_id, result=str(result)
            )
        )

    def _record_failure(self, action: Action, error: str) -> None:
        self.action_log.append(
            ActionRecord(record_id=str(uuid4()), action_id=action.action_id, status="failed", error=error)
        )
        self._kernel.publish(
            ActionFailedEvent(
                source_component="executor", action_id=action.action_id, plan_id=action.plan_id, error=error
            )
        )


__all__ = [
    "Action",
    "ActionRecord",
    "ToolRegistry",
    "ActionLog",
    "Sandbox",
    "LocalSandbox",
    "SandboxExecutionRecord",
    "SandboxExecutionLog",
    "RetryableError",
    "RetryPolicy",
    "RetryRecord",
    "RetryLog",
    "RetryManager",
    "Credential",
    "CredentialStore",
    "Executor",
]
