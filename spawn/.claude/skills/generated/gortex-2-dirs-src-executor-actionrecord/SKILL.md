---
name: gortex-2-dirs-src-executor-actionrecord
description: "Work in the . +2 dirs · src.executor.ActionRecord area — 13 symbols across 4 files (83% cohesion)"
---

# . +2 dirs · src.executor.ActionRecord

13 symbols | 4 files | 83% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.executor.ActionLog`
- `external-call::dep:src.executor.ActionRecord`
- `src\executor\__init__.py`
- `tests\test_executor.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.executor.ActionLog` | src.executor.ActionLog |
| `external-call::dep:src.executor.ActionRecord` | src.executor.ActionRecord |
| `src\executor\__init__.py` | read_all, ActionLog, __init__, ActionRecord |
| `tests\test_executor.py` | test_append_and_read_all, test_action_record_is_immutable, ActionLogTests, ActionRecordModelTests, test_action_record_carries_required_fields, ... |

## Connected Communities

- **. +1 dirs · now** (4 cross-edges)

## How to Explore

```
get_communities with id: "community-92"
smart_context with task: "understand . +2 dirs · src.executor.ActionRecord", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
