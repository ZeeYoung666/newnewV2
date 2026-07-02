---
name: gortex-2-dirs-outcome
description: "Work in the . +2 dirs · Outcome area — 15 symbols across 4 files (87% cohesion)"
---

# . +2 dirs · Outcome

15 symbols | 4 files | 87% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.memory.Outcome`
- `external-call::dep:src.memory.OutcomeStore`
- `src\memory\__init__.py`
- `tests\test_memory.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.memory.Outcome` | src.memory.Outcome |
| `external-call::dep:src.memory.OutcomeStore` | src.memory.OutcomeStore |
| `src\memory\__init__.py` | Outcome, OutcomeStore, get, read_all, __init__, ... |
| `tests\test_memory.py` | test_append_and_read_all, test_outcome_carries_required_fields, test_outcome_is_immutable, test_store_has_no_mutation_methods_other_than_append, OutcomeModelTests, ... |

## Connected Communities

- **. +1 dirs · now** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-87"
smart_context with task: "understand . +2 dirs · Outcome", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
