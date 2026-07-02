"""Minimal kernel infrastructure for typed event transport."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Callable, DefaultDict, Deque

from src.events import (
    Event,
    EventType,
    KernelStartingEvent,
    KernelStartedEvent,
    KernelStoppingEvent,
    KernelStoppedEvent,
)

Subscriber = Callable[[Event], None]


class EventLog:
    """Append-only log for storing events with monotonic sequence numbers."""

    def __init__(self) -> None:
        self._entries: list[tuple[int, Event]] = []
        self._next_sequence = 1

    def append(self, event: Event) -> int:
        """Append an event and return its assigned sequence number."""
        sequence_number = self._next_sequence
        self._next_sequence += 1
        self._entries.append((sequence_number, event))
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


class Kernel:
    """Infrastructure-only event bus for typed event delivery.

    The shutdown semantics are intentionally frozen: events already accepted into
    the queue before shutdown begins are preserved, while non-lifecycle events
    published after shutdown starts are not dispatched.
    """

    def __init__(self) -> None:
        self._subscribers: DefaultDict[EventType, list[Subscriber]] = defaultdict(list)
        self.event_log = EventLog()
        self._queue: Deque[Event] = deque()
        self._running = False
        self._started = False
        self._dispatching = False
        self._stopping = False

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

    def start(self) -> None:
        """Start the kernel event loop."""
        if not self._running:
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

    def publish(self, event: Event) -> None:
        """Queue an event for processing by the event loop."""
        self.event_log.append(event)
        self._queue.append(event)
        if not self._dispatching and (
            not self._started
            or event.event_type in {
                EventType.KERNEL_STARTING,
                EventType.KERNEL_STARTED,
                EventType.KERNEL_STOPPING,
                EventType.KERNEL_STOPPED,
            }
        ):
            self.run_until_idle()

    def process_next(self) -> None:
        """Process the next queued event, if any."""
        if not self._queue:
            return
        event = self._queue.popleft()
        if self._stopping and event.event_type not in {
            EventType.KERNEL_STARTING,
            EventType.KERNEL_STARTED,
            EventType.KERNEL_STOPPING,
            EventType.KERNEL_STOPPED,
        }:
            return
        self._dispatching = True
        self.dispatch(event)
        self._dispatching = False

    def run_until_idle(self) -> None:
        """Process queued events until the queue is empty or the kernel has stopped."""
        while self._queue and (
            not self._started
            or self._running
            or any(event.event_type in {EventType.KERNEL_STARTED, EventType.KERNEL_STOPPED} for event in self._queue)
        ):
            self.process_next()

    def dispatch(self, event: Event) -> None:
        """Synchronously deliver an event to every subscriber for its type."""
        for subscriber in self._subscribers.get(event.event_type, []):
            subscriber(event)


__all__ = ["EventLog", "Kernel", "Subscriber"]
