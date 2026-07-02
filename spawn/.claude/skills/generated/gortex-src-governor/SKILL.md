---
name: gortex-src-governor
description: "Work in the src\governor area — 12 symbols across 1 files (79% cohesion)"
---

# src\governor

12 symbols | 1 files | 79% cohesion

## When to Use

Use this skill when working on files in:
- `src\governor\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `src\governor\__init__.py` | budget_id, fund_budget, budget, BudgetStore, budget, ... |

## How to Explore

```
get_communities with id: "community-78"
smart_context with task: "understand src\governor", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
