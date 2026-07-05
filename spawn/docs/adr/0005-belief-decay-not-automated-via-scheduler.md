# ADR-0005: Belief decay remains manually invoked despite the Kernel now having a timer/scheduler

- Status: Open / deferred
- Date: 2026-07-05

## Context

`WorldModel.apply_decay(now)` (`src/world_model/__init__.py:184`) still
requires an external caller to invoke it with the current time — identical
to the finding at the original baseline audit. Roadmap item 5 (Kernel:
scheduler + timer table) shipped specifically to unblock "automatic belief
decay (currently manually invoked)," per its own stated rationale in the
baseline audit's roadmap, and `Scheduler.schedule_at()`
(`src/kernel/__init__.py:243`) is fully implemented and tested. No code
anywhere calls `schedule_at()` to register a recurring decay tick.

## Decision

Defer wiring decay to the scheduler. The primitive exists; the integration
doesn't, and building it without a concrete decay cadence in mind (see
ADR-0002 for the same class of open question in the Slow Learning Loop)
would be guessing at a policy value.

## Consequences

- Decay only happens where a test or caller explicitly drives it. In the
  running composition root (`main.py`), nothing currently ages beliefs over
  time — a long-running organism's confidence values will not decay on
  their own.
- When picked up: register a periodic `schedule_at()` callback from World
  Model's own constructor, matching how every other component self-registers
  its subscriptions, and publish `BeliefUpdated` exactly as the manual path
  does today — no new event type needed, just an automatic trigger for the
  existing one.
