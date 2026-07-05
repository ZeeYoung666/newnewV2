# ADR-0002: Slow Learning Loop consolidation cadence is count-based, not time-based

- Status: Accepted
- Date: 2026-07-05

## Context

`SlowLearner.CONSOLIDATION_INTERVAL = 3` (`src/memory/__init__.py:330`)
triggers a Slow Learning Loop consolidation pass every 3 accumulated
heuristics, via a modulo check in `should_consolidate()`. The Kernel gained
a real timer/scheduler (`Scheduler.schedule_at`, `src/kernel/__init__.py:243`,
roadmap item 5) after this loop's design was settled, so a time-based
cadence ("consolidate every N logical-time ticks") became possible but was
not adopted.

## Decision

Keep the count-based trigger. It is deterministic and replay-safe by
construction — the same heuristic history always produces the same
consolidation points, with no dependency on Kernel timer wiring or wall
clock. The constant `3` is arbitrary: small enough to exercise the loop
early in tests and with a small number of outcomes, not derived from any
calibration study of real heuristic-arrival rates.

## Consequences

- Consolidation frequency in wall-clock time depends entirely on how fast
  heuristics accumulate, which depends on how fast the Medium Learning Loop
  scores outcomes. Under sparse activity, consolidation could stall for a
  long time; under a burst, it could fire back-to-back.
- Revisit if heuristic volume in practice produces uneven consolidation
  gaps. If so, migrate to a `Scheduler.schedule_at()`-driven periodic
  consolidation — the same pattern belief decay would need if ADR-0005 is
  picked up — rather than changing the constant.
