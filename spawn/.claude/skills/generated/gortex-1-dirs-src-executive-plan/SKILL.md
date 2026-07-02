---
name: gortex-1-dirs-src-executive-plan
description: "Work in the . +1 dirs · src.executive.Plan area — 8 symbols across 3 files (84% cohesion)"
---

# . +1 dirs · src.executive.Plan

8 symbols | 3 files | 84% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.executive.Plan`
- `external-call::dep:src.executive.PlanStore`
- `tests\test_executive.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.executive.Plan` | src.executive.Plan |
| `external-call::dep:src.executive.PlanStore` | src.executive.PlanStore |
| `tests\test_executive.py` | PlanStoreTests, test_plan_is_immutable, test_plan_carries_required_fields, test_get_raises_for_unknown_plan, PlanModelTests, ... |

## Entry Points

- `tests\test_executive.py::PlanModelTests.test_plan_carries_required_fields`
- `tests\test_executive.py::PlanStoreTests.test_append_and_get_round_trip`

## Connected Communities

- **. +1 dirs · now** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-43"
smart_context with task: "understand . +1 dirs · src.executive.Plan", format: "gcx"
find_usages with id: "tests\test_executive.py::PlanModelTests.test_plan_carries_required_fields", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
