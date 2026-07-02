---
name: gortex-src-kernel-eventlog
description: "Work in the src\kernel · EventLog area — 6 symbols across 1 files (68% cohesion)"
---

# src\kernel · EventLog

6 symbols | 1 files | 68% cohesion

## When to Use

Use this skill when working on files in:
- `src\kernel\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `src\kernel\__init__.py` | read_all, __init__, EventLog, sequence_number, read_from, ... |

## How to Explore

```
get_communities with id: "community-33"
smart_context with task: "understand src\kernel · EventLog", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
