import io
import unittest

import main
from src.events import EventType, ObservationCreatedEvent
from src.kernel import Kernel


class AttachEventStreamTests(unittest.TestCase):
    def test_subscribes_to_every_event_type(self) -> None:
        kernel = Kernel()
        main.attach_event_stream(kernel, stream=io.StringIO(), color=False)

        for event_type in EventType:
            self.assertGreaterEqual(len(kernel._subscribers[event_type]), 1)

    def test_prints_one_line_with_timestamp_type_and_correlation_id(self) -> None:
        buffer = io.StringIO()
        kernel = Kernel()
        main.attach_event_stream(kernel, stream=buffer, color=False)

        event = ObservationCreatedEvent(
            source_component="test",
            observation_id="obs-1",
            sensor_id="sensor-1",
            normalized_value=1.0,
            confidence=0.5,
            raw_source_type="research",
        )
        kernel.publish(event)

        lines = [line for line in buffer.getvalue().splitlines() if line]
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertIn(EventType.OBSERVATION_CREATED.value, line)
        self.assertIn(f"correlation_id={event.correlation_id}", line)
        self.assertIn("sensor_id='sensor-1'", line)

    def test_color_disabled_emits_no_ansi_codes(self) -> None:
        buffer = io.StringIO()
        kernel = Kernel()
        main.attach_event_stream(kernel, stream=buffer, color=False)

        kernel.publish(
            ObservationCreatedEvent(
                source_component="test",
                observation_id="obs-1",
                sensor_id="sensor-1",
                normalized_value=1.0,
                confidence=0.5,
                raw_source_type="research",
            )
        )

        self.assertNotIn("\x1b[", buffer.getvalue())

    def test_color_enabled_wraps_known_prefix_in_ansi_codes(self) -> None:
        buffer = io.StringIO()
        kernel = Kernel()
        main.attach_event_stream(kernel, stream=buffer, color=True)

        kernel.publish(
            ObservationCreatedEvent(
                source_component="test",
                observation_id="obs-1",
                sensor_id="sensor-1",
                normalized_value=1.0,
                confidence=0.5,
                raw_source_type="research",
            )
        )

        output = buffer.getvalue()
        self.assertIn("\x1b[34m", output)  # observation.* -> blue
        self.assertIn(main._EVENT_STREAM_RESET, output)

    def test_printer_never_raises_when_a_field_repr_fails(self) -> None:
        buffer = io.StringIO()
        kernel = Kernel()
        main.attach_event_stream(kernel, stream=buffer, color=False)

        class Explodes:
            def __repr__(self) -> str:
                raise RuntimeError("boom")

        event = ObservationCreatedEvent(
            source_component="test",
            observation_id="obs-1",
            sensor_id="sensor-1",
            normalized_value=1.0,
            confidence=0.5,
            raw_source_type="research",
        )
        event.raw_source_type = Explodes()  # type: ignore[assignment]

        # Call the registered printer directly: routing this through
        # kernel.publish would fail first in EventLog's own JSON
        # serialization, which isn't what this test is about — it's
        # asserting the printer itself is defensive.
        printer = kernel._subscribers[EventType.OBSERVATION_CREATED][0]
        printer(event)  # must not raise

        self.assertIn("unprintable event", buffer.getvalue())

    def test_stream_survives_every_event_type_in_a_full_explore_cycle_without_crashing(self) -> None:
        buffer = io.StringIO()
        organism = main.build_organism()
        main.configure_bootstrap(organism)
        main.attach_event_stream(organism.kernel, stream=buffer, color=False)

        organism.kernel.start()
        main.run_exploration_cycle(organism)
        organism.kernel.stop()

        output = buffer.getvalue()
        lines = [line for line in output.splitlines() if line]
        self.assertGreater(len(lines), 0)
        self.assertNotIn("unprintable event", output)

        printed_types = {line.split()[1] for line in lines}
        for expected in (
            EventType.RESEARCH_SPEND_REQUESTED,
            EventType.RESEARCH_SPEND_APPROVED,
            EventType.RESEARCH_INTENT_EMITTED,
            EventType.OBSERVATION_CREATED,
            EventType.BELIEF_CREATED,
            EventType.PLAN_PROPOSED,
            EventType.APPROVAL_GRANTED,
            EventType.ACTION_SUCCEEDED,
            EventType.OUTCOME_RECORDED,
        ):
            self.assertIn(expected.value, printed_types)


class RunExplorationCycleTimeoutTests(unittest.TestCase):
    def test_generous_timeout_prints_no_warning(self) -> None:
        import sys
        from io import StringIO

        organism = main.build_organism()
        main.configure_bootstrap(organism)
        organism.kernel.start()

        stderr = StringIO()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            main.run_exploration_cycle(organism, timeout=DEFAULT_TIMEOUT_FOR_TEST)
        finally:
            sys.stderr = old_stderr
            organism.kernel.stop()

        self.assertNotIn("exceeding", stderr.getvalue())

    def test_zero_timeout_reports_a_warning_but_still_completes(self) -> None:
        import sys
        from io import StringIO

        organism = main.build_organism()
        main.configure_bootstrap(organism)
        organism.kernel.start()

        stderr = StringIO()
        old_stderr = sys.stderr
        sys.stderr = stderr
        try:
            request_ids = main.run_exploration_cycle(organism, timeout=0.0)
        finally:
            sys.stderr = old_stderr
            organism.kernel.stop()

        self.assertTrue(request_ids)
        self.assertIn("exceeding the 0.00s timeout", stderr.getvalue())


DEFAULT_TIMEOUT_FOR_TEST = 30.0


if __name__ == "__main__":
    unittest.main()
