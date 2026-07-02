# Correlation ID Propagation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every event descending from one observation carries the same `correlation_id` end-to-end (Observation → Belief → Opportunity → Plan → Approval → Execution → Outcome → Memory); two independent observations get different ones; components never generate or overwrite a `correlation_id`.

**Architecture:** `Kernel.publish()` is the sole call site that appends to `EventLog`, so it's the single choke point for assignment. Add one `self._active_correlation_id: Optional[UUID]` slot to `Kernel`. `publish()` assigns a fresh `uuid4()` only when no correlation is currently active; otherwise the new event inherits the active one. The active id is cleared in `_dispatch_scheduled` exactly when `self.scheduler.pending_count() == 0` — i.e. when the whole cascade from one root event has fully drained — which is correct whether the drain happens synchronously inside `publish()` (kernel not yet started) or later via a caller's own `run_until_idle()` call (kernel already running, the real `main.py` path). No component code changes. `EventLog` and replay already round-trip `correlation_id` correctly (verified — `_encode_value`/`_decode_value` handle `Optional[UUID]` generically, and `Kernel.replay()` calls `dispatch()` directly, bypassing `publish()` entirely, so persisted ids are never touched).

**Tech Stack:** Python 3, `unittest` (stdlib), no new dependencies. Test runner: `python -m unittest discover -s tests` from `spawn/` (confirmed: 177 tests currently pass this way).

**Design doc:** `spawn/docs/superpowers/specs/2026-07-02-correlation-id-propagation-design.md`

---

### Task 1: Kernel assigns and propagates `correlation_id`

**Files:**
- Modify: `spawn/src/kernel/__init__.py`
- Create: `spawn/tests/test_correlation_id.py`

- [ ] **Step 1: Write the failing tests**

Create `spawn/tests/test_correlation_id.py`:

```python
import unittest
from uuid import UUID, uuid4

from src.events import Event, EventType
from src.kernel import Kernel


class KernelCorrelationIdTests(unittest.TestCase):
    def test_root_publish_assigns_a_fresh_correlation_id(self) -> None:
        kernel = Kernel()
        event = Event(source_component="perception", event_type=EventType.OBSERVATION_CREATED)

        kernel.publish(event)

        self.assertIsInstance(event.correlation_id, UUID)

    def test_two_independent_root_publishes_get_different_correlation_ids(self) -> None:
        kernel = Kernel()
        first = Event(source_component="perception", event_type=EventType.OBSERVATION_CREATED)
        second = Event(source_component="perception", event_type=EventType.OBSERVATION_CREATED)

        kernel.publish(first)
        kernel.publish(second)

        self.assertNotEqual(first.correlation_id, second.correlation_id)

    def test_nested_publish_during_dispatch_inherits_the_active_correlation_id(self) -> None:
        kernel = Kernel()
        kernel.start()
        triggering = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        nested = Event(source_component="world_model", event_type=EventType.PLAN_PROPOSED)

        def subscriber(event: Event) -> None:
            if event is triggering:
                kernel.publish(nested)

        kernel.register_subscriber(EventType.BELIEF_UPDATED, subscriber)
        kernel.publish(triggering)
        kernel.run_until_idle()

        self.assertIsNotNone(triggering.correlation_id)
        self.assertEqual(nested.correlation_id, triggering.correlation_id)

    def test_cascade_still_shares_one_id_when_drain_happens_after_publish_returns(self) -> None:
        # Mirrors the real main.py path: after start(), publish() for a
        # non-lifecycle event does NOT auto-drain; the caller drains later
        # via a separate run_until_idle() call. The active id must survive
        # that gap.
        kernel = Kernel()
        kernel.start()
        triggering = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        nested = Event(source_component="world_model", event_type=EventType.PLAN_PROPOSED)

        def subscriber(event: Event) -> None:
            if event is triggering:
                kernel.publish(nested)

        kernel.register_subscriber(EventType.BELIEF_UPDATED, subscriber)
        kernel.publish(triggering)  # returns without draining; queue still has 1 pending task
        self.assertEqual(kernel.scheduler.pending_count(), 1)

        kernel.run_until_idle()  # caller drains separately, as main.run_bootstrap_cycle does

        self.assertEqual(nested.correlation_id, triggering.correlation_id)

    def test_publish_never_overwrites_a_preexisting_correlation_id(self) -> None:
        kernel = Kernel()
        preset_id = uuid4()
        event = Event(
            source_component="perception",
            event_type=EventType.OBSERVATION_CREATED,
            correlation_id=preset_id,
        )

        kernel.publish(event)

        self.assertEqual(event.correlation_id, preset_id)

    def test_active_correlation_id_clears_after_full_cascade_drains(self) -> None:
        kernel = Kernel()
        kernel.start()
        first = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        kernel.publish(first)
        kernel.run_until_idle()

        second = Event(source_component="world_model", event_type=EventType.BELIEF_UPDATED)
        kernel.publish(second)
        kernel.run_until_idle()

        self.assertNotEqual(first.correlation_id, second.correlation_id)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd spawn && python -m unittest tests.test_correlation_id -v`
