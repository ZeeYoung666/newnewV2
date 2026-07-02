# Correlation ID Propagation — Design (Task #18)

## Goal

Every event descending from one observation carries the same `correlation_id`
through Observation → Belief → Opportunity → Plan → Approval → Execution →
Outcome → Memory. Two independent observations get different `correlation_id`s.
The Kernel is the sole place that assigns/propagates it; components never
generate or overwrite one.

## Current state (verified against source)

- `Event` (`src/events/__init__.py`) already declares
  `correlation_id: Optional[UUID] = None`. No component anywhere constructs an
  event with `correlation_id=...` (confirmed by full-repo text search) — the
  field is always left at its default `None` by callers.
- `Kernel.publish()` (`src/kernel/__init__.py`) is the **only** call site that
  appends to `EventLog` (`event_log.append`); every component
  (Perception, WorldModel, Executive, Governor, Executor, MemoryLedger,
  InferencePort) funnels its events through `self._kernel.publish(...)`. This
  makes `Kernel.publish` the single choke point for the whole rule.
- Dispatch is synchronous and FIFO via `Scheduler`, not call-stack recursion:
  a subscriber invoked during `dispatch()` may call `kernel.publish()` again,
  but that just appends a new task to `Scheduler`'s queue; the *same*
  `run_until_idle()` loop (started by the original top-level `publish()` call)
  drains it before that outer `publish()` returns. So a whole
  observation-to-outcome cascade happens inside one `run_until_idle()`
  invocation, never re-entrantly across two separate top-level `publish()`
  calls.
- `EventLog._encode_event` / `_decode_event` already serialize/deserialize
  every dataclass field generically, including `correlation_id: Optional[UUID]`
  (the `Union`/`UUID` branches in `_decode_value` already handle it). No change
  needed there.
- `Kernel.replay()` calls `self.dispatch(event)` directly for each historical
  log entry — it does **not** go through `publish()`. So replayed events keep
  whatever `correlation_id` was persisted, automatically, with zero new logic.
  (`publish()` is guarded by `if self._replaying: return`, so any events a
  handler re-emits during replay are already no-ops today.)

## Design

Add one piece of state to `Kernel`: `self._active_correlation_id: Optional[UUID] = None`.

In `Kernel.publish(self, event: Event)`, before the existing
`if self._replaying: return` logic continues:

```python
def publish(self, event: Event) -> None:
    if self._replaying:
        return
    is_root = self._active_correlation_id is None
    if event.correlation_id is None:
        event.correlation_id = self._active_correlation_id or uuid4()
    if is_root:
        self._active_correlation_id = event.correlation_id
    try:
        self.event_log.append(event)
        ...  # existing scheduling logic
        if not self._dispatching and (...):
            self.run_until_idle()
    finally:
        if is_root:
            self._active_correlation_id = None
```

Rules encoded:
- **Root publish** (no active correlation in flight): assign a fresh
  `uuid4()` if the event doesn't already have one, mark it active for the
  duration of this call's `run_until_idle()` drain, clear it afterward.
- **Nested publish** (called while a root's cascade is still draining,
  i.e. `_active_correlation_id` is set — includes both genuinely nested
  calls and same-loop cascade calls scheduled via `Scheduler`): inherit the
  active id.
- **Already-stamped event** (defensive only — never triggered by current
  components, but keeps replayed/re-published events with a real id from
  being clobbered): if `event.correlation_id` is already set, leave it.
- `uuid4` needs importing in `src/kernel/__init__.py` (`UUID` is already
  imported; `uuid4` is not).
- No changes to `EventLog`, no changes to any component (`Perception`,
  `WorldModel`, `Executive`, `Governor`, `Executor`, `MemoryLedger`,
  `InferencePort`) — they keep constructing events the same way they do
  today, satisfying "no component-specific propagation logic" and "existing
  public APIs unchanged."

## Testing

New tests in `tests/test_kernel.py` (or a new `tests/test_correlation_id.py`,
whichever fits the existing test file convention — check before adding):

1. **One observation → one correlation_id across the whole organism.**
   Wire Perception → WorldModel → Executive → Governor → Executor →
   MemoryLedger onto one Kernel (mirrors the existing composition-root test
   setup), call `record_observation`, drain, then assert every event read
   back from `EventLog.read_all()` for that run shares one non-null
   `correlation_id`.
2. **Two independent observations → two different correlation_ids.** Call
   `record_observation` twice (sequentially, so each fully drains before the
   next starts, matching how the synchronous kernel actually runs); assert
   the two resulting event groups have different `correlation_id`s and each
   group is internally consistent.
3. **Nested publish preserves the active id.** A subscriber that itself
   calls `kernel.publish()` again while handling an event (already implicit
   in the WorldModel → Executive → Governor → Executor chain, but add a
   focused unit test directly against `Kernel` using a minimal subscriber) —
   assert the nested event's `correlation_id` equals the triggering event's.
4. **Replay reproduces original correlation_ids exactly.** Build a Kernel
   against a persisted `EventLog` containing events with known
   `correlation_id`s, construct a fresh `Kernel` over the same log path,
   call `replay()`, and assert dispatched/read-back events carry the exact
   original `correlation_id` values (not regenerated).
5. Full existing suite (177 tests) still green — no regressions.

## Out of scope

- No new public API surface (no new constructor args, no new methods needed
  beyond the internal `_active_correlation_id` attribute).
- No concurrency/thread-safety handling — the kernel is single-threaded and
  synchronous today; this design relies on that.
