---
name: gortex-2-dirs-identify-opportunity
description: "Work in the . +2 dirs · _identify_opportunity area — 39 symbols across 5 files (81% cohesion)"
---

# . +2 dirs · _identify_opportunity

39 symbols | 5 files | 81% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `external-call::dep:src.events.OpportunityIdentifiedEvent`
- `external-call::dep:src.events.OpportunityScoredEvent`
- `src\events\__init__.py`
- `src\executive\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | uuid4, uuid.uuid4 |
| `external-call::dep:src.events.OpportunityIdentifiedEvent` | src.events.OpportunityIdentifiedEvent |
| `external-call::dep:src.events.OpportunityScoredEvent` | src.events.OpportunityScoredEvent |
| `src\events\__init__.py` | OpportunityIdentifiedEvent, OpportunityScoredEvent |
| `src\executive\__init__.py` | __init__, __init__, event, opportunity_id, _identify_opportunity, ... |

## Connected Communities

- **. +3 dirs · EventType** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-74"
smart_context with task: "understand . +2 dirs · _identify_opportunity", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
