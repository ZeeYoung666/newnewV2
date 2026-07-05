"""World Model: converts observations into beliefs with confidence, provenance, decay.

Owns the belief store. Subscribes to ObservationCreated events from the Kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.events import (
    BeliefCreatedEvent,
    BeliefUpdatedEvent,
    EventType,
    ObservationCreatedEvent,
    SensorReliabilityUpdatedEvent,
)
from src.kernel import Kernel

DEFAULT_DECAY_RATE = 0.01
DEFAULT_SENSOR_RELIABILITY = 1.0


@dataclass(slots=True, kw_only=True, frozen=True)
class Belief:
    """A claim about the world, held with some confidence, tied to its source. Immutable snapshot."""

    belief_id: str
    claim: str
    confidence: float
    provenance: str
    last_updated: datetime
    decay_rate: float = DEFAULT_DECAY_RATE


class BeliefStore:
    """Current-state store of beliefs, keyed by belief_id."""

    def __init__(self) -> None:
        self._beliefs: dict[str, Belief] = {}

    def put(self, belief: Belief) -> None:
        """Insert or replace the belief under its belief_id."""
        self._beliefs[belief.belief_id] = belief

    def get(self, belief_id: str) -> Belief:
        """Return the current belief. Raises KeyError if it does not exist."""
        return self._beliefs[belief_id]

    def exists(self, belief_id: str) -> bool:
        """Return whether a belief with this id is currently held."""
        return belief_id in self._beliefs

    def read_all(self) -> list[Belief]:
        """Return all current beliefs."""
        return list(self._beliefs.values())


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(slots=True, kw_only=True, frozen=True)
class SensorReliability:
    """World Model's own cached view of a sensor's learned reliability.

    Populated only via SensorReliabilityUpdatedEvent — World Model never
    reads Memory & Ledger's SensorReliabilityLedger directly.
    """

    sensor_id: str
    reliability: float


class SensorReliabilityStore:
    """Current-state store of sensor reliabilities, keyed by sensor_id."""

    def __init__(self) -> None:
        self._reliabilities: dict[str, SensorReliability] = {}

    def put(self, reliability: SensorReliability) -> None:
        """Insert or replace the reliability under its sensor_id."""
        self._reliabilities[reliability.sensor_id] = reliability

    def get(self, sensor_id: str) -> float:
        """The learned reliability for a sensor, or the neutral default if never updated."""
        entry = self._reliabilities.get(sensor_id)
        return entry.reliability if entry is not None else DEFAULT_SENSOR_RELIABILITY

    def read_all(self) -> list[SensorReliability]:
        """Return every currently cached sensor reliability."""
        return list(self._reliabilities.values())


class WorldModel:
    """Owns the belief store; converts observations into beliefs and decays them over time."""

    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.belief_store = BeliefStore()
        self.sensor_reliability_store = SensorReliabilityStore()
        kernel.register_subscriber(EventType.OBSERVATION_CREATED, self._on_observation_created)
        kernel.register_subscriber(EventType.SENSOR_RELIABILITY_UPDATED, self._on_sensor_reliability_updated)
        kernel.register_snapshot_source(
            "world_model.beliefs", Belief, self.belief_store.read_all, self._restore_beliefs
        )
        kernel.register_snapshot_source(
            "world_model.sensor_reliability",
            SensorReliability,
            self.sensor_reliability_store.read_all,
            self._restore_sensor_reliability,
        )

    def _restore_beliefs(self, beliefs: list[Belief]) -> None:
        for belief in beliefs:
            self.belief_store.put(belief)

    def _restore_sensor_reliability(self, reliabilities: list[SensorReliability]) -> None:
        for reliability in reliabilities:
            self.sensor_reliability_store.put(reliability)

    def _belief_id_for_sensor(self, sensor_id: str) -> str:
        return f"sensor:{sensor_id}"

    def _on_sensor_reliability_updated(self, event: SensorReliabilityUpdatedEvent) -> None:
        self.sensor_reliability_store.put(
            SensorReliability(sensor_id=event.sensor_id, reliability=event.reliability)
        )

    def _on_observation_created(self, event: ObservationCreatedEvent) -> None:
        belief_id = self._belief_id_for_sensor(event.sensor_id)
        claim = str(event.normalized_value)
        # Fast Learning Loop: weight the incoming evidence by this sensor's
        # learned reliability (1.0, full trust, until Memory & Ledger has
        # resolved predictions to score it from) instead of treating every
        # sensor's report as equally trustworthy.
        reliability = self.sensor_reliability_store.get(event.sensor_id)
        weighted_confidence = event.confidence * reliability

        if self.belief_store.exists(belief_id):
            existing = self.belief_store.get(belief_id)
            previous_confidence = existing.confidence
            new_confidence = _clamp_confidence((existing.confidence + weighted_confidence) / 2)
            self.belief_store.put(
                Belief(
                    belief_id=belief_id,
                    claim=claim,
                    confidence=new_confidence,
                    provenance=event.sensor_id,
                    last_updated=event.timestamp,
                    decay_rate=existing.decay_rate,
                )
            )
            self._kernel.publish(
                BeliefUpdatedEvent(
                    source_component="world_model",
                    belief_id=belief_id,
                    previous_confidence=previous_confidence,
                    new_confidence=new_confidence,
                    provenance=event.sensor_id,
                )
            )
        else:
            self.belief_store.put(
                Belief(
                    belief_id=belief_id,
                    claim=claim,
                    confidence=weighted_confidence,
                    provenance=event.sensor_id,
                    last_updated=event.timestamp,
                    decay_rate=DEFAULT_DECAY_RATE,
                )
            )
            self._kernel.publish(
                BeliefCreatedEvent(
                    source_component="world_model",
                    belief_id=belief_id,
                    claim=claim,
                    confidence=weighted_confidence,
                    provenance=event.sensor_id,
                )
            )

    def apply_decay(self, now: datetime) -> None:
        """Decay every belief's confidence based on elapsed time since it was last updated."""
        for belief in self.belief_store.read_all():
            if belief.decay_rate <= 0:
                continue
            elapsed_seconds = (now - belief.last_updated).total_seconds()
            if elapsed_seconds <= 0:
                continue

            previous_confidence = belief.confidence
            decayed_confidence = _clamp_confidence(belief.confidence - belief.decay_rate * elapsed_seconds)
            if decayed_confidence == previous_confidence:
                continue

            self.belief_store.put(
                Belief(
                    belief_id=belief.belief_id,
                    claim=belief.claim,
                    confidence=decayed_confidence,
                    provenance=belief.provenance,
                    last_updated=now,
                    decay_rate=belief.decay_rate,
                )
            )
            self._kernel.publish(
                BeliefUpdatedEvent(
                    source_component="world_model",
                    belief_id=belief.belief_id,
                    previous_confidence=previous_confidence,
                    new_confidence=decayed_confidence,
                    provenance=belief.provenance,
                )
            )


__all__ = [
    "Belief",
    "BeliefStore",
    "SensorReliability",
    "SensorReliabilityStore",
    "WorldModel",
    "DEFAULT_DECAY_RATE",
    "DEFAULT_SENSOR_RELIABILITY",
]
