---
name: gortex-3-dirs-execute-action
description: "Work in the . +3 dirs · _execute_action area — 40 symbols across 8 files (76% cohesion)"
---

# . +3 dirs · _execute_action

40 symbols | 8 files | 76% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.ActionApprovedEvent`
- `external-call::dep:src.events.ActionAttemptedEvent`
- `external-call::dep:src.events.ActionFailedEvent`
- `external-call::dep:src.events.ActionSucceededEvent`
- `src\events\__init__.py`
- `src\executor\__init__.py`
- `tests\test_executor.py`
- `tests\test_memory.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.ActionApprovedEvent` | src.events.ActionApprovedEvent |
| `external-call::dep:src.events.ActionAttemptedEvent` | src.events.ActionAttemptedEvent |
| `external-call::dep:src.events.ActionFailedEvent` | src.events.ActionFailedEvent |
| `external-call::dep:src.events.ActionSucceededEvent` | src.events.ActionSucceededEvent |
| `src\events\__init__.py` | ActionApprovedEvent, ActionAttemptedEvent, ApprovalGrantedEvent |
| `src\executor\__init__.py` | kernel, plan_id, result, record, action_type, ... |
| `tests\test_executor.py` | failing_tool, action |
| `tests\test_memory.py` | kernel, kernel, action_id, plan_id, publish_action_succeeded, ... |

## Connected Communities

- **. +2 dirs · _identify_opportunity** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-76"
smart_context with task: "understand . +3 dirs · _execute_action", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
