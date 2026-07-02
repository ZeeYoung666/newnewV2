---
name: gortex-2-dirs-src-perception-sensorregistry
description: "Work in the . +2 dirs · src.perception.SensorRegistry area — 18 symbols across 3 files (97% cohesion)"
---

# . +2 dirs · src.perception.SensorRegistry

18 symbols | 3 files | 97% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.perception.SensorRegistry`
- `src\perception\__init__.py`
- `tests\test_perception.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.perception.SensorRegistry` | src.perception.SensorRegistry |
| `src\perception\__init__.py` | sensor_id, __init__, source_type, sensor_id, register_sensor, ... |
| `tests\test_perception.py` | SensorRegistryTests, test_is_active_returns_false_for_unknown_sensor, test_unregister_sensor_removes_it, test_get_metadata_raises_for_unknown_sensor, test_registering_duplicate_sensor_id_raises, ... |

## Entry Points

- `tests\test_perception.py::SensorRegistryTests.test_register_sensor_stores_metadata_and_marks_active`
- `tests\test_perception.py::SensorRegistryTests.test_unregister_sensor_removes_it`
- `tests\test_perception.py::SensorRegistryTests.test_registering_duplicate_sensor_id_raises`

## How to Explore

```
get_communities with id: "community-48"
smart_context with task: "understand . +2 dirs · src.perception.SensorRegistry", format: "gcx"
find_usages with id: "tests\test_perception.py::SensorRegistryTests.test_register_sensor_stores_metadata_and_marks_active", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
