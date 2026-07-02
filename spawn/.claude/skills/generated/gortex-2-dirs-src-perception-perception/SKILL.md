---
name: gortex-2-dirs-src-perception-perception
description: "Work in the . +2 dirs · src.perception.Perception area — 14 symbols across 5 files (66% cohesion)"
---

# . +2 dirs · src.perception.Perception

14 symbols | 5 files | 66% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.perception.Perception`
- `external-call::dep:src.world_model.WorldModel`
- `src\perception\__init__.py`
- `tests\test_perception.py`
- `tests\test_world_model.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.perception.Perception` | src.perception.Perception |
| `external-call::dep:src.world_model.WorldModel` | src.world_model.WorldModel |
| `src\perception\__init__.py` | __init__, kernel, Perception |
| `tests\test_perception.py` | test_record_observation_rejects_inactive_sensor, PerceptionTests, test_record_observation_rejects_unregistered_sensor, test_record_observation_rejects_confidence_out_of_range, test_record_observation_creates_appends_and_publishes_event |
| `tests\test_world_model.py` | WorldModelObservationTests, test_repeated_observation_for_same_sensor_updates_confidence_and_emits_belief_updated, test_first_observation_creates_belief_and_emits_belief_created, test_observations_from_different_sensors_create_separate_beliefs |

## Entry Points

- `tests\test_perception.py::PerceptionTests.test_record_observation_creates_appends_and_publishes_event`
- `tests\test_world_model.py::WorldModelObservationTests.test_repeated_observation_for_same_sensor_updates_confidence_and_emits_belief_updated`
- `tests\test_world_model.py::WorldModelObservationTests.test_first_observation_creates_belief_and_emits_belief_created`
- `tests\test_world_model.py::WorldModelObservationTests.test_observations_from_different_sensors_create_separate_beliefs`
- `tests\test_perception.py::PerceptionTests.test_record_observation_rejects_confidence_out_of_range`

## Connected Communities

- **. +2 dirs · EventType** (7 cross-edges)

## How to Explore

```
get_communities with id: "community-47"
smart_context with task: "understand . +2 dirs · src.perception.Perception", format: "gcx"
find_usages with id: "tests\test_perception.py::PerceptionTests.test_record_observation_creates_appends_and_publishes_event", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
