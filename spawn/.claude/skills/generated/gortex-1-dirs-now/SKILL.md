---
name: gortex-1-dirs-now
description: "Work in the . +1 dirs · now area — 47 symbols across 15 files (70% cohesion)"
---

# . +1 dirs · now

47 symbols | 15 files | 70% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `external-call::dep:src.executive.Goal`
- `external-call::dep:src.executive.GoalStore`
- `external-call::dep:src.executive.Opportunity`
- `external-call::dep:src.executive.OpportunityStore`
- `external-call::dep:src.executor.Action`
- `external-call::dep:src.governor.BudgetState`
- `external-call::dep:src.governor.BudgetStore`
- `external-call::dep:src.governor.Constitution`
- `external-call::dep:src.governor.ConstitutionStore`
- `external-call::dep:src.inference.InferenceResponse`
- `tests\test_executive.py`
- `tests\test_executor.py`
- `tests\test_governor.py`
- `tests\test_inference.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | now |
| `external-call::dep:src.executive.Goal` | src.executive.Goal |
| `external-call::dep:src.executive.GoalStore` | src.executive.GoalStore |
| `external-call::dep:src.executive.Opportunity` | src.executive.Opportunity |
| `external-call::dep:src.executive.OpportunityStore` | src.executive.OpportunityStore |
| `external-call::dep:src.executor.Action` | src.executor.Action |
| `external-call::dep:src.governor.BudgetState` | src.governor.BudgetState |
| `external-call::dep:src.governor.BudgetStore` | src.governor.BudgetStore |
| `external-call::dep:src.governor.Constitution` | src.governor.Constitution |
| `external-call::dep:src.governor.ConstitutionStore` | src.governor.ConstitutionStore |
| `external-call::dep:src.inference.InferenceResponse` | src.inference.InferenceResponse |
| `tests\test_executive.py` | test_append_and_get_round_trip, GoalStoreTests, test_goal_is_immutable, test_get_raises_for_unknown_goal, OpportunityStoreTests, ... |
| `tests\test_executor.py` | ActionModelTests, test_action_carries_required_fields, test_action_is_immutable |
| `tests\test_governor.py` | BudgetStateModelTests, test_budget_state_is_immutable, test_put_get_and_exists, test_append_get_and_current, test_constitution_is_immutable, ... |
| `tests\test_inference.py` | test_response_is_immutable, test_response_carries_required_fields, InferenceResponseModelTests |

## Entry Points

- `tests\test_governor.py::BudgetStoreTests.test_put_get_and_exists`

## Connected Communities

- **. +3 dirs · EventType** (2 cross-edges)

## How to Explore

```
get_communities with id: "community-106"
smart_context with task: "understand . +1 dirs · now", format: "gcx"
find_usages with id: "tests\test_governor.py::BudgetStoreTests.test_put_get_and_exists", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
