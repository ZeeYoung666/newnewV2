# ADR-0003: Medium Learning Loop calibration signal is not consumed by the Executive

- Status: Open / deferred (not implemented)
- Date: 2026-07-05

## Context

`Architecture.pdf` §7 describes the medium loop as adjusting "the
Executive's priors on opportunity classes and its calibration (if EV
estimates run 3x optimistic, future estimates get discounted 3x)."

What's built: `MediumLearner` (`src/memory/__init__.py:229`) computes
`compute_mean_error()` and `compute_confidence()` from resolved predictions,
and `MemoryLedger` stores the result as a `Heuristic` (a description string
plus a confidence float) in `HeuristicStore`. This is fully event-driven,
deterministic, snapshot-restorable, and tested.

What's missing: `Executive` never imports or reads `HeuristicStore` —
confirmed by grep, zero references anywhere in `src/executive/__init__.py`.
The specific "3x optimism / 3x future discount" correction described in the
original design conversation was never implemented in any form; there is no
optimism-bias correction anywhere in the codebase. The wording in
`Architecture.pdf` describing this as a concrete mechanism is aspirational,
not a spec that was ever finalized — `Architecture.md` §7 has been reworded
to say so plainly.

## Decision

Defer. Recording the calibration signal (this ADR's prerequisite) is done.
Feeding it back into Executive's EV estimation is explicitly out of scope
until a concrete reward-shaping model is designed — not silently implied to
exist by roadmap item 17 ("medium learning loop") having shipped.

## Consequences

- Executive's EV estimates carry no calibration correction today. An
  opportunity class that is systematically overvalued will not self-correct
  through this pathway.
- Before wiring this: (1) design how Executive consumes heuristics —
  per the architecture's own communication rule, this should be a new event
  type carrying a calibration adjustment, not a direct `HeuristicStore`
  read; (2) define the actual discount function. The original "3x" was
  illustrative in the design chat, not a spec — pick a real one (e.g.
  derived from `MediumLearner.compute_mean_error()` against a rolling
  window) when this is picked up.
