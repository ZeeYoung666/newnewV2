---
name: gortex-2-dirs-eventtype
description: "Work in the . +2 dirs · EventType area — 27 symbols across 6 files (79% cohesion)"
---

# . +2 dirs · EventType

27 symbols | 6 files | 79% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.Event`
- `external-call::dep:src.kernel.EventLog`
- `external-call::dep:src.kernel.Kernel`
- `src\events\__init__.py`
- `tests\test_executive.py`
- `tests\test_kernel.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.Event` | src.events.Event |
| `external-call::dep:src.kernel.EventLog` | src.kernel.EventLog |
| `external-call::dep:src.kernel.Kernel` | src.kernel.Kernel |
| `src\events\__init__.py` | Event, EventType |
| `tests\test_executive.py` | test_belief_created_generates_opportunity_scores_it_and_proposes_plan |
| `tests\test_kernel.py` | test_unregistering_subscribers_works, subscriber, test_stop_emits_kernel_stopping_and_kernel_stopped, test_event_log_read_from_returns_suffix_without_mutating_entries, test_event_order_is_preserved, ... |

## Entry Points

- `tests\test_executive.py::ExecutiveBeliefCreatedPipelineTests.test_belief_created_generates_opportunity_scores_it_and_proposes_plan`
- `tests\test_kernel.py::KernelTests.test_stop_emits_kernel_stopping_and_kernel_stopped`
- `tests\test_kernel.py::KernelTests.test_event_log_read_from_returns_suffix_without_mutating_entries`
- `tests\test_kernel.py::KernelTests.test_repeated_start_and_stop_do_not_emit_duplicate_lifecycle_events_on_no_state_change`
- `tests\test_kernel.py::KernelTests.test_start_emits_kernel_starting_and_kernel_started`

## Connected Communities

- **. +2 dirs · test_core_event_models_are_impo…** (2 cross-edges)

## How to Explore

```
get_communities with id: "community-44"
smart_context with task: "understand . +2 dirs · EventType", format: "gcx"
find_usages with id: "tests\test_executive.py::ExecutiveBeliefCreatedPipelineTests.test_belief_created_generates_opportunity_scores_it_and_proposes_plan", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
