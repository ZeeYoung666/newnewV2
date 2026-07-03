import dataclasses
import unittest

from src.events import Event, EventType, ObservationCreatedEvent
from src.kernel import Kernel
from src.perception import (
    AdapterRegistry,
    FlatValueAdapter,
    NestedReadingAdapter,
    Observation,
    ObservationLog,
    Perception,
    SensorRegistry,
)


class SensorRegistryTests(unittest.TestCase):
    def test_register_sensor_stores_metadata_and_marks_active(self) -> None:
        registry = SensorRegistry()

        registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        metadata = registry.get_metadata("sensor-1")
        self.assertEqual(metadata.sensor_id, "sensor-1")
        self.assertEqual(metadata.name, "Price Feed")
        self.assertEqual(metadata.source_type, "market_feed")
        self.assertTrue(registry.is_active("sensor-1"))

    def test_registering_duplicate_sensor_id_raises(self) -> None:
        registry = SensorRegistry()
        registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        with self.assertRaises(ValueError):
            registry.register_sensor(sensor_id="sensor-1", name="Other Feed", source_type="market_feed")

    def test_unregister_sensor_removes_it(self) -> None:
        registry = SensorRegistry()
        registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        registry.unregister_sensor("sensor-1")

        self.assertFalse(registry.is_active("sensor-1"))
        with self.assertRaises(KeyError):
            registry.get_metadata("sensor-1")

    def test_get_metadata_raises_for_unknown_sensor(self) -> None:
        registry = SensorRegistry()

        with self.assertRaises(KeyError):
            registry.get_metadata("unknown")

    def test_is_active_returns_false_for_unknown_sensor(self) -> None:
        registry = SensorRegistry()

        self.assertFalse(registry.is_active("unknown"))


