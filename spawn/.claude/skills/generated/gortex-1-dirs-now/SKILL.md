---
name: gortex-1-dirs-now
description: "Work in the . +1 dirs · now area — 22 symbols across 6 files (72% cohesion)"
---

# . +1 dirs · now

22 symbols | 6 files | 72% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `external-call::dep:src.executive.Goal`
- `external-call::dep:src.executive.GoalStore`
- `external-call::dep:src.world_model.Belief`
- `tests\test_executive.py`
- `tests\test_world_model.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | now, timedelta, datetime.datetime, datetime.timedelta |
| `external-call::dep:src.executive.Goal` | src.executive.Goal |
| `external-call::dep:src.executive.GoalStore` | src.executive.GoalStore |
| `external-call::dep:src.world_model.Belief` | src.world_model.Belief |
| `tests\test_executive.py` | test_goal_carries_required_fields, GoalModelTests, test_append_and_get_round_trip, GoalStoreTests, test_goal_is_immutable, ... |
| `tests\test_world_model.py` | test_belief_is_immutable, test_apply_decay_skips_beliefs_with_zero_decay_rate, test_apply_decay_does_not_go_below_zero, test_put_and_get_round_trip, BeliefModelTests, ... |

## Entry Points

- `tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_reduces_confidence_and_emits_belief_updated`
- `tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_skips_beliefs_with_zero_decay_rate`
- `tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_skips_when_no_time_has_elapsed`
- `tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_does_not_go_below_zero`
- `tests\test_world_model.py::BeliefModelTests.test_belief_carries_required_fields`

## Connected Communities

- **. +2 dirs · EventType** (4 cross-edges)
- **. +2 dirs · src.perception.Perception** (4 cross-edges)
- **. +1 dirs · src.world_model.BeliefStore** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-49"
smart_context with task: "understand . +1 dirs · now", format: "gcx"
find_usages with id: "tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_reduces_confidence_and_emits_belief_updated", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
