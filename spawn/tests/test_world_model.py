import dataclasses
import unittest
from datetime import datetime, timedelta, timezone

from src.events import BeliefCreatedEvent, BeliefUpdatedEvent, Event, EventType
from src.kernel import Kernel
from src.perception import Perception
from src.world_model import Belief, BeliefStore, WorldModel


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


if __name__ == "__main__":
    unittest.main()
