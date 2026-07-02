"""Perception: turns external signals into normalized, timestamped observations.

Owns the sensor registry and the observation log. Does not own beliefs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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


class Perception:
    """Owns the sensor registry and observation log; publishes ObservationCreated events."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.sensor_registry = SensorRegistry()
        self.observation_log = ObservationLog()

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


__all__ = [
    "Observation",
    "ObservationLog",
    "Perception",
    "SensorMetadata",
    "SensorRegistry",
]
