---
name: gortex-2-dirs-on-observation-created
description: "Work in the . +2 dirs · _on_observation_created area — 24 symbols across 3 files (82% cohesion)"
---

# . +2 dirs · _on_observation_created

24 symbols | 3 files | 82% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.BeliefUpdatedEvent`
- `src\events\__init__.py`
- `src\world_model\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.BeliefUpdatedEvent` | src.events.BeliefUpdatedEvent |
| `src\events\__init__.py` | ObservationCreatedEvent, BeliefUpdatedEvent |
| `src\world_model\__init__.py` | _clamp_confidence, sensor_id, belief_id, _belief_id_for_sensor, now, ... |

## Entry Points

- `src\world_model\__init__.py::WorldModel._on_observation_created`
- `src\world_model\__init__.py::WorldModel.apply_decay`

## Connected Communities

- **. +2 dirs · test_core_event_models_are_impo…** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-39"
smart_context with task: "understand . +2 dirs · _on_observation_created", format: "gcx"
find_usages with id: "src\world_model\__init__.py::WorldModel._on_observation_created", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
