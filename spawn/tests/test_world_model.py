import dataclasses
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from src.events import (
    BeliefCreatedEvent,
    BeliefUpdatedEvent,
    Event,
    EventType,
    ObservationCreatedEvent,
    SensorReliabilityUpdatedEvent,
)
from src.kernel import EventLog, Kernel
from src.perception import Perception
from src.world_model import (
    Belief,
    BeliefStore,
    DEFAULT_SENSOR_RELIABILITY,
    SensorReliability,
    SensorReliabilityStore,
    WorldModel,
)


class BeliefModelTests(unittest.TestCase):
    def test_belief_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        belief = Belief(
            belief_id="belief-1",
            claim="0.5",
            confidence=0.7,
            provenance="sensor-1",
            last_updated=now,
            decay_rate=0.01,
        )

        self.assertEqual(belief.belief_id, "belief-1")
        self.assertEqual(belief.claim, "0.5")
        self.assertEqual(belief.confidence, 0.7)
        self.assertEqual(belief.provenance, "sensor-1")
        self.assertEqual(belief.last_updated, now)
        self.assertEqual(belief.decay_rate, 0.01)

    def test_belief_is_immutable(self) -> None:
        belief = Belief(
            belief_id="belief-1",
            claim="0.5",
            confidence=0.7,
            provenance="sensor-1",
            last_updated=datetime.now(timezone.utc),
            decay_rate=0.01,
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            belief.confidence = 0.1  # type: ignore[misc]


class BeliefStoreTests(unittest.TestCase):
    def test_put_and_get_round_trip(self) -> None:
        store = BeliefStore()
        belief = Belief(
            belief_id="belief-1",
            claim="0.5",
            confidence=0.7,
            provenance="sensor-1",
            last_updated=datetime.now(timezone.utc),
            decay_rate=0.0,
        )

        store.put(belief)

        self.assertEqual(store.get("belief-1"), belief)
        self.assertTrue(store.exists("belief-1"))

    def test_get_raises_for_unknown_belief(self) -> None:
        store = BeliefStore()

        with self.assertRaises(KeyError):
            store.get("unknown")

    def test_exists_returns_false_for_unknown_belief(self) -> None:
        store = BeliefStore()

        self.assertFalse(store.exists("unknown"))

    def test_put_replaces_existing_belief_and_read_all_reflects_current_state(self) -> None:
        store = BeliefStore()
        original = Belief(
            belief_id="belief-1",
            claim="0.5",
            confidence=0.7,
            provenance="sensor-1",
            last_updated=datetime.now(timezone.utc),
            decay_rate=0.0,
        )
        replacement = dataclasses.replace(original, confidence=0.9)

        store.put(original)
        store.put(replacement)

        self.assertEqual(store.get("belief-1").confidence, 0.9)
        self.assertEqual(store.read_all(), [replacement])


class WorldModelObservationTests(unittest.TestCase):
    def test_first_observation_creates_belief_and_emits_belief_created(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        world_model = WorldModel(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_CREATED, received.append)

        perception.record_observation(
            sensor_id="sensor-1",
            normalized_value=0.42,
            confidence=0.8,
            raw_source_type="market_feed",
        )

        beliefs = world_model.belief_store.read_all()
        self.assertEqual(len(beliefs), 1)
        belief = beliefs[0]
        self.assertEqual(belief.confidence, 0.8)
        self.assertEqual(belief.provenance, "sensor-1")

        self.assertEqual(len(received), 1)
        created_event = received[0]
        self.assertIsInstance(created_event, BeliefCreatedEvent)
        self.assertEqual(created_event.belief_id, belief.belief_id)
        self.assertEqual(created_event.confidence, 0.8)
        self.assertEqual(created_event.provenance, "sensor-1")

    def test_repeated_observation_for_same_sensor_updates_confidence_and_emits_belief_updated(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        world_model = WorldModel(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        perception.record_observation(
            sensor_id="sensor-1",
            normalized_value=0.4,
            confidence=0.6,
            raw_source_type="market_feed",
        )

        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        perception.record_observation(
            sensor_id="sensor-1",
            normalized_value=0.5,
            confidence=1.0,
            raw_source_type="market_feed",
        )

        beliefs = world_model.belief_store.read_all()
        self.assertEqual(len(beliefs), 1)
        belief = beliefs[0]
        self.assertEqual(belief.confidence, 0.8)  # average of 0.6 and 1.0

        self.assertEqual(len(received), 1)
        updated_event = received[0]
        self.assertIsInstance(updated_event, BeliefUpdatedEvent)
        self.assertEqual(updated_event.belief_id, belief.belief_id)
        self.assertEqual(updated_event.previous_confidence, 0.6)
        self.assertEqual(updated_event.new_confidence, 0.8)
        self.assertEqual(updated_event.provenance, "sensor-1")

    def test_observations_from_different_sensors_create_separate_beliefs(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        world_model = WorldModel(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")
        perception.sensor_registry.register_sensor(sensor_id="sensor-2", name="News Feed", source_type="news_feed")

        perception.record_observation(
            sensor_id="sensor-1", normalized_value=0.4, confidence=0.6, raw_source_type="market_feed"
        )
        perception.record_observation(
            sensor_id="sensor-2", normalized_value=0.9, confidence=0.7, raw_source_type="news_feed"
        )

        beliefs = world_model.belief_store.read_all()
        self.assertEqual(len(beliefs), 2)
        provenances = {belief.provenance for belief in beliefs}
        self.assertEqual(provenances, {"sensor-1", "sensor-2"})


class WorldModelDecayTests(unittest.TestCase):
    def test_apply_decay_reduces_confidence_and_emits_belief_updated(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)
        start = datetime.now(timezone.utc)
        belief = Belief(
            belief_id="belief-1",
            claim="0.5",
            confidence=0.8,
            provenance="sensor-1",
            last_updated=start,
            decay_rate=0.01,
        )
        world_model.belief_store.put(belief)

        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        world_model.apply_decay(start + timedelta(seconds=10))

        updated = world_model.belief_store.get("belief-1")
        self.assertAlmostEqual(updated.confidence, 0.7)
        self.assertEqual(updated.last_updated, start + timedelta(seconds=10))

        self.assertEqual(len(received), 1)
        event = received[0]
        self.assertIsInstance(event, BeliefUpdatedEvent)
        self.assertEqual(event.belief_id, "belief-1")
        self.assertAlmostEqual(event.previous_confidence, 0.8)
        self.assertAlmostEqual(event.new_confidence, 0.7)

    def test_apply_decay_does_not_go_below_zero(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)
        start = datetime.now(timezone.utc)
        belief = Belief(
            belief_id="belief-1",
            claim="0.5",
            confidence=0.2,
            provenance="sensor-1",
            last_updated=start,
            decay_rate=0.5,
        )
        world_model.belief_store.put(belief)

        world_model.apply_decay(start + timedelta(seconds=10))

        self.assertEqual(world_model.belief_store.get("belief-1").confidence, 0.0)

    def test_apply_decay_skips_beliefs_with_zero_decay_rate(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)
        start = datetime.now(timezone.utc)
        belief = Belief(
            belief_id="belief-1",
            claim="0.5",
            confidence=0.8,
            provenance="sensor-1",
            last_updated=start,
            decay_rate=0.0,
        )
        world_model.belief_store.put(belief)

        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        world_model.apply_decay(start + timedelta(seconds=10))

        self.assertEqual(world_model.belief_store.get("belief-1").confidence, 0.8)
        self.assertEqual(received, [])

    def test_apply_decay_skips_when_no_time_has_elapsed(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)
        start = datetime.now(timezone.utc)
        belief = Belief(
            belief_id="belief-1",
            claim="0.5",
            confidence=0.8,
            provenance="sensor-1",
            last_updated=start,
            decay_rate=0.01,
        )
        world_model.belief_store.put(belief)

        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)

        world_model.apply_decay(start)

        self.assertEqual(world_model.belief_store.get("belief-1").confidence, 0.8)
        self.assertEqual(received, [])


class SensorReliabilityModelTests(unittest.TestCase):
    def test_carries_required_fields(self) -> None:
        reliability = SensorReliability(sensor_id="sensor-1", reliability=0.75)

        self.assertEqual(reliability.sensor_id, "sensor-1")
        self.assertEqual(reliability.reliability, 0.75)

    def test_is_immutable(self) -> None:
        reliability = SensorReliability(sensor_id="sensor-1", reliability=0.75)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            reliability.reliability = 0.1  # type: ignore[misc]


class SensorReliabilityStoreTests(unittest.TestCase):
    def test_unknown_sensor_returns_the_neutral_default(self) -> None:
        store = SensorReliabilityStore()

        self.assertEqual(store.get("unknown"), DEFAULT_SENSOR_RELIABILITY)
        self.assertEqual(store.read_all(), [])

    def test_put_and_get_round_trip(self) -> None:
        store = SensorReliabilityStore()

        store.put(SensorReliability(sensor_id="sensor-1", reliability=0.4))

        self.assertEqual(store.get("sensor-1"), 0.4)
        self.assertEqual(store.read_all(), [SensorReliability(sensor_id="sensor-1", reliability=0.4)])

    def test_put_replaces_existing_reliability(self) -> None:
        store = SensorReliabilityStore()

        store.put(SensorReliability(sensor_id="sensor-1", reliability=0.4))
        store.put(SensorReliability(sensor_id="sensor-1", reliability=0.9))

        self.assertEqual(store.get("sensor-1"), 0.9)


def publish_observation(
    kernel: Kernel, *, sensor_id: str, normalized_value: float = 0.5, confidence: float = 0.8
) -> None:
    kernel.publish(
        ObservationCreatedEvent(
            source_component="perception",
            observation_id=str(uuid4()),
            sensor_id=sensor_id,
            normalized_value=normalized_value,
            confidence=confidence,
            raw_source_type="test",
        )
    )


def publish_sensor_reliability(kernel: Kernel, *, sensor_id: str, reliability: float) -> None:
    kernel.publish(
        SensorReliabilityUpdatedEvent(
            source_component="memory_ledger",
            sensor_id=sensor_id,
            reliability=reliability,
            predictions_considered=1,
        )
    )


class WorldModelSensorReliabilityTests(unittest.TestCase):
    def test_sensor_reliability_updated_event_only_mutates_the_cache_there(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)

        publish_sensor_reliability(kernel, sensor_id="sensor-1", reliability=0.3)

        self.assertEqual(world_model.sensor_reliability_store.get("sensor-1"), 0.3)

    def test_an_unscored_sensor_behaves_exactly_as_before_fast_learning(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)

        publish_observation(kernel, sensor_id="sensor-1", normalized_value=0.5, confidence=0.8)

        self.assertEqual(world_model.belief_store.read_all()[0].confidence, 0.8)

    def test_a_low_reliability_sensor_contributes_less_confidence_to_a_new_belief(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)
        publish_sensor_reliability(kernel, sensor_id="sensor-1", reliability=0.25)

        publish_observation(kernel, sensor_id="sensor-1", normalized_value=0.5, confidence=0.8)

        self.assertAlmostEqual(world_model.belief_store.read_all()[0].confidence, 0.8 * 0.25)

    def test_reliable_sensors_contribute_more_confidence_than_unreliable_sensors(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)
        publish_sensor_reliability(kernel, sensor_id="reliable", reliability=0.9)
        publish_sensor_reliability(kernel, sensor_id="unreliable", reliability=0.2)

        publish_observation(kernel, sensor_id="reliable", normalized_value=0.5, confidence=0.8)
        publish_observation(kernel, sensor_id="unreliable", normalized_value=0.5, confidence=0.8)

        beliefs = {belief.provenance: belief for belief in world_model.belief_store.read_all()}
        self.assertGreater(beliefs["reliable"].confidence, beliefs["unreliable"].confidence)

    def test_confidence_changes_as_reliability_changes(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)

        publish_sensor_reliability(kernel, sensor_id="sensor-1", reliability=1.0)
        publish_observation(kernel, sensor_id="sensor-1", normalized_value=0.5, confidence=0.8)
        first_confidence = world_model.belief_store.get("sensor:sensor-1").confidence

        publish_sensor_reliability(kernel, sensor_id="sensor-1", reliability=0.1)
        publish_observation(kernel, sensor_id="sensor-1", normalized_value=0.5, confidence=0.8)
        second_confidence = world_model.belief_store.get("sensor:sensor-1").confidence

        self.assertLess(second_confidence, first_confidence)

    def test_updated_belief_also_weights_incoming_evidence_by_reliability(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)
        publish_sensor_reliability(kernel, sensor_id="sensor-1", reliability=0.5)

        publish_observation(kernel, sensor_id="sensor-1", normalized_value=0.4, confidence=0.6)
        first = world_model.belief_store.get("sensor:sensor-1").confidence
        self.assertAlmostEqual(first, 0.6 * 0.5)

        publish_observation(kernel, sensor_id="sensor-1", normalized_value=0.5, confidence=1.0)
        second = world_model.belief_store.get("sensor:sensor-1").confidence
        self.assertAlmostEqual(second, (first + 1.0 * 0.5) / 2)


class WorldModelSensorReliabilityReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.log_path = Path(tmpdir.name) / "events.jsonl"

    def test_replay_reconstructs_reliability(self) -> None:
        event_log = EventLog(path=self.log_path)
        kernel = Kernel(event_log=event_log)
        world_model = WorldModel(kernel)

        publish_sensor_reliability(kernel, sensor_id="sensor-1", reliability=0.3)
        publish_observation(kernel, sensor_id="sensor-1", normalized_value=0.5, confidence=0.8)

        rebuilt_kernel = Kernel(event_log=EventLog(path=self.log_path))
        rebuilt_world_model = WorldModel(rebuilt_kernel)
        rebuilt_kernel.replay()

        self.assertEqual(rebuilt_world_model.sensor_reliability_store.get("sensor-1"), 0.3)
        self.assertEqual(
            rebuilt_world_model.belief_store.read_all(), world_model.belief_store.read_all()
        )


class WorldModelSensorReliabilitySnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_reliability(self) -> None:
        kernel = Kernel()
        world_model = WorldModel(kernel)

        publish_sensor_reliability(kernel, sensor_id="sensor-1", reliability=0.3)
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_world_model = WorldModel(rebuilt_kernel)
        rebuilt_kernel.replay()

        self.assertEqual(rebuilt_world_model.sensor_reliability_store.get("sensor-1"), 0.3)

        # Confidence weighting must use the restored reliability, not the
        # neutral default, for a fresh observation processed after restore.
        publish_observation(rebuilt_kernel, sensor_id="sensor-1", normalized_value=0.5, confidence=0.8)
        self.assertAlmostEqual(rebuilt_world_model.belief_store.get("sensor:sensor-1").confidence, 0.8 * 0.3)


if __name__ == "__main__":
    unittest.main()
