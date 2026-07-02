---
name: gortex-3-dirs-eventtype
description: "Work in the . +3 dirs · EventType area — 95 symbols across 16 files (84% cohesion)"
---

# . +3 dirs · EventType

95 symbols | 16 files | 84% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.events.ApprovalGrantedEvent`
- `external-call::dep:src.events.Event`
- `external-call::dep:src.events.PlanProposedEvent`
- `external-call::dep:src.executor.Executor`
- `external-call::dep:src.governor.Governor`
- `external-call::dep:src.kernel.EventLog`
- `external-call::dep:src.kernel.Kernel`
- `external-call::dep:src.memory.MemoryLedger`
- `src\events\__init__.py`
- `src\kernel\__init__.py`
- `tests\test_executive.py`
- `tests\test_executor.py`
- `tests\test_governor.py`
- `tests\test_kernel.py`
- `tests\test_memory.py`
- `tests\test_world_model.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.events.ApprovalGrantedEvent` | src.events.ApprovalGrantedEvent |
| `external-call::dep:src.events.Event` | src.events.Event |
| `external-call::dep:src.events.PlanProposedEvent` | src.events.PlanProposedEvent |
| `external-call::dep:src.executor.Executor` | src.executor.Executor |
| `external-call::dep:src.governor.Governor` | src.governor.Governor |
| `external-call::dep:src.kernel.EventLog` | src.kernel.EventLog |
| `external-call::dep:src.kernel.Kernel` | src.kernel.Kernel |
| `external-call::dep:src.memory.MemoryLedger` | src.memory.MemoryLedger |
| `src\events\__init__.py` | Event, EventType |
| `src\kernel\__init__.py` | read_all, Kernel, read_from, EventLog, sequence_number, ... |
| `tests\test_executive.py` | test_belief_created_generates_opportunity_scores_it_and_proposes_plan |
| `tests\test_executor.py` | ordered_actions, test_unregistered_tool_is_recorded_and_emitted_as_failure, test_executor_never_executes_unapproved_plans, kernel, publish_approval_granted, ... |
| `tests\test_governor.py` | test_governor_does_not_create_or_execute_plans, GovernorApprovalDeniedTests, GovernorAuthorityBoundaryTests, publish_plan_proposed, kernel, ... |
| `tests\test_kernel.py` | event, test_publish_after_start_queues_on_scheduler_until_drained, test_sequence_numbers_continue_after_restart, subscriber, test_read_all_after_restart_returns_copy_not_shared_reference, ... |
| `tests\test_memory.py` | MemoryLedgerScopeBoundaryTests, MemoryLedgerAppendOnlyTests, MemoryLedgerFailureTests, test_multiple_outcomes_accumulate_without_overwriting, test_action_failed_creates_outcome_episodic_entry_and_ledger_entry, ... |
| `tests\test_world_model.py` | test_repeated_observation_for_same_sensor_updates_confidence_and_emits_belief_updated |

## Entry Points

- `tests\test_executive.py::ExecutiveBeliefCreatedPipelineTests.test_belief_created_generates_opportunity_scores_it_and_proposes_plan`
- `tests\test_memory.py::MemoryLedgerSuccessTests.test_action_succeeded_creates_outcome_episodic_entry_and_ledger_entry`
- `tests\test_governor.py::GovernorApprovalGrantedTests.test_valid_plan_within_budget_is_granted_and_reserves_budget`
- `tests\test_executor.py::ExecutorEventEmissionTests.test_successful_action_emits_approved_attempted_and_succeeded`
- `tests\test_memory.py::MemoryLedgerFailureTests.test_action_failed_creates_outcome_episodic_entry_and_ledger_entry`

## Connected Communities

- **. +1 dirs · now** (5 cross-edges)
- **. +3 dirs · _execute_action** (4 cross-edges)
- **. +2 dirs · test_each_belief_event_produces…** (3 cross-edges)
- **. +2 dirs · src.perception.Perception** (1 cross-edges)
- **. +3 dirs · _on_observation_created** (1 cross-edges)
- **. +2 dirs · src.perception.Observation** (1 cross-edges)
- **. +1 dirs · append** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-98"
smart_context with task: "understand . +3 dirs · EventType", format: "gcx"
find_usages with id: "tests\test_executive.py::ExecutiveBeliefCreatedPipelineTests.test_belief_created_generates_opportunity_scores_it_and_proposes_plan", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
