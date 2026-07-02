---
name: gortex-2-dirs-append-external-call-dep-src-memory-external-call-dep-src-memory-14-1
description: "Work in the . +2 dirs · append · external-call::dep:src.memory · external-call::dep:src.memory (14) #1 area — 14 symbols across 4 files (90% cohesion)"
---

# . +2 dirs · append · external-call::dep:src.memory · external-call::dep:src.memory (14) #1

14 symbols | 4 files | 90% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.memory.Heuristic`
- `external-call::dep:src.memory.HeuristicStore`
- `src\memory\__init__.py`
- `tests\test_memory.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.memory.Heuristic` | src.memory.Heuristic |
| `external-call::dep:src.memory.HeuristicStore` | src.memory.HeuristicStore |
| `src\memory\__init__.py` | HeuristicStore, append, __init__, heuristic, read_all, ... |
| `tests\test_memory.py` | test_store_has_no_mutation_methods_other_than_append, HeuristicStoreTests, test_heuristic_carries_required_fields, HeuristicModelTests, test_append_and_read_all, ... |

## Connected Communities

- **. +1 dirs · now** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-100"
smart_context with task: "understand . +2 dirs · append · external-call::dep:src.memory · external-call::dep:src.memory (14) #1", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
