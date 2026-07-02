---
name: gortex-3-dirs-on-observation-created
description: "Work in the . +3 dirs · _on_observation_created area — 46 symbols across 8 files (80% cohesion)"
---

# . +3 dirs · _on_observation_created

46 symbols | 8 files | 80% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `external-call::dep:src.events.BeliefUpdatedEvent`
- `external-call::dep:src.world_model.Belief`
- `external-call::dep:src.world_model.BeliefStore`
- `external-call::dep:src.world_model.WorldModel`
- `src\events\__init__.py`
- `src\world_model\__init__.py`
- `tests\test_world_model.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | timedelta, datetime.timedelta, replace |
| `external-call::dep:src.events.BeliefUpdatedEvent` | src.events.BeliefUpdatedEvent |
| `external-call::dep:src.world_model.Belief` | src.world_model.Belief |
| `external-call::dep:src.world_model.BeliefStore` | src.world_model.BeliefStore |
| `external-call::dep:src.world_model.WorldModel` | src.world_model.WorldModel |
| `src\events\__init__.py` | BeliefUpdatedEvent, ObservationCreatedEvent |
| `src\world_model\__init__.py` | WorldModel, belief_id, exists, read_all, _clamp_confidence, ... |
| `tests\test_world_model.py` | test_apply_decay_skips_when_no_time_has_elapsed, BeliefModelTests, test_belief_carries_required_fields, test_put_replaces_existing_belief_and_read_all_reflects_current_state, BeliefStoreTests, ... |

## Entry Points

- `tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_reduces_confidence_and_emits_belief_updated`
- `tests\test_world_model.py::WorldModelObservationTests.test_first_observation_creates_belief_and_emits_belief_created`
- `tests\test_world_model.py::WorldModelObservationTests.test_observations_from_different_sensors_create_separate_beliefs`
- `tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_skips_beliefs_with_zero_decay_rate`
- `tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_skips_when_no_time_has_elapsed`

## Connected Communities

- **. +1 dirs · now** (8 cross-edges)
- **. +3 dirs · EventType** (6 cross-edges)
- **. +2 dirs · src.perception.Perception** (2 cross-edges)
- **. +2 dirs · test_each_belief_event_produces…** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-88"
smart_context with task: "understand . +3 dirs · _on_observation_created", format: "gcx"
find_usages with id: "tests\test_world_model.py::WorldModelDecayTests.test_apply_decay_reduces_confidence_and_emits_belief_updated", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
