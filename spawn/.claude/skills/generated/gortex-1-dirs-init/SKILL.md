---
name: gortex-1-dirs-init
description: "Work in the . +1 dirs · __init__ area — 5 symbols across 2 files (77% cohesion)"
---

# . +1 dirs · __init__

5 symbols | 2 files | 77% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `src\kernel\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | deque, defaultdict, collections.deque, collections.defaultdict |
| `src\kernel\__init__.py` | __init__ |

## How to Explore

```
get_communities with id: "community-34"
smart_context with task: "understand . +1 dirs · __init__", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
