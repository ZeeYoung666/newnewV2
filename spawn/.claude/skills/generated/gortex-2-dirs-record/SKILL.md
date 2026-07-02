---
name: gortex-2-dirs-record
description: "Work in the . +2 dirs · _record area — 22 symbols across 4 files (74% cohesion)"
---

# . +2 dirs · _record

22 symbols | 4 files | 74% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.LedgerEntryPostedEvent`
- `external-call::dep:src.events.OutcomeRecordedEvent`
- `src\events\__init__.py`
- `src\memory\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.LedgerEntryPostedEvent` | src.events.LedgerEntryPostedEvent |
| `external-call::dep:src.events.OutcomeRecordedEvent` | src.events.OutcomeRecordedEvent |
| `src\events\__init__.py` | ActionFailedEvent, LedgerEntryPostedEvent, OutcomeRecordedEvent, ActionSucceededEvent |
| `src\memory\__init__.py` | plan_id, success, MemoryLedger, _on_action_failed, result, ... |

## Connected Communities

- **. +2 dirs · _identify_opportunity** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-86"
smart_context with task: "understand . +2 dirs · _record", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
