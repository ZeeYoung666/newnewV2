---
name: gortex-2-dirs-src-kernel-scheduler
description: "Work in the . +2 dirs · src.kernel.Scheduler area — 32 symbols across 4 files (94% cohesion)"
---

# . +2 dirs · src.kernel.Scheduler

32 symbols | 4 files | 94% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `external-call::dep:src.kernel.Scheduler`
- `src\kernel\__init__.py`
- `tests\test_scheduler.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | defaultdict, collections.defaultdict |
| `external-call::dep:src.kernel.Scheduler` | src.kernel.Scheduler |
| `src\kernel\__init__.py` | cancel, task_id, Scheduler, process_next, __init__, ... |
| `tests\test_scheduler.py` | SchedulerPendingCountTests, SchedulerCancellationTests, first, test_fifo_execution_order, test_run_until_idle_drains_all_pending_work, ... |

## Entry Points

- `tests\test_scheduler.py::SchedulerPendingCountTests.test_pending_count_tracks_queue_state`
- `tests\test_scheduler.py::SchedulerNestedSchedulingTests.test_scheduling_during_execution_does_not_run_synchronously`
- `tests\test_scheduler.py::SchedulerCancellationTests.test_cancellation_prevents_execution`

## How to Explore

```
get_communities with id: "community-105"
smart_context with task: "understand . +2 dirs · src.kernel.Scheduler", format: "gcx"
find_usages with id: "tests\test_scheduler.py::SchedulerPendingCountTests.test_pending_count_tracks_queue_state", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
