---
name: gortex-1-dirs-record-observation
description: "Work in the . +1 dirs · record_observation area — 10 symbols across 2 files (77% cohesion)"
---

# . +1 dirs · record_observation

10 symbols | 2 files | 77% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.ObservationCreatedEvent`
- `src\perception\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.ObservationCreatedEvent` | src.events.ObservationCreatedEvent |
| `src\perception\__init__.py` | is_active, observation, sensor_id, raw_source_type, confidence, ... |

## Entry Points

- `src\perception\__init__.py::Perception.record_observation`

## How to Explore

```
get_communities with id: "community-38"
smart_context with task: "understand . +1 dirs · record_observation", format: "gcx"
find_usages with id: "src\perception\__init__.py::Perception.record_observation", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
