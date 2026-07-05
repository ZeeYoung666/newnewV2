# ADR-0004: Goal tree exists as scaffolding; attention allocation is caller-supplied, not goal-driven

- Status: Open / deferred
- Date: 2026-07-05

## Context

`Executive.goal_store` (`GoalStore`, `src/executive/__init__.py:184` and
`:350`) is instantiated in the constructor but never read or written
anywhere else in the file — the same state the original 6:31pm baseline
audit flagged. Since then, `Executive.deliberate(available_attention,
available_capital)` (`src/executive/__init__.py:352`) shipped real
budget-aware allocation across competing plans (roadmap item 8): it spends
`remaining_attention` / `remaining_capital` across ranked candidates
correctly. But the attention/capital figures themselves are passed in by
the caller — in `main.py`'s bootstrap config, fixed constants — rather than
derived from any goal tree's priorities.

## Decision

Defer building the goal tree into an actual prioritization input. The
allocation *mechanism* is real and tested; only the upstream "how much is
available, and why" question is unaddressed. Ship allocation-against-a-given-
budget now; goal-tree-driven budget derivation is separate, later work.

## Consequences

- Today, attention/capital budgets are static configuration, not policy —
  there is no code path where competing long-term goals influence how much
  gets allocated to any given deliberation cycle.
- `GoalStore` and `Goal` stay dead code until this is picked up. Flag this
  in review rather than assuming `goal_store` does something because it
  exists on `Executive`.
