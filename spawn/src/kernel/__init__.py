"""Minimal kernel infrastructure for typed event transport."""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
import typing
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, DefaultDict, Optional, Union
from uuid import UUID, uuid4

import src.events as _events_module
from src.events import (
    Event,
    EventType,
    KernelStartingEvent,
    KernelStartedEvent,
    KernelStoppingEvent,
    KernelStoppedEvent,
)

Subscriber = Callable[[Event], None]
SnapshotCapture = Callable[[], list]
SnapshotRestore = Callable[[list], None]

_EVENT_CLASSES: dict[str, type[Event]] = {
    name: obj
    for name, obj in vars(_events_module).items()
    if isinstance(obj, type) and issubclass(obj, Event)
}


def _encode_value(value: object) -> object:
    if isinstance(value, EventType):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return list(value)
    return value


def _decode_value(value: object, target_type: object) -> object:
    origin = typing.get_origin(target_type)
    if origin is Union:
        non_none = [arg for arg in typing.get_args(target_type) if arg is not type(None)]
        if value is None:
            return None
        return _decode_value(value, non_none[0])
    if target_type is UUID:
        return UUID(value)  # type: ignore[arg-type]
    if target_type is datetime:
        return datetime.fromisoformat(value)  # type: ignore[arg-type]
    if target_type is EventType:
        return EventType(value)
    if origin is tuple:
        return tuple(value)  # type: ignore[arg-type]
    return value


def _encode_dataclass_fields(obj: object) -> dict:
    """Encode every field of an arbitrary dataclass instance to a JSON-safe dict.

    Shared by event log persistence and snapshot persistence — both need the
    same UUID/datetime/tuple-aware field encoding, just wrapped differently.
    """
    return {f.name: _encode_value(getattr(obj, f.name)) for f in dataclasses.fields(obj)}


def _decode_dataclass(fields: dict, cls: type) -> object:
    """Decode a JSON-safe field dict back into an instance of the given dataclass."""
    type_hints = typing.get_type_hints(cls)
    kwargs = {name: _decode_value(value, type_hints[name]) for name, value in fields.items()}
    return cls(**kwargs)


def _encode_event(sequence_number: int, event: Event) -> dict:
    return {"sequence": sequence_number, "class": type(event).__name__, "fields": _encode_dataclass_fields(event)}


def _decode_event(record: dict) -> tuple[int, Event]:
    cls = _EVENT_CLASSES[record["class"]]
    return record["sequence"], _decode_dataclass(record["fields"], cls)


