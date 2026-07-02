---
name: gortex-src-kernel-kernel
description: "Work in the src\kernel · Kernel area — 6 symbols across 1 files (36% cohesion)"
---

# src\kernel · Kernel

6 symbols | 1 files | 36% cohesion

## When to Use

Use this skill when working on files in:
- `src\kernel\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `src\kernel\__init__.py` | event, dispatch, process_next, run_until_idle, is_running, ... |

## How to Explore

```
get_communities with id: "community-45"
smart_context with task: "understand src\kernel · Kernel", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
