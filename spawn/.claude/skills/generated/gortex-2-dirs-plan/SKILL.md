---
name: gortex-2-dirs-plan
description: "Work in the . +2 dirs · Plan area — 16 symbols across 4 files (90% cohesion)"
---

# . +2 dirs · Plan

16 symbols | 4 files | 90% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.executive.Plan`
- `external-call::dep:src.executive.PlanStore`
- `src\executive\__init__.py`
- `tests\test_executive.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.executive.Plan` | src.executive.Plan |
| `external-call::dep:src.executive.PlanStore` | src.executive.PlanStore |
| `src\executive\__init__.py` | append, plan_id, read_all, Plan, PlanStore, ... |
| `tests\test_executive.py` | PlanModelTests, test_get_raises_for_unknown_plan, PlanStoreTests, test_plan_is_immutable, test_plan_carries_required_fields, ... |

## Connected Communities

- **. +1 dirs · now** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-75"
smart_context with task: "understand . +2 dirs · Plan", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
