---
name: gortex-2-dirs-test-core-event-models-are-impo
description: "Work in the . +2 dirs · test_core_event_models_are_impo… area — 23 symbols across 12 files (69% cohesion)"
---

# . +2 dirs · test_core_event_models_are_impo…

23 symbols | 12 files | 69% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.ActionAttemptedEvent`
- `external-call::dep:src.events.ApprovalGrantedEvent`
- `external-call::dep:src.events.BeliefCreatedEvent`
- `external-call::dep:src.events.ExecutiveDecisionEvent`
- `external-call::dep:src.events.OpportunityIdentifiedEvent`
- `external-call::dep:src.events.OpportunityScoredEvent`
- `external-call::dep:src.events.PlanAbandonedEvent`
- `external-call::dep:src.events.PlanProposedEvent`
- `external-call::dep:src.executive.Executive`
- `src\events\__init__.py`
- `tests\test_events.py`
- `tests\test_executive.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.ActionAttemptedEvent` | src.events.ActionAttemptedEvent |
| `external-call::dep:src.events.ApprovalGrantedEvent` | src.events.ApprovalGrantedEvent |
| `external-call::dep:src.events.BeliefCreatedEvent` | src.events.BeliefCreatedEvent |
| `external-call::dep:src.events.ExecutiveDecisionEvent` | src.events.ExecutiveDecisionEvent |
| `external-call::dep:src.events.OpportunityIdentifiedEvent` | src.events.OpportunityIdentifiedEvent |
| `external-call::dep:src.events.OpportunityScoredEvent` | src.events.OpportunityScoredEvent |
| `external-call::dep:src.events.PlanAbandonedEvent` | src.events.PlanAbandonedEvent |
| `external-call::dep:src.events.PlanProposedEvent` | src.events.PlanProposedEvent |
| `external-call::dep:src.executive.Executive` | src.executive.Executive |
| `src\events\__init__.py` | ApprovalGrantedEvent, PlanProposedEvent, ExecutiveDecisionEvent, PlanAbandonedEvent, ActionAttemptedEvent, ... |
| `tests\test_events.py` | EventModelTests, test_core_event_models_are_importable_and_instantiable |
| `tests\test_executive.py` | test_each_belief_event_produces_a_separate_opportunity_and_plan, test_belief_updated_also_triggers_pipeline, ExecutiveBeliefCreatedPipelineTests, test_executive_does_not_approve_or_execute |

## Entry Points

- `tests\test_events.py::EventModelTests.test_core_event_models_are_importable_and_instantiable`
- `tests\test_executive.py::ExecutiveBeliefCreatedPipelineTests.test_each_belief_event_produces_a_separate_opportunity_and_plan`
- `tests\test_executive.py::ExecutiveBeliefCreatedPipelineTests.test_belief_updated_also_triggers_pipeline`
- `tests\test_executive.py::ExecutiveBeliefCreatedPipelineTests.test_executive_does_not_approve_or_execute`

## Connected Communities

- **. +2 dirs · EventType** (3 cross-edges)
- **. +2 dirs · _on_observation_created** (2 cross-edges)
- **. +1 dirs · record_observation** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-41"
smart_context with task: "understand . +2 dirs · test_core_event_models_are_impo…", format: "gcx"
find_usages with id: "tests\test_events.py::EventModelTests.test_core_event_models_are_importable_and_instantiable", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
