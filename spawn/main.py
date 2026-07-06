"""Composition root: wires the organism as a single running system.

Constructs exactly one Kernel and exactly one instance of every component
against it, then proves the wiring is alive by driving one observation
through the full Observation -> Belief -> Opportunity -> Plan -> Approval ->
Execution -> Outcome -> Memory flow using only typed events.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, fields as dataclass_fields
from typing import IO, Optional

from src.events import Event, EventType
from src.executive import (
    COLD_START_ESTIMATED_COST_PER_QUERY,
    COLD_START_SEARCH_DEPTH,
    COLD_START_SEED_QUERIES,
    Executive,
    ResearchCandidate,
)
from src.executor import Executor
from src.governor import BudgetState, Constitution, Governor
from src.inference import InferencePort, MockInferenceProvider, ProviderRegistry
from src.kernel import Kernel
from src.memory import MemoryLedger
from src.perception import Observation, Perception
from src.world_model import WorldModel

BOOTSTRAP_SENSOR_ID = "bootstrap-sensor"
BOOTSTRAP_ACTION_TYPES = ("investigate", "act_on")
BOOTSTRAP_CONSTITUTION_ID = "bootstrap-constitution"
BOOTSTRAP_BUDGET_ID = "bootstrap-budget"
BOOTSTRAP_AVAILABLE_ATTENTION = 100.0
BOOTSTRAP_AVAILABLE_CAPITAL = 1000.0
BOOTSTRAP_OBSERVATION_VALUE = 1.0
BOOTSTRAP_OBSERVATION_CONFIDENCE = 0.9
BOOTSTRAP_RESEARCH_BUDGET = 50.0
BOOTSTRAP_RESEARCH_BUDGET_WINDOW_SECONDS = 86400.0
BOOTSTRAP_MAX_SEARCHES_PER_DELIBERATION = 5
BOOTSTRAP_MAX_SEARCH_DEPTH = 3
EXPLORATION_DELIBERATION_ID = "manual-exploration"
DEFAULT_EXPLORATION_TIMEOUT_SECONDS = 30.0

# Minimal exploration visibility (CLI): a read-only printer, registered
# against every EventType, that streams each event to stdout as the Kernel
# dispatches it. Colors group events by owning component; ANSI codes are
# skipped entirely when the stream isn't a real terminal or NO_COLOR is set
# (https://no-color.org), so redirected/piped output stays plain text.
_EVENT_STREAM_RESET = "\033[0m"
_EVENT_STREAM_BLUE = "\033[34m"  # research / perception
_EVENT_STREAM_PURPLE = "\033[35m"  # beliefs / opportunities / plans
_EVENT_STREAM_GOLD = "\033[33m"  # governor
_EVENT_STREAM_GREEN = "\033[32m"  # execution
_EVENT_STREAM_CYAN = "\033[36m"  # memory / learning
_EVENT_STREAM_COLOR_BY_PREFIX: dict[str, str] = {
    "research": _EVENT_STREAM_BLUE,
    "observation": _EVENT_STREAM_BLUE,
    "sensor": _EVENT_STREAM_BLUE,
    "inference": _EVENT_STREAM_BLUE,
    "belief": _EVENT_STREAM_PURPLE,
    "opportunity": _EVENT_STREAM_PURPLE,
    "plan": _EVENT_STREAM_PURPLE,
    "executive": _EVENT_STREAM_PURPLE,
    "policy": _EVENT_STREAM_GOLD,
    "budget": _EVENT_STREAM_GOLD,
    "approval": _EVENT_STREAM_GOLD,
    "constitution": _EVENT_STREAM_GOLD,
    "escalation": _EVENT_STREAM_GOLD,
    "action": _EVENT_STREAM_GREEN,
    "sandbox": _EVENT_STREAM_GREEN,
    "credential": _EVENT_STREAM_GREEN,
    "outcome": _EVENT_STREAM_CYAN,
    "prediction": _EVENT_STREAM_CYAN,
    "learning": _EVENT_STREAM_CYAN,
    "knowledge": _EVENT_STREAM_CYAN,
    "ledger": _EVENT_STREAM_CYAN,
}
# event_type values not covered above (currently just "kernel.*" lifecycle
# events) print uncolored rather than raising a KeyError.
_EVENT_STREAM_BASE_FIELDS = {
    "source_component",
    "id",
    "timestamp",
    "correlation_id",
    "event_type",
    "event_version",
}


def _format_event_line(event: Event) -> str:
    """One line: timestamp, event type, correlation_id, then every field the
    concrete event subclass adds beyond the common Event base — whatever
    that event actually carries today, nothing assumed or stubbed for a
    stage that isn't wired yet.
    """
    extra = ", ".join(
        f"{f.name}={getattr(event, f.name)!r}"
        for f in dataclass_fields(event)
        if f.name not in _EVENT_STREAM_BASE_FIELDS
    )
    timestamp = event.timestamp.isoformat(timespec="milliseconds")
    return f"{timestamp} {event.event_type.value:<32} correlation_id={event.correlation_id} {extra}"


def _colorize_event_line(event_type: EventType, line: str) -> str:
    prefix = event_type.value.split(".", 1)[0]
    color = _EVENT_STREAM_COLOR_BY_PREFIX.get(prefix, "")
    return f"{color}{line}{_EVENT_STREAM_RESET}" if color else line


def attach_event_stream(kernel: Kernel, *, stream: Optional[IO[str]] = None, color: Optional[bool] = None) -> None:
    """Read-only observer: print every event live as the Kernel dispatches it.

    Kernel.register_subscriber has no wildcard, so the only way to observe
    the full bus is to register the same printer against every EventType
    member individually — still just "adding a subscriber", the same
    mechanism every component already uses, nothing added to the Kernel
    itself. This function never publishes an event, never reads or mutates
    any component's state, and cannot affect replay (Kernel.publish
    dispatches to subscribers exactly the same during a live run or a
    replay; this only ever prints).
    """
    out = stream if stream is not None else sys.stdout
    use_color = color if color is not None else (hasattr(out, "isatty") and out.isatty() and "NO_COLOR" not in os.environ)

    def _print_event(event: Event) -> None:
        try:
            line = _format_event_line(event)
            line = _colorize_event_line(event.event_type, line) if use_color else line
        except Exception as exc:  # a formatting bug must never break the pipeline it's observing
            line = f"<unprintable event {event.event_type!r}: {exc!r}>"
        print(line, file=out, flush=True)

    for event_type in EventType:
        kernel.register_subscriber(event_type, _print_event)


@dataclass(slots=True)
class Organism:
    """Every component, wired against the one shared Kernel."""

    kernel: Kernel
    perception: Perception
    world_model: WorldModel
    executive: Executive
    governor: Governor
    executor: Executor
    memory_ledger: MemoryLedger
    provider_registry: ProviderRegistry
    inference_port: InferencePort


def build_organism(kernel: Optional[Kernel] = None) -> Organism:
    """Construct one Kernel and exactly one instance of every component against it.

    Each component registers its own event subscriptions inside its
    constructor, so calling each constructor exactly once here registers
    every subscription exactly once.

    Pass an existing ``Kernel`` (wired to a persistent EventLog) to rebuild
    the organism against previously recorded history; its Kernel.start()
    will replay that history before normal scheduling begins. With no
    argument, a fresh in-memory Kernel is constructed for a first boot.
    """
    kernel = kernel if kernel is not None else Kernel()

    perception = Perception(kernel)
    world_model = WorldModel(kernel)
    executive = Executive(kernel)
    governor = Governor(kernel)
    executor = Executor(kernel)
    memory_ledger = MemoryLedger(kernel)

    provider_registry = ProviderRegistry()
    provider_registry.register("mock", MockInferenceProvider())
    provider_registry.set_active("mock")
    inference_port = InferencePort(kernel, provider_registry)
    executive.attach_inference_port(inference_port)

    return Organism(
        kernel=kernel,
        perception=perception,
        world_model=world_model,
        executive=executive,
        governor=governor,
        executor=executor,
        memory_ledger=memory_ledger,
        provider_registry=provider_registry,
        inference_port=inference_port,
    )


def configure_bootstrap(organism: Organism) -> None:
    """Configure the governance and execution surface the bootstrap cycle needs.

    This is prerequisite setup (constitution, budget, sensor, tools) — the
    same kind of direct configuration every component's own unit tests use
    before publishing an event. It is not part of the Observation -> Memory
    event flow itself.
    """
    organism.governor.adopt_constitution(
        Constitution(
            constitution_id=BOOTSTRAP_CONSTITUTION_ID,
            version=1,
            rules=(
                "non_negative_costs",
                f"research_budget:{BOOTSTRAP_RESEARCH_BUDGET},{BOOTSTRAP_RESEARCH_BUDGET_WINDOW_SECONDS}",
                f"max_searches_per_deliberation:{BOOTSTRAP_MAX_SEARCHES_PER_DELIBERATION}",
                f"max_search_depth:{BOOTSTRAP_MAX_SEARCH_DEPTH}",
            ),
        )
    )
    organism.governor.fund_budget(
        BudgetState(
            budget_id=BOOTSTRAP_BUDGET_ID,
            available_attention=BOOTSTRAP_AVAILABLE_ATTENTION,
            available_capital=BOOTSTRAP_AVAILABLE_CAPITAL,
        )
    )
    organism.perception.sensor_registry.register_sensor(
        sensor_id=BOOTSTRAP_SENSOR_ID,
        name="Bootstrap Sensor",
        source_type="bootstrap",
    )
    for action_type in BOOTSTRAP_ACTION_TYPES:
        organism.executor.tool_registry.register(
            action_type, lambda action: f"{action.action_type} completed"
        )


def run_bootstrap_cycle(organism: Organism) -> Observation:
    """Publish one observation and drain the Kernel until the full cycle completes.

    The observation is the only entry point touched directly; everything
    downstream of it (belief, opportunity, plan, approval, execution,
    outcome, memory) happens exclusively through typed events dispatched by
    the Kernel.
    """
    observation = organism.perception.record_observation(
        sensor_id=BOOTSTRAP_SENSOR_ID,
        normalized_value=BOOTSTRAP_OBSERVATION_VALUE,
        confidence=BOOTSTRAP_OBSERVATION_CONFIDENCE,
        raw_source_type="bootstrap",
    )
    organism.kernel.run_until_idle()
    return observation


def main() -> Organism:
    """Boot the organism: build it, configure it, start the Kernel, and prove it is alive."""
    organism = build_organism()
    configure_bootstrap(organism)
    organism.kernel.start()
    run_bootstrap_cycle(organism)
    organism.kernel.stop()
    return organism


def run_exploration_cycle(
    organism: Organism, *, timeout: float = DEFAULT_EXPLORATION_TIMEOUT_SECONDS
) -> list[Optional[str]]:
    """Fire one Economic Exploration cycle from the current objective, then drain it to completion.

    Touches exactly one public entry point on the running organism —
    ``Executive.request_research_batch`` — the same objective-driven research
    API the cold-start seeding path already uses internally (Charter §2/§6:
    broad, industry-agnostic discovery queries derived from the objective,
    never a specific venture pick). Everything downstream of that call
    (Governor's approve/deny decision, Executive's own ResearchIntentEvent
    emission, and whatever else is currently wired to react from there)
    happens exclusively through the Kernel's typed events — this function
    never touches Perception, World Model, Governor, Executor, or Memory
    directly, and it never calls Executive.deliberate() (that stage is an
    internal organism concern, not something a manual trigger reaches into).

    Fires once and returns; no scheduler, no loop. Returns once the Kernel's
    event queue is fully drained, carrying whatever request_ids the batch
    produced (a request_id is ``None`` where the soft-stop heuristic declined
    to even ask — see ``Executive.request_research``).

    ``timeout`` is a wall-clock budget this reports against, not one it
    preempts: every stage in this pipeline is synchronous and network-free,
    so there is nothing to interrupt mid-flight without racing the Kernel's
    own event-log writes — which would risk exactly the replay-determinism
    guarantee this CLI path must not touch. If the cycle still exceeds the
    budget, a warning is printed to stderr after the fact; the cycle itself
    always runs to completion.
    """
    started_at = time.monotonic()
    candidates = [
        ResearchCandidate(
            query=query,
            estimated_cost=COLD_START_ESTIMATED_COST_PER_QUERY,
            search_depth=COLD_START_SEARCH_DEPTH,
            priority=priority,
            rationale="manual exploration cycle: derived from the current objective",
            deliberation_id=EXPLORATION_DELIBERATION_ID,
        )
        for query, priority in COLD_START_SEED_QUERIES
    ]
    request_ids = organism.executive.request_research_batch(candidates)
    organism.kernel.run_until_idle()
    elapsed = time.monotonic() - started_at
    if elapsed > timeout:
        print(f"[explore] cycle took {elapsed:.2f}s, exceeding the {timeout:.2f}s timeout", file=sys.stderr)
    return request_ids


def _cli() -> None:
    """CLI dispatch: ``python main.py [bootstrap|explore]`` (defaults to bootstrap).

    No packaging/console-script exists for this project, so there is no
    installed ``aether`` binary — invoke as ``python main.py explore``.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="main.py")
    parser.add_argument("command", nargs="?", default="bootstrap", choices=("bootstrap", "explore"))
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_EXPLORATION_TIMEOUT_SECONDS,
        help="explore only: wall-clock seconds the cycle is expected to finish within (default: %(default)s)",
    )
    args = parser.parse_args()

    if args.command == "explore":
        organism = build_organism()
        configure_bootstrap(organism)
        attach_event_stream(organism.kernel)
        organism.kernel.start()
        run_exploration_cycle(organism, timeout=args.timeout)
        organism.kernel.stop()
    else:
        main()


if __name__ == "__main__":
    _cli()