class EventLog:
    """Append-only, disk-backed log of events with monotonic sequence numbers.

    Stored as JSONL: one line per event, never rewritten. With no explicit
    path, each instance gets its own fresh temp file so construction stays
    isolated (matching prior in-memory behavior) unless a path is given to
    read/write a specific durable log across restarts.
    """

    def __init__(self, path: Union[str, "os.PathLike[str]", None] = None) -> None:
        if path is None:
            fd, generated_path = tempfile.mkstemp(suffix=".jsonl", prefix="event-log-")
            os.close(fd)
            path = generated_path
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[tuple[int, Event]] = []
        self._next_sequence = 1
        self._load_existing()

    @property
    def path(self) -> Path:
        """The on-disk location backing this log."""
        return self._path

    def _load_existing(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                self._entries.append(_decode_event(json.loads(line)))
        if self._entries:
            self._next_sequence = self._entries[-1][0] + 1

    def append(self, event: Event) -> int:
        """Append an event, durably persist it, and return its assigned sequence number."""
        sequence_number = self._next_sequence
        self._next_sequence += 1
        self._entries.append((sequence_number, event))
        record = _encode_event(sequence_number, event)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return sequence_number

    def read_all(self) -> list[tuple[int, Event]]:
        """Return a copy of the stored entries in insertion order."""
        return list(self._entries)

    def read_from(self, sequence_number: int) -> list[tuple[int, Event]]:
        """Return the suffix of entries whose sequence number is greater than or equal to the given value."""
        if sequence_number < 1:
            return []
        return [(sequence, event) for sequence, event in self._entries if sequence >= sequence_number]

    def latest_sequence(self) -> int:
        """Return the latest assigned sequence number, or 0 when empty."""
        if not self._entries:
            return 0
        return self._entries[-1][0]


class SnapshotStore:
    """Disk-backed store for the single most recent organism snapshot.

    Every create_snapshot() call atomically overwrites this file — only the
    latest snapshot is ever retained, there is no history of snapshots. The
    EventLog itself is never touched by this class and stays append-only
    regardless of how many snapshots are taken.
    """

    def __init__(self, path: Union[str, "os.PathLike[str]", None] = None) -> None:
        if path is None:
            fd, generated_path = tempfile.mkstemp(suffix=".snapshot.json", prefix="snapshot-")
            os.close(fd)
            path = generated_path
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, sequence: int, sources: dict) -> None:
        """Atomically persist a snapshot, replacing whatever was there before."""
        record = {"sequence": sequence, "sources": sources}
        tmp_path = self._path.with_name(self._path.name + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(record, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, self._path)

    def load(self) -> Optional[dict]:
        """Return the persisted snapshot record, or None if none exists yet.

        The default (path=None) constructor path uses tempfile.mkstemp,
        which creates an empty file on disk before any snapshot is ever
        saved — an empty file is treated the same as a missing one rather
        than a JSON decode error.
        """
        if not self._path.exists():
            return None
        with self._path.open("r", encoding="utf-8") as fh:
            content = fh.read()
        if not content:
            return None
        return json.loads(content)


class Scheduler:
    """Deterministic, FIFO scheduler that owns execution order for the Kernel.

    Purely mechanical: queues zero-argument callbacks and runs them in the
    order they were scheduled. It has no idea what a callback does — no
    event types, no dispatch, no business logic. Nested scheduling (a
    callback calling schedule() on itself) appends to the back of the queue
    rather than recursing, so run_until_idle drains new work in later
    iterations of its own loop, never via a nested call stack.
    """

    def __init__(self) -> None:
        self._queue: list[tuple[int, Callable[[], None]]] = []
        self._next_task_id = 1

    def schedule(self, callback: Callable[[], None]) -> int:
        """Queue a callback to run exactly once, in FIFO order. Returns its task id."""
        task_id = self._next_task_id
        self._next_task_id += 1
        self._queue.append((task_id, callback))
        return task_id

    def cancel(self, task_id: int) -> bool:
        """Remove a still-pending task so it never executes. Returns whether it was found."""
        for index, (existing_id, _) in enumerate(self._queue):
            if existing_id == task_id:
                del self._queue[index]
                return True
        return False

    def run_next(self) -> bool:
        """Execute the next pending task, if any. Returns whether one ran."""
        if not self._queue:
            return False
        _, callback = self._queue.pop(0)
        callback()
        return True

    def run_until_idle(self) -> None:
        """Run pending tasks until none remain, including any queued during execution."""
        while self._queue:
            self.run_next()

    def pending_count(self) -> int:
        """Return how many tasks are still queued (cancelled tasks are removed immediately)."""
        return len(self._queue)


class Kernel:
    """Infrastructure-only event bus for typed event delivery.

    The shutdown semantics are intentionally frozen: events already accepted into
    the queue before shutdown begins are preserved, while non-lifecycle events
    published after shutdown starts are not dispatched.
    """

    _TERMINAL_LIFECYCLE_TYPES = {EventType.KERNEL_STARTED, EventType.KERNEL_STOPPED}
    _LIFECYCLE_TYPES = {
        EventType.KERNEL_STARTING,
        EventType.KERNEL_STARTED,
        EventType.KERNEL_STOPPING,
        EventType.KERNEL_STOPPED,
    }

    def __init__(
        self, event_log: Optional[EventLog] = None, snapshot_store: Optional[SnapshotStore] = None
    ) -> None:
        self._subscribers: DefaultDict[EventType, list[Subscriber]] = defaultdict(list)
        self.event_log = event_log if event_log is not None else EventLog()
        self.snapshot_store = (
            snapshot_store
            if snapshot_store is not None
            else SnapshotStore(path=self.event_log.path.with_suffix(".snapshot.json"))
        )
        self._snapshot_sources: dict[str, tuple[type, SnapshotCapture, SnapshotRestore]] = {}
        self.scheduler = Scheduler()
        self._pending_terminal_lifecycle = 0
        self._running = False
        self._started = False
        self._dispatching = False
        self._stopping = False
        self._replaying = False
        self._replayed = False
        self._active_correlation_id: Optional[UUID] = None

    def register_subscriber(self, event_type: EventType, subscriber: Subscriber) -> None:
        """Register a subscriber for a specific event type."""
        self._subscribers[event_type].append(subscriber)

    def unregister_subscriber(self, event_type: EventType, subscriber: Subscriber) -> None:
        """Remove a subscriber from a specific event type."""
        subscribers = self._subscribers.get(event_type, [])
        if subscriber in subscribers:
            subscribers.remove(subscriber)

    def subscribe(self, event_type: EventType, subscriber: Subscriber) -> None:
        """Alias for register_subscriber."""
        self.register_subscriber(event_type, subscriber)

    def unsubscribe(self, event_type: EventType, subscriber: Subscriber) -> None:
        """Alias for unregister_subscriber."""
        self.unregister_subscriber(event_type, subscriber)

    def register_snapshot_source(
        self, name: str, item_cls: type, capture: SnapshotCapture, restore: SnapshotRestore
    ) -> None:
        """Register a component's own store for snapshot capture/restore.

        `capture` and `restore` close over exactly one component's own store
        (e.g. `self.belief_store.read_all` / a helper that calls
        `self.belief_store.put` for each item) — the Kernel only ever sees an
        opaque list of `item_cls` instances, never reaches into store
        internals itself, and never crosses into another component's store.
        """
        self._snapshot_sources[name] = (item_cls, capture, restore)

    def create_snapshot(self) -> int:
        """Capture every registered source's current state at the event log's
        current sequence number and persist it as the new latest snapshot.
        """
        sequence = self.event_log.latest_sequence()
        sources = {
            name: [_encode_dataclass_fields(item) for item in capture()]
            for name, (_, capture, _) in self._snapshot_sources.items()
        }
        self.snapshot_store.save(sequence, sources)
        return sequence

    def start(self) -> None:
        """Start the kernel event loop, replaying any persisted history first."""
        if not self._running:
            if not self._replayed:
                self.replay()
            self._stopping = False
            self.publish(KernelStartingEvent(source_component="kernel"))
            self._running = True
            self._started = True
            self.publish(KernelStartedEvent(source_component="kernel"))

    def stop(self) -> None:
        """Stop the kernel event loop."""
        if self._running:
            self._stopping = True
            self.publish(KernelStoppingEvent(source_component="kernel"))
            self._running = False
            self.publish(KernelStoppedEvent(source_component="kernel"))
            self._stopping = False

    def is_running(self) -> bool:
        """Return whether the kernel is currently running."""
        return self._running

    def replay(self) -> int:
        """Reconstruct component state from the latest snapshot (if any) plus
        every event recorded after it, in original sequence order. Must run
        before the kernel starts, and runs at most once.

        With no snapshot present this dispatches from sequence 1, identical
        to full replay. Events a handler re-publishes while this runs are not
        re-appended to the log or re-dispatched here: each one is already its
        own entry in the log and gets visited directly by this same loop when
        its own sequence number is reached. Suppressing the nested publish is
        what keeps every historical event dispatched exactly once and leaves
        the log with no duplicates.
        """
        if self._started:
            raise RuntimeError("cannot replay after the kernel has started")
        if self._replayed:
            raise RuntimeError("replay has already run for this kernel")

        self._replaying = True
        try:
            snapshot_sequence = self._restore_latest_snapshot()
            start_sequence = 1 if snapshot_sequence is None else snapshot_sequence + 1
            for _, event in self.event_log.read_from(start_sequence):
                self.dispatch(event)
        finally:
            self._replaying = False
        self._replayed = True
        return self.event_log.latest_sequence()

    def _restore_latest_snapshot(self) -> Optional[int]:
        """Load the latest snapshot (if any) and hand each source's state back
        to the component that registered it. Returns the snapshot's sequence
        number, or None if no snapshot has ever been taken.
        """
        record = self.snapshot_store.load()
        if record is None:
            return None
        for name, encoded_items in record["sources"].items():
            if name not in self._snapshot_sources:
                continue
            item_cls, _, restore = self._snapshot_sources[name]
            restore([_decode_dataclass(fields, item_cls) for fields in encoded_items])
        return record["sequence"]

    def publish(self, event: Event) -> None:
        """Queue an event for processing by the event loop, via the scheduler.

        The Kernel is the sole owner of correlation_id propagation. A
        publish that happens while no correlation is currently active mints
        a fresh id (unless the event already carries one); every other
        publish inherits whatever id is currently active. The active id is
        cleared in `_dispatch_scheduled` once the scheduler's queue fully
        drains, not when this method returns — after the kernel has
        started, publish() for a non-lifecycle event schedules the task but
        does not drain it itself, so the active id must survive until the
        caller's own run_until_idle() call actually processes the cascade.
        """
        if self._replaying:
            return
        if event.correlation_id is None:
            event.correlation_id = (
                self._active_correlation_id if self._active_correlation_id is not None else uuid4()
            )
        if self._active_correlation_id is None:
            self._active_correlation_id = event.correlation_id
        self.event_log.append(event)
        if event.event_type in self._TERMINAL_LIFECYCLE_TYPES:
            self._pending_terminal_lifecycle += 1
        self.scheduler.schedule(lambda: self._dispatch_scheduled(event))
        if not self._dispatching and (not self._started or event.event_type in self._LIFECYCLE_TYPES):
            self.run_until_idle()

    def _dispatch_scheduled(self, event: Event) -> None:
        """Business logic executed by the scheduler for one queued event."""
        if event.event_type in self._TERMINAL_LIFECYCLE_TYPES:
            self._pending_terminal_lifecycle -= 1
        if self._stopping and event.event_type not in self._LIFECYCLE_TYPES:
            if self.scheduler.pending_count() == 0:
                self._active_correlation_id = None
            return
        self._dispatching = True
        self.dispatch(event)
        self._dispatching = False
        if self.scheduler.pending_count() == 0:
            self._active_correlation_id = None

    def process_next(self) -> None:
        """Process the next queued event, if any, by delegating to the scheduler."""
        self.scheduler.run_next()

    def run_until_idle(self) -> None:
        """Process queued events until the queue is empty or the kernel has stopped."""
        while self.scheduler.pending_count() and (
            not self._started or self._running or self._pending_terminal_lifecycle > 0
        ):
            self.process_next()

    def dispatch(self, event: Event) -> None:
        """Synchronously deliver an event to every subscriber for its type."""
        for subscriber in self._subscribers.get(event.event_type, []):
            subscriber(event)


__all__ = ["EventLog", "Kernel", "Scheduler", "SnapshotStore", "Subscriber"]