Expected: FAIL — `test_root_publish_assigns_a_fresh_correlation_id` and others fail with `AssertionError` because `event.correlation_id` is `None` (the field exists on `Event` already, but nothing assigns it yet).

- [ ] **Step 3: Implement the minimal change in `src/kernel/__init__.py`**

Change the import line (currently `from uuid import UUID`):

```python
from uuid import UUID, uuid4
```

In `Kernel.__init__`, add the new attribute (after `self._replayed = False`):

```python
        self._replayed = False
        self._active_correlation_id: Optional[UUID] = None
```

Replace the body of `Kernel.publish`:

```python
    def publish(self, event: Event) -> None:
        """Queue an event for processing by the event loop, via the scheduler.

        The Kernel is the sole owner of correlation_id propagation. A
        publish that happens while no correlation is currently active mints
        a fresh id (unless the event already carries one); every other
        publish inherits whatever id is currently active. The active id is
        cleared in `_dispatch_scheduled` once the scheduler's queue fully
        drains, not when this method returns — after the kernel has
        started, publish() for a non-lifecycle event schedules the task but
        does not drain it itself, so the active id must survive until the
        caller's own run_until_idle() call actually processes the cascade.
        """
        if self._replaying:
            return
        if event.correlation_id is None:
            event.correlation_id = (
                self._active_correlation_id if self._active_correlation_id is not None else uuid4()
            )
        if self._active_correlation_id is None:
            self._active_correlation_id = event.correlation_id
        self.event_log.append(event)
        if event.event_type in self._TERMINAL_LIFECYCLE_TYPES:
            self._pending_terminal_lifecycle += 1
        self.scheduler.schedule(lambda: self._dispatch_scheduled(event))
        if not self._dispatching and (not self._started or event.event_type in self._LIFECYCLE_TYPES):
            self.run_until_idle()
```

Replace the body of `Kernel._dispatch_scheduled`:

```python
    def _dispatch_scheduled(self, event: Event) -> None:
        """Business logic executed by the scheduler for one queued event."""
        if event.event_type in self._TERMINAL_LIFECYCLE_TYPES:
            self._pending_terminal_lifecycle -= 1
        if self._stopping and event.event_type not in self._LIFECYCLE_TYPES:
            if self.scheduler.pending_count() == 0:
                self._active_correlation_id = None
            return
        self._dispatching = True
        self.dispatch(event)
        self._dispatching = False
        if self.scheduler.pending_count() == 0:
            self._active_correlation_id = None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd spawn && python -m unittest tests.test_correlation_id -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Run the full existing suite for regressions**

Run: `cd spawn && python -m unittest discover -s tests -v`
Expected: `Ran 178 tests` — wait, this task only adds `test_correlation_id.py` (6 tests) on top of the existing 177, so expect `Ran 183 tests ... OK`. (177 existing + 6 new = 183.)

- [ ] **Step 6: Commit**

```bash
cd spawn
git add src/kernel/__init__.py tests/test_correlation_id.py
git commit -m "$(cat <<'EOF'
Add correlation_id propagation to Kernel.publish

Single choke point for the whole organism: a publish with no active
correlation mints a fresh id, everything else inherits it. Clearing is
tied to the scheduler actually draining to empty (in
_dispatch_scheduled), not to publish() returning, since after start()
publish() for a non-lifecycle event schedules without draining -- the
caller drains separately later.
EOF
)"
```

---

### Task 2: End-to-end organism test — one observation, one correlation_id

**Files:**
- Modify: `spawn/tests/test_composition_root.py`

This file already has a `BootstrapCycleTests` class whose `setUp` builds a full `Organism` (`main.build_organism()` + `main.configure_bootstrap()` + `kernel.start()`), and an existing test (`test_full_cycle_emits_events_in_architectural_order`) that proves one `record_observation()` cascades into exactly 18 typed events across every component. Add a sibling test asserting all 18 share one `correlation_id`.

- [ ] **Step 1: Write the failing test**

Add this method to the `BootstrapCycleTests` class in `spawn/tests/test_composition_root.py` (place it right after `test_full_cycle_emits_events_in_architectural_order`):

```python
    def test_full_cycle_shares_one_correlation_id_across_every_event(self) -> None:
        start_sequence = self.organism.kernel.event_log.latest_sequence() + 1

        main.run_bootstrap_cycle(self.organism)

        cascade = self.organism.kernel.event_log.read_from(start_sequence)
        correlation_ids = {event.correlation_id for _, event in cascade}

        self.assertEqual(len(cascade), 18)
        self.assertEqual(len(correlation_ids), 1)
        self.assertIsNotNone(next(iter(correlation_ids)))
