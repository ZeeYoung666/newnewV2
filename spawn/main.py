"""Composition root: wires the organism as a single running system.

Constructs exactly one Kernel and exactly one instance of every component
against it, then proves the wiring is alive by driving one observation
through the full Observation -> Belief -> Opportunity -> Plan -> Approval ->
Execution -> Outcome -> Memory flow using only typed events.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.executive import Executive
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


def build_organism() -> Organism:
    """Construct one Kernel and exactly one instance of every component against it.

    Each component registers its own event subscriptions inside its
    constructor, so calling each constructor exactly once here registers
    every subscription exactly once.
    """
    kernel = Kernel()

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
            rules=("non_negative_costs",),
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


if __name__ == "__main__":
    main()
