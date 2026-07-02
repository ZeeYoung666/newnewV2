---
name: gortex-1-dirs-test-append-and-read-all
description: "Work in the . +1 dirs · test_append_and_read_all area — 5 symbols across 3 files (90% cohesion)"
---

# . +1 dirs · test_append_and_read_all

5 symbols | 3 files | 90% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.executive.DecisionRecord`
- `external-call::dep:src.executive.DecisionRecordStore`
- `tests\test_executive.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.executive.DecisionRecord` | src.executive.DecisionRecord |
| `external-call::dep:src.executive.DecisionRecordStore` | src.executive.DecisionRecordStore |
| `tests\test_executive.py` | test_get_raises_for_unknown_decision, test_append_and_read_all, DecisionRecordStoreTests |

## Entry Points

- `tests\test_executive.py::DecisionRecordStoreTests.test_append_and_read_all`

## Connected Communities

- **. +1 dirs · now** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-40"
smart_context with task: "understand . +1 dirs · test_append_and_read_all", format: "gcx"
find_usages with id: "tests\test_executive.py::DecisionRecordStoreTests.test_append_and_read_all", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
