---
name: gortex-1-dirs-decode-value
description: "Work in the . +1 dirs · _decode_value area — 14 symbols across 3 files (91% cohesion)"
---

# . +1 dirs · _decode_value

14 symbols | 3 files | 91% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `external-call::dep:src.events.EventType`
- `src\kernel\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | fromisoformat, uuid.UUID, typing, get_type_hints, get_args, ... |
| `external-call::dep:src.events.EventType` | src.events.EventType |
| `src\kernel\__init__.py` | value, _decode_value, record, _decode_event, target_type |

## How to Explore

```
get_communities with id: "community-84"
smart_context with task: "understand . +1 dirs · _decode_value", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
