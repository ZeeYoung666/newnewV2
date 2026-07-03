"""Perception: turns external signals into normalized, timestamped observations.

Owns the sensor registry and the observation log. Does not own beliefs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from src.events import ObservationCreatedEvent
from src.kernel import Kernel


@dataclass(slots=True, kw_only=True)
class SensorMetadata:
    """Descriptive metadata for a registered sensor."""

    sensor_id: str
    name: str
    source_type: str


class SensorRegistry:
    """Tracks which sensors are known to Perception and whether they are active."""

    def __init__(self) -> None:
        self._sensors: dict[str, SensorMetadata] = {}

    def register_sensor(self, *, sensor_id: str, name: str, source_type: str) -> None:
        """Register a new sensor. Raises ValueError if the sensor_id is already registered."""
        if sensor_id in self._sensors:
            raise ValueError(f"sensor '{sensor_id}' is already registered")
        self._sensors[sensor_id] = SensorMetadata(sensor_id=sensor_id, name=name, source_type=source_type)

    def unregister_sensor(self, sensor_id: str) -> None:
        """Remove a sensor from the registry. No-op if it is not registered."""
        self._sensors.pop(sensor_id, None)

    def get_metadata(self, sensor_id: str) -> SensorMetadata:
        """Return metadata for a sensor. Raises KeyError if it is not registered."""
        return self._sensors[sensor_id]

    def is_active(self, sensor_id: str) -> bool:
        """Return whether the sensor is currently registered and active."""
        return sensor_id in self._sensors


@dataclass(slots=True, kw_only=True, frozen=True)
class Observation:
    """A normalized, timestamped reading accepted from a sensor. Immutable once created."""

    observation_id: UUID = field(default_factory=uuid4)
    sensor_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    normalized_value: float
    confidence: float
    raw_source_type: str


class ObservationLog:
    """Append-only log of observations with monotonic sequence numbers."""

    def __init__(self) -> None:
        self._entries: list[tuple[int, Observation]] = []
        self._next_sequence = 1

    def append(self, observation: Observation) -> int:
        """Append an observation and return its assigned sequence number."""
        sequence_number = self._next_sequence
        self._next_sequence += 1
        self._entries.append((sequence_number, observation))
        return sequence_number

    def read_all(self) -> list[tuple[int, Observation]]:
        """Return a copy of the stored entries in insertion order."""
        return list(self._entries)

    def read_from(self, sequence_number: int) -> list[tuple[int, Observation]]:
        """Return the suffix of entries whose sequence number is greater than or equal to the given value."""
        if sequence_number < 1:
            return []
        return [(sequence, observation) for sequence, observation in self._entries if sequence >= sequence_number]


@dataclass(slots=True, kw_only=True, frozen=True)
class NormalizedReading:
    """The canonical (value, confidence) pair an adapter extracts from a raw payload."""

    normalized_value: float
    confidence: float


@runtime_checkable
class ObservationAdapter(Protocol):
    """Normalizes one raw sensor payload format into a NormalizedReading."""

    def accepts(self, payload: object) -> bool:
        """Return whether this adapter knows how to normalize the given payload."""
        ...

    def normalize(self, payload: object) -> NormalizedReading:
        """Extract a NormalizedReading from the payload. Only called if accepts() returned True."""
        ...


class FlatValueAdapter:
    """Normalizes payloads shaped like {"value": float, "confidence": float}."""

    def accepts(self, payload: object) -> bool:
        return isinstance(payload, dict) and "value" in payload and "confidence" in payload

    def normalize(self, payload: object) -> NormalizedReading:
        assert isinstance(payload, dict)
        return NormalizedReading(
            normalized_value=float(payload["value"]),
            confidence=float(payload["confidence"]),
        )


class NestedReadingAdapter:
    """Normalizes payloads shaped like {"reading": {"amount": float, "quality": float}}."""

    def accepts(self, payload: object) -> bool:
        if not isinstance(payload, dict) or "reading" not in payload:
            return False
        reading = payload["reading"]
        return isinstance(reading, dict) and "amount" in reading and "quality" in reading

    def normalize(self, payload: object) -> NormalizedReading:
        assert isinstance(payload, dict)
        reading = payload["reading"]
        return NormalizedReading(
            normalized_value=float(reading["amount"]),
            confidence=float(reading["quality"]),
        )


class AdapterRegistry:
    """Ordered chain of ObservationAdapters. The first adapter that accepts a payload normalizes it."""

    def __init__(self) -> None:
        self._adapters: list[ObservationAdapter] = []

    def register(self, adapter: ObservationAdapter) -> None:
        """Append an adapter to the end of the selection chain."""
        self._adapters.append(adapter)

    def normalize(self, payload: object) -> NormalizedReading:
        """Return the NormalizedReading from the first adapter that accepts payload.

        Raises ValueError if no registered adapter accepts the payload.
        """
        for adapter in self._adapters:
            if adapter.accepts(payload):
                return adapter.normalize(payload)
        raise ValueError(f"no adapter accepts payload: {payload!r}")


class Perception:
    """Owns the sensor registry and observation log; publishes ObservationCreated events."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.sensor_registry = SensorRegistry()
        self.observation_log = ObservationLog()
        self.adapter_registry = AdapterRegistry()
        self.adapter_registry.register(FlatValueAdapter())
        self.adapter_registry.register(NestedReadingAdapter())

    def record_observation(
        self,
        *,
        sensor_id: str,
        normalized_value: float,
        confidence: float,
        raw_source_type: str,
    ) -> Observation:
        """Validate, record, and announce a new observation.

        Raises ValueError if the sensor is not registered/active or confidence is out of range.
        """
        if not self.sensor_registry.is_active(sensor_id):
            raise ValueError(f"sensor '{sensor_id}' is not registered or not active")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence {confidence} is out of range [0.0, 1.0]")

        observation = Observation(
            sensor_id=sensor_id,
            normalized_value=normalized_value,
            confidence=confidence,
            raw_source_type=raw_source_type,
        )
        self.observation_log.append(observation)
        self._kernel.publish(
            ObservationCreatedEvent(
                source_component="perception",
                observation_id=str(observation.observation_id),
                sensor_id=observation.sensor_id,
                normalized_value=observation.normalized_value,
                confidence=observation.confidence,
                raw_source_type=observation.raw_source_type,
            )
        )
        return observation

    def record_raw_observation(self, *, sensor_id: str, payload: object) -> Observation:
        """Normalize a raw sensor payload through the adapter registry, then record it.

        Raises ValueError if the sensor is not registered/active or no adapter accepts the payload.
        """
        if not self.sensor_registry.is_active(sensor_id):
            raise ValueError(f"sensor '{sensor_id}' is not registered or not active")

        raw_source_type = self.sensor_registry.get_metadata(sensor_id).source_type
        reading = self.adapter_registry.normalize(payload)
        return self.record_observation(
            sensor_id=sensor_id,
            normalized_value=reading.normalized_value,
            confidence=reading.confidence,
            raw_source_type=raw_source_type,
        )


__all__ = [
    "AdapterRegistry",
    "FlatValueAdapter",
    "NestedReadingAdapter",
    "NormalizedReading",
    "Observation",
    "ObservationAdapter",
    "ObservationLog",
    "Perception",
    "SensorMetadata",
    "SensorRegistry",
]
