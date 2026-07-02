---
name: gortex-3-dirs-on-plan-proposed
description: "Work in the . +3 dirs · _on_plan_proposed area — 46 symbols across 9 files (69% cohesion)"
---

# . +3 dirs · _on_plan_proposed

46 symbols | 9 files | 69% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.ApprovalDeniedEvent`
- `external-call::dep:src.events.ApprovalRequiredEvent`
- `external-call::dep:src.events.BudgetCheckedEvent`
- `external-call::dep:src.events.ExecutiveDecisionEvent`
- `external-call::dep:src.events.PlanAbandonedEvent`
- `external-call::dep:src.events.PolicyEvaluatedEvent`
- `src\events\__init__.py`
- `src\governor\__init__.py`
- `tests\test_events.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.ApprovalDeniedEvent` | src.events.ApprovalDeniedEvent |
| `external-call::dep:src.events.ApprovalRequiredEvent` | src.events.ApprovalRequiredEvent |
| `external-call::dep:src.events.BudgetCheckedEvent` | src.events.BudgetCheckedEvent |
| `external-call::dep:src.events.ExecutiveDecisionEvent` | src.events.ExecutiveDecisionEvent |
| `external-call::dep:src.events.PlanAbandonedEvent` | src.events.PlanAbandonedEvent |
| `external-call::dep:src.events.PolicyEvaluatedEvent` | src.events.PolicyEvaluatedEvent |
| `src\events\__init__.py` | BudgetCheckedEvent, ApprovalDeniedEvent, PolicyEvaluatedEvent, ApprovalRequiredEvent, PlanAbandonedEvent, ... |
| `src\governor\__init__.py` | event, __init__, constitution, plan_id, plan_id, ... |
| `tests\test_events.py` | EventModelTests, test_core_event_models_are_importable_and_instantiable |

## Entry Points

- `tests\test_events.py::EventModelTests.test_core_event_models_are_importable_and_instantiable`

## Connected Communities

- **. +3 dirs · _execute_action** (4 cross-edges)
- **. +2 dirs · _identify_opportunity** (4 cross-edges)
- **. +3 dirs · EventType** (3 cross-edges)
- **. +2 dirs · infer** (2 cross-edges)
- **. +2 dirs · _record** (2 cross-edges)
- **. +2 dirs · test_each_belief_event_produces…** (1 cross-edges)
- **. +3 dirs · _on_observation_created** (1 cross-edges)
- **src\governor** (1 cross-edges)
- **. +2 dirs · src.perception.Observation** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-77"
smart_context with task: "understand . +3 dirs · _on_plan_proposed", format: "gcx"
find_usages with id: "tests\test_events.py::EventModelTests.test_core_event_models_are_importable_and_instantiable", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
