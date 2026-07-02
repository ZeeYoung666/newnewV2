---
name: gortex-1-dirs-src-executive-opportunity
description: "Work in the . +1 dirs · src.executive.Opportunity area — 8 symbols across 3 files (84% cohesion)"
---

# . +1 dirs · src.executive.Opportunity

8 symbols | 3 files | 84% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.executive.Opportunity`
- `external-call::dep:src.executive.OpportunityStore`
- `tests\test_executive.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.executive.Opportunity` | src.executive.Opportunity |
| `external-call::dep:src.executive.OpportunityStore` | src.executive.OpportunityStore |
| `tests\test_executive.py` | OpportunityModelTests, test_append_and_get_round_trip, test_opportunity_is_immutable, OpportunityStoreTests, test_get_raises_for_unknown_opportunity, ... |

## Entry Points

- `tests\test_executive.py::OpportunityStoreTests.test_append_and_get_round_trip`
- `tests\test_executive.py::OpportunityModelTests.test_opportunity_carries_required_fields`

## Connected Communities

- **. +1 dirs · now** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-42"
smart_context with task: "understand . +1 dirs · src.executive.Opportunity", format: "gcx"
find_usages with id: "tests\test_executive.py::OpportunityStoreTests.test_append_and_get_round_trip", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
