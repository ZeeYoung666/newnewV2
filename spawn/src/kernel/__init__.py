"""Minimal kernel infrastructure for typed event transport."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict

from src.events import Event, EventType

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
    """Infrastructure-only event bus for typed event delivery."""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[EventType, list[Subscriber]] = defaultdict(list)
        self.event_log = EventLog()

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

    def publish(self, event: Event) -> None:
        """Publish an event and dispatch it synchronously to matching subscribers."""
        self.event_log.append(event)
        self.dispatch(event)

    def dispatch(self, event: Event) -> None:
        """Synchronously deliver an event to every subscriber for its type."""
        for subscriber in self._subscribers.get(event.event_type, []):
            subscriber(event)


__all__ = ["EventLog", "Kernel", "Subscriber"]
