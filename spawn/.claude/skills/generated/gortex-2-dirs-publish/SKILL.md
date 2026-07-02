---
name: gortex-2-dirs-publish
description: "Work in the . +2 dirs · publish area — 14 symbols across 6 files (78% cohesion)"
---

# . +2 dirs · publish

14 symbols | 6 files | 78% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.KernelStartedEvent`
- `external-call::dep:src.events.KernelStartingEvent`
- `external-call::dep:src.events.KernelStoppedEvent`
- `external-call::dep:src.events.KernelStoppingEvent`
- `src\events\__init__.py`
- `src\kernel\__init__.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.KernelStartedEvent` | src.events.KernelStartedEvent |
| `external-call::dep:src.events.KernelStartingEvent` | src.events.KernelStartingEvent |
| `external-call::dep:src.events.KernelStoppedEvent` | src.events.KernelStoppedEvent |
| `external-call::dep:src.events.KernelStoppingEvent` | src.events.KernelStoppingEvent |
| `src\events\__init__.py` | KernelStartedEvent, KernelStoppedEvent, KernelStartingEvent, KernelStoppingEvent |
| `src\kernel\__init__.py` | event, append, start, publish, event, ... |

## Entry Points

- `src\kernel\__init__.py::Kernel.start`
- `src\kernel\__init__.py::Kernel.stop`

## Connected Communities

- **src\kernel · Kernel** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-35"
smart_context with task: "understand . +2 dirs · publish", format: "gcx"
find_usages with id: "src\kernel\__init__.py::Kernel.start", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
