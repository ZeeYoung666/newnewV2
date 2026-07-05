# ADR-0001: Replay produces different internal record IDs than the original run

- Status: Accepted (documented limitation, not a defect)
- Date: 2026-07-05

## Context

First identified while building Task #17 (Replay-on-Start) and reconfirmed
on every audit pass since. `Executor`, `Executive`, `Governor`, and `Memory
& Ledger` each mint a fresh `uuid4()` inside their event handlers on every
run, rather than deriving the ID deterministically from the triggering
event. Concretely: `action_id`, `decision_id`, `approval_id`, and similar
fields differ between an original run and a replay of the same event log.

Reconstructed state is identical to uninterrupted execution for everything
the architecture actually asks to be identical: belief confidence,
plan/approval counts, budget deltas, outcome success, ledger entries. It is
not identical for these internal surrogate keys.

## Decision

Accept as-is. These IDs were never part of the durable-identity axiom
(Architecture §1: identity is belief/goal/ledger/memory/decision-record
*state*, not surrogate keys). Do not build deterministic ID derivation now.

## Consequences

- No test or downstream feature may assume byte-for-byte ID reproduction
  across replay.
- If a future feature needs it — e.g. an idempotent external side-effect
  keyed by `action_id` — derive the ID deterministically from
  `(triggering_event_id, handler_name)` at that time, rather than reaching
  for `uuid4()`. This ADR is the record of *why* that isn't done today: no
  current consumer needs it, and building it speculatively would be
  premature.