```

- [ ] **Step 2: Run the test**

This is a pure end-to-end verification test — Task 1 already implemented the underlying behavior, so no new production code is needed here. (If run against a checkout *without* Task 1 applied, it would FAIL on `assertIsNotNone`, since every event's `correlation_id` would still be `None`.)

Run: `cd spawn && python -m unittest tests.test_composition_root.BootstrapCycleTests.test_full_cycle_shares_one_correlation_id_across_every_event -v`
Expected: PASS

- [ ] **Step 4: Run the full suite for regressions**

Run: `cd spawn && python -m unittest discover -s tests -v`
Expected: `Ran 184 tests ... OK`

- [ ] **Step 5: Commit**

```bash
cd spawn
git add tests/test_composition_root.py
git commit -m "test: assert one observation yields one correlation_id end-to-end"
```

---

### Task 3: End-to-end organism test — two independent observations, two different correlation_ids

**Files:**
- Modify: `spawn/tests/test_composition_root.py`

- [ ] **Step 1: Write the failing test**

Add this method to `BootstrapCycleTests`, right after the test added in Task 2:

```python
    def test_two_independent_cycles_receive_different_correlation_ids(self) -> None:
        before_first = len(self.organism.kernel.event_log.read_all())
        main.run_bootstrap_cycle(self.organism)
        after_first = len(self.organism.kernel.event_log.read_all())

        main.run_bootstrap_cycle(self.organism)
        after_second = len(self.organism.kernel.event_log.read_all())

        all_events = [event for _, event in self.organism.kernel.event_log.read_all()]
        first_cascade = all_events[before_first:after_first]
        second_cascade = all_events[after_first:after_second]

        first_ids = {event.correlation_id for event in first_cascade}
        second_ids = {event.correlation_id for event in second_cascade}

        self.assertEqual(len(first_cascade), 18)
        self.assertEqual(len(second_cascade), 18)
        self.assertEqual(len(first_ids), 1)
        self.assertEqual(len(second_ids), 1)
        self.assertNotEqual(first_ids, second_ids)
```

- [ ] **Step 2: Run the test**

Pure verification test, same as Task 2 — Task 1's Kernel change already makes this correct; no new production code here.

Run: `cd spawn && python -m unittest tests.test_composition_root.BootstrapCycleTests.test_two_independent_cycles_receive_different_correlation_ids -v`
Expected: PASS

- [ ] **Step 3: Run the full suite for regressions**

Run: `cd spawn && python -m unittest discover -s tests -v`
Expected: `Ran 185 tests ... OK`

- [ ] **Step 4: Commit**

```bash
cd spawn
git add tests/test_composition_root.py
git commit -m "test: assert two independent observation cycles get different correlation_ids"
```

---

### Task 4: Replay preserves original `correlation_id`s exactly

**Files:**
- Modify: `spawn/tests/test_replay.py`

This file already has `_boot_fresh(log_path)` (runs one full bootstrap cycle against a persistent `EventLog`) and a pattern (`test_replay_preserves_original_event_order`) for registering a catch-all subscriber across every `EventType` and replaying. Reuse both.

- [ ] **Step 1: Write the failing test**

Add this method to `ReplayOnStartTests` in `spawn/tests/test_replay.py`, right after `test_replay_preserves_original_event_order`:

```python
    def test_replay_preserves_original_correlation_ids_exactly(self) -> None:
        _boot_fresh(self.log_path)

        replay_log = EventLog(path=self.log_path)
        original_correlation_ids = [event.correlation_id for _, event in replay_log.read_all()]
        self.assertGreater(len(original_correlation_ids), 0)
        self.assertTrue(all(cid is not None for cid in original_correlation_ids))

        replayed_correlation_ids: list[object] = []
        kernel = Kernel(event_log=replay_log)

        def record(event: object) -> None:
            replayed_correlation_ids.append(event.correlation_id)  # type: ignore[attr-defined]

        for event_type in EventType:
            kernel.register_subscriber(event_type, record)

        kernel.replay()

        self.assertEqual(replayed_correlation_ids, original_correlation_ids)
```

- [ ] **Step 2: Run the test**

Pure verification test — Task 1's Kernel change already makes this correct, and replay itself needed zero new code (`Kernel.replay()` calls `dispatch()` directly, bypassing `publish()`, so persisted ids are never regenerated). (Without Task 1 applied, this would FAIL on `self.assertTrue(all(cid is not None for cid in original_correlation_ids))`, since every persisted `correlation_id` would still be `None`.)

Run: `cd spawn && python -m unittest tests.test_replay.ReplayOnStartTests.test_replay_preserves_original_correlation_ids_exactly -v`
Expected: PASS

- [ ] **Step 3: Run the full suite for regressions**

Run: `cd spawn && python -m unittest discover -s tests -v`
Expected: `Ran 186 tests ... OK`

- [ ] **Step 4: Commit**

```bash
cd spawn
git add tests/test_replay.py
git commit -m "test: assert replay reproduces original correlation_ids exactly"
```

---

### Task 5: Final full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the complete suite one more time from a clean state**

Run: `cd spawn && python -m unittest discover -s tests -v 2>&1 | tail -5`
Expected: `Ran 186 tests in <N>s` followed by `OK` — 177 original + 9 new (6 in Task 1, 1 each in Tasks 2–4).

- [ ] **Step 2: Confirm no stray state**

Run: `cd "c:\Users\Assya\Desktop\newnew" && git status --porcelain`
Expected: clean (everything from Tasks 1–4 committed); pre-existing unrelated entries (`D spawn/Architecture.md`, `?? spawn/repass.pdf`) are out of scope for this task and should be left untouched.