class ObservationModelTests(unittest.TestCase):
    def test_observation_carries_required_fields(self) -> None:
        observation = Observation(
            sensor_id="sensor-1",
            normalized_value=0.75,
            confidence=0.9,
            raw_source_type="market_feed",
        )

        self.assertEqual(observation.sensor_id, "sensor-1")
        self.assertEqual(observation.normalized_value, 0.75)
        self.assertEqual(observation.confidence, 0.9)
        self.assertEqual(observation.raw_source_type, "market_feed")
        self.assertIsNotNone(observation.observation_id)
        self.assertIsNotNone(observation.timestamp)

    def test_observation_is_immutable(self) -> None:
        observation = Observation(
            sensor_id="sensor-1",
            normalized_value=0.75,
            confidence=0.9,
            raw_source_type="market_feed",
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            observation.normalized_value = 0.1  # type: ignore[misc]


class ObservationLogTests(unittest.TestCase):
    def test_append_assigns_increasing_sequence_and_read_all_returns_in_order(self) -> None:
        log = ObservationLog()
        first = Observation(sensor_id="sensor-1", normalized_value=0.1, confidence=0.5, raw_source_type="market_feed")
        second = Observation(sensor_id="sensor-2", normalized_value=0.2, confidence=0.6, raw_source_type="market_feed")

        log.append(first)
        log.append(second)

        stored = log.read_all()
        self.assertEqual([sequence for sequence, _ in stored], [1, 2])
        self.assertEqual([observation for _, observation in stored], [first, second])

    def test_read_from_returns_suffix_without_mutating_entries(self) -> None:
        log = ObservationLog()
        first = Observation(sensor_id="sensor-1", normalized_value=0.1, confidence=0.5, raw_source_type="market_feed")
        second = Observation(sensor_id="sensor-2", normalized_value=0.2, confidence=0.6, raw_source_type="market_feed")
        third = Observation(sensor_id="sensor-3", normalized_value=0.3, confidence=0.7, raw_source_type="market_feed")

        log.append(first)
        log.append(second)
        log.append(third)

        suffix = log.read_from(2)
        self.assertEqual([sequence for sequence, _ in suffix], [2, 3])
        self.assertEqual([observation for _, observation in suffix], [second, third])

        original = log.read_all()
        self.assertEqual([observation for _, observation in original], [first, second, third])


class PerceptionTests(unittest.TestCase):
    def test_record_observation_creates_appends_and_publishes_event(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        received: list[Event] = []
        kernel.register_subscriber(EventType.OBSERVATION_CREATED, received.append)

        observation = perception.record_observation(
            sensor_id="sensor-1",
            normalized_value=0.42,
            confidence=0.8,
            raw_source_type="market_feed",
        )

        self.assertEqual(
            [observation for _, observation in perception.observation_log.read_all()],
            [observation],
        )
        self.assertEqual(len(received), 1)
        published = received[0]
        self.assertIsInstance(published, ObservationCreatedEvent)
        self.assertEqual(published.observation_id, str(observation.observation_id))
        self.assertEqual(published.sensor_id, "sensor-1")
        self.assertEqual(published.normalized_value, 0.42)
        self.assertEqual(published.confidence, 0.8)
        self.assertEqual(published.raw_source_type, "market_feed")
        self.assertEqual([event for _, event in kernel.event_log.read_all()], [published])

    def test_record_observation_rejects_unregistered_sensor(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)

        with self.assertRaises(ValueError):
            perception.record_observation(
                sensor_id="unknown",
                normalized_value=0.1,
                confidence=0.5,
                raw_source_type="market_feed",
            )

        self.assertEqual(perception.observation_log.read_all(), [])

    def test_record_observation_rejects_inactive_sensor(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")
        perception.sensor_registry.unregister_sensor("sensor-1")

        with self.assertRaises(ValueError):
            perception.record_observation(
                sensor_id="sensor-1",
                normalized_value=0.1,
                confidence=0.5,
                raw_source_type="market_feed",
            )

    def test_record_observation_rejects_confidence_out_of_range(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        with self.assertRaises(ValueError):
            perception.record_observation(
                sensor_id="sensor-1",
                normalized_value=0.1,
                confidence=1.5,
                raw_source_type="market_feed",
            )

        self.assertEqual(perception.observation_log.read_all(), [])


class AdapterRegistryTests(unittest.TestCase):
    def test_flat_value_adapter_accepts_and_normalizes(self) -> None:
        adapter = FlatValueAdapter()
        payload = {"value": 0.42, "confidence": 0.8}

        self.assertTrue(adapter.accepts(payload))
        reading = adapter.normalize(payload)
        self.assertEqual(reading.normalized_value, 0.42)
        self.assertEqual(reading.confidence, 0.8)

    def test_flat_value_adapter_rejects_nested_payload(self) -> None:
        adapter = FlatValueAdapter()

        self.assertFalse(adapter.accepts({"reading": {"amount": 0.42, "quality": 0.8}}))

    def test_nested_reading_adapter_accepts_and_normalizes(self) -> None:
        adapter = NestedReadingAdapter()
        payload = {"reading": {"amount": 0.42, "quality": 0.8}}

        self.assertTrue(adapter.accepts(payload))
        reading = adapter.normalize(payload)
        self.assertEqual(reading.normalized_value, 0.42)
        self.assertEqual(reading.confidence, 0.8)

    def test_nested_reading_adapter_rejects_flat_payload(self) -> None:
        adapter = NestedReadingAdapter()

        self.assertFalse(adapter.accepts({"value": 0.42, "confidence": 0.8}))

    def test_registry_selects_first_accepting_adapter_in_registration_order(self) -> None:
        registry = AdapterRegistry()
        registry.register(FlatValueAdapter())
        registry.register(NestedReadingAdapter())

        flat_reading = registry.normalize({"value": 0.1, "confidence": 0.2})
        nested_reading = registry.normalize({"reading": {"amount": 0.3, "quality": 0.4}})

        self.assertEqual((flat_reading.normalized_value, flat_reading.confidence), (0.1, 0.2))
        self.assertEqual((nested_reading.normalized_value, nested_reading.confidence), (0.3, 0.4))

    def test_registry_selection_is_deterministic_with_a_third_adapter(self) -> None:
        class AlwaysAcceptsAdapter:
            def accepts(self, payload: object) -> bool:
                return True

            def normalize(self, payload: object) -> "NormalizedReading":  # noqa: F821
                raise AssertionError("should never be reached: an earlier adapter must win")

        registry = AdapterRegistry()
        registry.register(FlatValueAdapter())
        registry.register(NestedReadingAdapter())
        registry.register(AlwaysAcceptsAdapter())

        reading = registry.normalize({"value": 0.5, "confidence": 0.6})

        self.assertEqual((reading.normalized_value, reading.confidence), (0.5, 0.6))

    def test_registry_rejects_unsupported_payload(self) -> None:
        registry = AdapterRegistry()
        registry.register(FlatValueAdapter())
        registry.register(NestedReadingAdapter())

        with self.assertRaises(ValueError):
            registry.normalize({"unknown_shape": True})


class PerceptionRecordRawObservationTests(unittest.TestCase):
    def test_flat_and_nested_payloads_normalize_to_identical_observation(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        flat_observation = perception.record_raw_observation(
            sensor_id="sensor-1", payload={"value": 0.42, "confidence": 0.8}
        )

        kernel2 = Kernel()
        perception2 = Perception(kernel2)
        perception2.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        nested_observation = perception2.record_raw_observation(
            sensor_id="sensor-1", payload={"reading": {"amount": 0.42, "quality": 0.8}}
        )

        self.assertEqual(flat_observation.sensor_id, nested_observation.sensor_id)
        self.assertEqual(flat_observation.normalized_value, nested_observation.normalized_value)
        self.assertEqual(flat_observation.confidence, nested_observation.confidence)
        self.assertEqual(flat_observation.raw_source_type, nested_observation.raw_source_type)

    def test_record_raw_observation_derives_raw_source_type_from_sensor_metadata(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="News Feed", source_type="news_feed")

        observation = perception.record_raw_observation(
            sensor_id="sensor-1", payload={"value": 0.1, "confidence": 0.5}
        )

        self.assertEqual(observation.raw_source_type, "news_feed")

    def test_record_raw_observation_appends_and_publishes_event(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        received: list[Event] = []
        kernel.register_subscriber(EventType.OBSERVATION_CREATED, received.append)

        observation = perception.record_raw_observation(
            sensor_id="sensor-1", payload={"value": 0.42, "confidence": 0.8}
        )

        self.assertEqual(
            [observation for _, observation in perception.observation_log.read_all()],
            [observation],
        )
        self.assertEqual(len(received), 1)
        published = received[0]
        self.assertIsInstance(published, ObservationCreatedEvent)
        self.assertEqual(published.observation_id, str(observation.observation_id))
        self.assertEqual(published.sensor_id, "sensor-1")
        self.assertEqual(published.normalized_value, 0.42)
        self.assertEqual(published.confidence, 0.8)
        self.assertEqual(published.raw_source_type, "market_feed")
        self.assertEqual([event for _, event in kernel.event_log.read_all()], [published])

    def test_record_raw_observation_rejects_unregistered_sensor(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)

        with self.assertRaises(ValueError):
            perception.record_raw_observation(sensor_id="unknown", payload={"value": 0.1, "confidence": 0.5})

        self.assertEqual(perception.observation_log.read_all(), [])

    def test_record_raw_observation_rejects_inactive_sensor(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")
        perception.sensor_registry.unregister_sensor("sensor-1")

        with self.assertRaises(ValueError):
            perception.record_raw_observation(sensor_id="sensor-1", payload={"value": 0.1, "confidence": 0.5})

    def test_record_raw_observation_rejects_unsupported_payload(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        with self.assertRaises(ValueError):
            perception.record_raw_observation(sensor_id="sensor-1", payload={"unknown_shape": True})

        self.assertEqual(perception.observation_log.read_all(), [])

    def test_record_raw_observation_rejects_confidence_out_of_range(self) -> None:
        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Price Feed", source_type="market_feed")

        with self.assertRaises(ValueError):
            perception.record_raw_observation(sensor_id="sensor-1", payload={"value": 0.1, "confidence": 1.5})

        self.assertEqual(perception.observation_log.read_all(), [])

    def test_custom_adapter_can_be_registered_and_is_selected_when_it_accepts(self) -> None:
        class ScaledPercentAdapter:
            """Accepts {"percent": 0-100, "quality_flag": 0 or 1} and rescales to canonical range."""

            def accepts(self, payload: object) -> bool:
                return isinstance(payload, dict) and "percent" in payload and "quality_flag" in payload

            def normalize(self, payload: object):
                from src.perception import NormalizedReading

                assert isinstance(payload, dict)
                return NormalizedReading(
                    normalized_value=payload["percent"] / 100.0,
                    confidence=float(payload["quality_flag"]),
                )

        kernel = Kernel()
        perception = Perception(kernel)
        perception.sensor_registry.register_sensor(sensor_id="sensor-1", name="Legacy Feed", source_type="legacy_feed")
        perception.adapter_registry.register(ScaledPercentAdapter())

        observation = perception.record_raw_observation(
            sensor_id="sensor-1", payload={"percent": 42, "quality_flag": 1}
        )

        self.assertEqual(observation.normalized_value, 0.42)
        self.assertEqual(observation.confidence, 1.0)

        # Built-in adapters registered before the custom one still win for their own shapes.
        flat_observation = perception.record_raw_observation(
            sensor_id="sensor-1", payload={"value": 0.9, "confidence": 0.7}
        )
        self.assertEqual(flat_observation.normalized_value, 0.9)


if __name__ == "__main__":
    unittest.main()
