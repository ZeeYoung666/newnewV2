---
name: gortex-2-dirs-src-perception-observation
description: "Work in the . +2 dirs · src.perception.Observation area — 14 symbols across 4 files (94% cohesion)"
---

# . +2 dirs · src.perception.Observation

14 symbols | 4 files | 94% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.perception.Observation`
- `external-call::dep:src.perception.ObservationLog`
- `src\perception\__init__.py`
- `tests\test_perception.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.perception.Observation` | src.perception.Observation |
| `external-call::dep:src.perception.ObservationLog` | src.perception.ObservationLog |
| `src\perception\__init__.py` | read_from, sequence_number, read_all, ObservationLog, __init__, ... |
| `tests\test_perception.py` | ObservationLogTests, test_observation_carries_required_fields, test_observation_is_immutable, test_read_from_returns_suffix_without_mutating_entries, ObservationModelTests, ... |

## Entry Points

- `tests\test_perception.py::ObservationLogTests.test_read_from_returns_suffix_without_mutating_entries`
- `tests\test_perception.py::ObservationLogTests.test_append_assigns_increasing_sequence_and_read_all_returns_in_order`
- `tests\test_perception.py::ObservationModelTests.test_observation_carries_required_fields`

## How to Explore

```
get_communities with id: "community-46"
smart_context with task: "understand . +2 dirs · src.perception.Observation", format: "gcx"
find_usages with id: "tests\test_perception.py::ObservationLogTests.test_read_from_returns_suffix_without_mutating_entries", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
