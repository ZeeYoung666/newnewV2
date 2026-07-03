# Kernel Snapshotting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Kernel persist a point-in-time snapshot of organism state and restore from the latest snapshot on replay, so restart no longer means re-dispatching the event log from sequence 1.

**Architecture:** The Kernel already owns `EventLog` (append-only, disk-backed) and `replay()` (re-dispatches persisted events to rebuild in-memory state — landed in Task #18's predecessor work). Add a sibling `SnapshotStore` the Kernel also owns: a single-record, atomically-overwritten JSON file holding `{sequence, sources}`. Components register their own store's capture/restore closures with the Kernel via `register_snapshot_source(name, item_cls, capture, restore)` — mirroring the existing `register_subscriber` pattern already used for events, so ownership stays exactly where it is today (each component only ever touches its own store). `Kernel.replay()` becomes: load the latest snapshot (if any) and call each source's `restore()`, then dispatch only the event-log tail after the snapshot's sequence number. With no snapshot present, behavior is byte-for-byte identical to today (dispatch from sequence 1).

Only 10 of the organism's stores are populated purely by Kernel-dispatched event handlers (verified by grepping every `register_subscriber` call and its handler body): `world_model.belief_store`, `executive.opportunity_store`, `executive.plan_store`, `executive.decision_record_store`, `governor.budget_store`, `governor.approval_log`, `executor.action_log`, `memory_ledger.outcome_store`, `memory_ledger.episodic_memory_store`, `memory_ledger.financial_ledger`. Everything else (`SensorRegistry`, `ToolRegistry`, `ConstitutionStore`, `GoalStore`, `HeuristicStore`, `ObservationLog`) is populated by direct calls from bootstrap config or a component's own public API, never by dispatch — `_reboot()` already re-applies that config on every boot (see `tests/test_replay.py`), and Task #19 does not change that. Snapshotting only those 10 sources keeps "existing replay semantics unchanged": anything replay doesn't reconstruct today, snapshotting doesn't need to reconstruct either.

**Tech Stack:** Python 3, stdlib only (`json`, `dataclasses`, `typing`, `pathlib`, `tempfile`, `os`) — same toolkit `EventLog` already uses. `unittest`, no pytest (confirmed not installed in this environment).

---

## File Structure

- `spawn/src/kernel/__init__.py` — add `SnapshotStore` class, generalize the existing `_encode_event`/`_decode_event` dataclass codec into reusable `_encode_dataclass_fields`/`_decode_dataclass` helpers, add `EventLog.path` property, add `Kernel.register_snapshot_source`/`Kernel.create_snapshot`, make `Kernel.replay()` snapshot-aware.
- `spawn/src/world_model/__init__.py` — register `belief_store` as a snapshot source.
- `spawn/src/executive/__init__.py` — register `opportunity_store`, `plan_store`, `decision_record_store` as snapshot sources.
- `spawn/src/governor/__init__.py` — register `budget_store`, `approval_log` as snapshot sources.
- `spawn/src/executor/__init__.py` — register `action_log` as a snapshot source.
- `spawn/src/memory/__init__.py` — register `outcome_store`, `episodic_memory_store`, `financial_ledger` as snapshot sources.
- `spawn/tests/test_kernel.py` — unit tests for `SnapshotStore` and `Kernel.create_snapshot`/`register_snapshot_source`.
- `spawn/tests/test_snapshot.py` (new) — integration tests: snapshot-assisted replay vs full replay, restart determinism, tail-only dispatch.

No file split needed — `kernel/__init__.py` is already the single home for all Kernel-owned infrastructure (`EventLog`, `Scheduler`, `Kernel`); `SnapshotStore` belongs there for the same reason.

---

## Task 1: `EventLog.path` property

**Files:**
- Modify: `spawn/src/kernel/__init__.py:77-136` (the `EventLog` class)
- Test: `spawn/tests/test_kernel.py`

- [ ] **Step 1: Write the failing test**

Add to `spawn/tests/test_kernel.py` inside a class near the other `EventLog` tests (or a new small one):

```python
class EventLogPathTests(unittest.TestCase):
    def test_path_property_exposes_backing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"
            log = EventLog(path=log_path)

            self.assertEqual(log.path, log_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_kernel.EventLogPathTests -v`
Expected: `FAIL` / `AttributeError: 'EventLog' object has no attribute 'path'`

- [ ] **Step 3: Add the property**

In `spawn/src/kernel/__init__.py`, inside `class EventLog`, immediately after `__init__` (after line 95, before `_load_existing`):

```python
    @property
    def path(self) -> Path:
        """The on-disk location backing this log."""
        return self._path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_kernel.EventLogPathTests -v`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add spawn/src/kernel/__init__.py spawn/tests/test_kernel.py
git commit -m "feat: expose EventLog.path for snapshot colocation"
```

---

## Task 2: Generalize the dataclass codec (refactor, no new behavior)

**Files:**
- Modify: `spawn/src/kernel/__init__.py:65-74` (`_encode_event`/`_decode_event`)

- [ ] **Step 1: Extract reusable helpers**

Replace lines 65-74 in `spawn/src/kernel/__init__.py`:

```python
def _encode_event(sequence_number: int, event: Event) -> dict:
    fields = {f.name: _encode_value(getattr(event, f.name)) for f in dataclasses.fields(event)}
    return {"sequence": sequence_number, "class": type(event).__name__, "fields": fields}


def _decode_event(record: dict) -> tuple[int, Event]:
    cls = _EVENT_CLASSES[record["class"]]
    type_hints = typing.get_type_hints(cls)
    kwargs = {name: _decode_value(value, type_hints[name]) for name, value in record["fields"].items()}
    return record["sequence"], cls(**kwargs)
```

with:

```python
def _encode_dataclass_fields(obj: object) -> dict:
    """Encode every field of an arbitrary dataclass instance to a JSON-safe dict.

    Shared by event log persistence and snapshot persistence — both need the
    same UUID/datetime/tuple-aware field encoding, just wrapped differently.
    """
    return {f.name: _encode_value(getattr(obj, f.name)) for f in dataclasses.fields(obj)}


def _decode_dataclass(fields: dict, cls: type) -> object:
    """Decode a JSON-safe field dict back into an instance of the given dataclass."""
    type_hints = typing.get_type_hints(cls)
    kwargs = {name: _decode_value(value, type_hints[name]) for name, value in fields.items()}
    return cls(**kwargs)


def _encode_event(sequence_number: int, event: Event) -> dict:
    return {"sequence": sequence_number, "class": type(event).__name__, "fields": _encode_dataclass_fields(event)}


def _decode_event(record: dict) -> tuple[int, Event]:
    cls = _EVENT_CLASSES[record["class"]]
    return record["sequence"], _decode_dataclass(record["fields"], cls)
```

This is a pure refactor — behavior is identical, so no new test is required. The existing event-log tests in `test_kernel.py` and every replay/correlation test are the regression safety net.

- [ ] **Step 2: Run the full suite to confirm no regression**

Run: `python -m unittest discover -s tests`
Expected: `OK` (same 186 tests as before this plan started)

- [ ] **Step 3: Commit**

```bash
git add spawn/src/kernel/__init__.py
git commit -m "refactor: generalize event codec into reusable dataclass encode/decode"
```

---

## Task 3: `SnapshotStore`

**Files:**
- Modify: `spawn/src/kernel/__init__.py` — add `SnapshotStore` class after `EventLog`, before `Scheduler`
- Test: `spawn/tests/test_kernel.py`

- [ ] **Step 1: Write the failing tests**

Add to `spawn/tests/test_kernel.py`:

```python
class SnapshotStoreTests(unittest.TestCase):
    def test_load_returns_none_when_no_snapshot_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(path=Path(tmpdir) / "events.snapshot.json")

            self.assertIsNone(store.load())

    def test_save_then_load_round_trips_the_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(path=Path(tmpdir) / "events.snapshot.json")

            store.save(7, {"world_model.beliefs": [{"belief_id": "sensor:x", "confidence": 0.5}]})
            record = store.load()

            self.assertEqual(record["sequence"], 7)
            self.assertEqual(record["sources"]["world_model.beliefs"][0]["belief_id"], "sensor:x")

    def test_save_overwrites_the_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(path=Path(tmpdir) / "events.snapshot.json")

            store.save(1, {"a": []})
            store.save(2, {"b": []})
            record = store.load()

            self.assertEqual(record["sequence"], 2)
            self.assertEqual(record["sources"], {"b": []})

    def test_default_path_is_isolated_per_instance(self) -> None:
        first = SnapshotStore()
        second = SnapshotStore()

        first.save(1, {"a": []})

        self.assertIsNone(second.load())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_kernel.SnapshotStoreTests -v`
Expected: `FAIL` / `ImportError: cannot import name 'SnapshotStore'` (once added to the test file's import line — see Step 3)

- [ ] **Step 3: Update the test file's import**

In `spawn/tests/test_kernel.py`, change line 16 from:

```python
from src.kernel import EventLog, Kernel, Scheduler, Subscriber
```

to:

```python
from src.kernel import EventLog, Kernel, Scheduler, SnapshotStore, Subscriber
```

- [ ] **Step 4: Implement `SnapshotStore`**

In `spawn/src/kernel/__init__.py`, insert immediately after the `EventLog` class (after line 136, before `class Scheduler:`):

```python
class SnapshotStore:
    """Disk-backed store for the single most recent organism snapshot.

    Every create_snapshot() call atomically overwrites this file — only the
    latest snapshot is ever retained, there is no history of snapshots. The
    EventLog itself is never touched by this class and stays append-only
    regardless of how many snapshots are taken.
    """

    def __init__(self, path: Union[str, "os.PathLike[str]", None] = None) -> None:
        if path is None:
            fd, generated_path = tempfile.mkstemp(suffix=".snapshot.json", prefix="snapshot-")
            os.close(fd)
            path = generated_path
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, sequence: int, sources: dict) -> None:
        """Atomically persist a snapshot, replacing whatever was there before."""
        record = {"sequence": sequence, "sources": sources}
        tmp_path = self._path.with_name(self._path.name + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(record, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, self._path)

    def load(self) -> Optional[dict]:
        """Return the persisted snapshot record, or None if none exists yet."""
        if not self._path.exists():
            return None
        with self._path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
```

Also update the module's `__all__` (last line of the file):

```python
__all__ = ["EventLog", "Kernel", "Scheduler", "SnapshotStore", "Subscriber"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.test_kernel.SnapshotStoreTests -v`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add spawn/src/kernel/__init__.py spawn/tests/test_kernel.py
git commit -m "feat: add SnapshotStore for durable organism snapshots"
```

---

## Task 4: `Kernel.register_snapshot_source` + `Kernel.create_snapshot`

**Files:**
- Modify: `spawn/src/kernel/__init__.py` (the `Kernel` class)
- Test: `spawn/tests/test_kernel.py`

- [ ] **Step 1: Write the failing tests**

Add to `spawn/tests/test_kernel.py`:

```python
@dataclass(slots=True, kw_only=True, frozen=True)
class _StubRecord:
    record_id: str
    value: float


class KernelSnapshotTests(unittest.TestCase):
    def test_kernel_derives_a_snapshot_path_from_the_event_log_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"
            kernel = Kernel(event_log=EventLog(path=log_path))

            self.assertEqual(kernel.snapshot_store._path, Path(tmpdir) / "events.snapshot.json")

    def test_create_snapshot_returns_the_event_log_sequence(self) -> None:
        kernel = Kernel()
        kernel.publish(Event(source_component="test", event_type=EventType.BELIEF_UPDATED))
        kernel.publish(Event(source_component="test", event_type=EventType.BELIEF_UPDATED))

        sequence = kernel.create_snapshot()

        self.assertEqual(sequence, 2)

    def test_create_snapshot_persists_every_registered_source(self) -> None:
        kernel = Kernel()
        store: list[_StubRecord] = [_StubRecord(record_id="a", value=1.0)]
        kernel.register_snapshot_source("stub", _StubRecord, lambda: store, store.extend)

        kernel.create_snapshot()
        record = kernel.snapshot_store.load()

        self.assertEqual(record["sources"]["stub"], [{"record_id": "a", "value": 1.0}])

    def test_create_snapshot_with_no_sources_registered_persists_an_empty_record(self) -> None:
        kernel = Kernel()

        sequence = kernel.create_snapshot()
        record = kernel.snapshot_store.load()

        self.assertEqual(sequence, 0)
        self.assertEqual(record["sources"], {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_kernel.KernelSnapshotTests -v`
Expected: `FAIL` / `AttributeError: 'Kernel' object has no attribute 'snapshot_store'`

(Also add `Event`, `dataclass` to the test file's imports if not already present — `Event` and `EventType` are already imported at the top; add `from dataclasses import dataclass` near the top of `test_kernel.py`.)

- [ ] **Step 3: Add snapshot plumbing to `Kernel`**

In `spawn/src/kernel/__init__.py`, add a type alias near the top (after the existing `Subscriber = Callable[[Event], None]` line):

```python
SnapshotCapture = Callable[[], list]
SnapshotRestore = Callable[[list], None]
```

Change `Kernel.__init__` (currently lines 202-213) from:

```python
    def __init__(self, event_log: Optional[EventLog] = None) -> None:
        self._subscribers: DefaultDict[EventType, list[Subscriber]] = defaultdict(list)
        self.event_log = event_log if event_log is not None else EventLog()
        self.scheduler = Scheduler()
        self._pending_terminal_lifecycle = 0
        self._running = False
        self._started = False
        self._dispatching = False
        self._stopping = False
        self._replaying = False
        self._replayed = False
        self._active_correlation_id: Optional[UUID] = None
```

to:

```python
    def __init__(
        self, event_log: Optional[EventLog] = None, snapshot_store: Optional[SnapshotStore] = None
    ) -> None:
        self._subscribers: DefaultDict[EventType, list[Subscriber]] = defaultdict(list)
        self.event_log = event_log if event_log is not None else EventLog()
        self.snapshot_store = (
            snapshot_store
            if snapshot_store is not None
            else SnapshotStore(path=self.event_log.path.with_suffix(".snapshot.json"))
        )
        self._snapshot_sources: dict[str, tuple[type, SnapshotCapture, SnapshotRestore]] = {}
        self.scheduler = Scheduler()
        self._pending_terminal_lifecycle = 0
        self._running = False
        self._started = False
        self._dispatching = False
        self._stopping = False
        self._replaying = False
        self._replayed = False
        self._active_correlation_id: Optional[UUID] = None
```

Add two new methods to `Kernel`, right after `unsubscribe` (after line 231, before `start`):

```python
    def register_snapshot_source(
        self, name: str, item_cls: type, capture: SnapshotCapture, restore: SnapshotRestore
    ) -> None:
        """Register a component's own store for snapshot capture/restore.

        `capture` and `restore` close over exactly one component's own store
        (e.g. `self.belief_store.read_all` / a helper that calls
        `self.belief_store.put` for each item) — the Kernel only ever sees an
        opaque list of `item_cls` instances, never reaches into store
        internals itself, and never crosses into another component's store.
        """
        self._snapshot_sources[name] = (item_cls, capture, restore)

    def create_snapshot(self) -> int:
        """Capture every registered source's current state at the event log's
        current sequence number and persist it as the new latest snapshot.
        """
        sequence = self.event_log.latest_sequence()
        sources = {
            name: [_encode_dataclass_fields(item) for item in capture()]
            for name, (_, capture, _) in self._snapshot_sources.items()
        }
        self.snapshot_store.save(sequence, sources)
        return sequence
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_kernel.KernelSnapshotTests -v`
Expected: `OK`

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `python -m unittest discover -s tests`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add spawn/src/kernel/__init__.py spawn/tests/test_kernel.py
git commit -m "feat: Kernel owns snapshot creation via registered per-component sources"
```

---

## Task 5: Snapshot-aware `Kernel.replay()`

**Files:**
- Modify: `spawn/src/kernel/__init__.py:257-281` (`Kernel.replay`)
- Test: `spawn/tests/test_kernel.py`

- [ ] **Step 1: Write the failing tests**

Add to `spawn/tests/test_kernel.py`:

```python
class KernelSnapshotReplayTests(unittest.TestCase):
    def test_replay_with_no_snapshot_dispatches_every_event(self) -> None:
        kernel = Kernel()
        received: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, received.append)
        kernel.publish(Event(source_component="test", event_type=EventType.BELIEF_UPDATED))
        kernel.publish(Event(source_component="test", event_type=EventType.BELIEF_UPDATED))

        rebuilt = Kernel(event_log=kernel.event_log)
        rebuilt.register_subscriber(EventType.BELIEF_UPDATED, received.append)
        rebuilt.replay()

        self.assertEqual(len(received), 4)  # 2 from the live kernel, 2 from replay

    def test_replay_restores_snapshot_state_via_registered_source(self) -> None:
        kernel = Kernel()
        store: list[_StubRecord] = []
        kernel.register_snapshot_source("stub", _StubRecord, lambda: store, store.extend)
        store.append(_StubRecord(record_id="a", value=1.0))
        kernel.create_snapshot()

        rebuilt = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        restored: list[_StubRecord] = []
        rebuilt.register_snapshot_source("stub", _StubRecord, lambda: restored, restored.extend)
        rebuilt.replay()

        self.assertEqual(restored, [_StubRecord(record_id="a", value=1.0)])

    def test_replay_only_dispatches_events_after_the_snapshot_sequence(self) -> None:
        kernel = Kernel()
        dispatched: list[Event] = []
        kernel.register_subscriber(EventType.BELIEF_UPDATED, dispatched.append)
        kernel.publish(Event(source_component="test", event_type=EventType.BELIEF_UPDATED))
        kernel.publish(Event(source_component="test", event_type=EventType.BELIEF_UPDATED))
        kernel.create_snapshot()
        kernel.publish(Event(source_component="test", event_type=EventType.BELIEF_UPDATED))

        rebuilt = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        replayed: list[Event] = []
        rebuilt.register_subscriber(EventType.BELIEF_UPDATED, replayed.append)
        rebuilt.replay()

        self.assertEqual(len(replayed), 1)  # only the post-snapshot event
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_kernel.KernelSnapshotReplayTests -v`
Expected: `FAIL` — `test_replay_restores_snapshot_state_via_registered_source` and `test_replay_only_dispatches_events_after_the_snapshot_sequence` fail because `replay()` doesn't consult the snapshot store yet (`test_replay_with_no_snapshot_dispatches_every_event` should already pass — it's a regression pin, not a new behavior).

- [ ] **Step 3: Make `replay()` snapshot-aware**

Replace `Kernel.replay` (currently lines 257-281) in `spawn/src/kernel/__init__.py`:

```python
    def replay(self) -> int:
        """Reconstruct component state from the latest snapshot (if any) plus
        every event recorded after it, in original sequence order. Must run
        before the kernel starts, and runs at most once.

        With no snapshot present this dispatches from sequence 1, identical
        to full replay. Events a handler re-publishes while this runs are not
        re-appended to the log or re-dispatched here: each one is already its
        own entry in the log and gets visited directly by this same loop when
        its own sequence number is reached. Suppressing the nested publish is
        what keeps every historical event dispatched exactly once and leaves
        the log with no duplicates.
        """
        if self._started:
            raise RuntimeError("cannot replay after the kernel has started")
        if self._replayed:
            raise RuntimeError("replay has already run for this kernel")

        self._replaying = True
        try:
            snapshot_sequence = self._restore_latest_snapshot()
            start_sequence = 1 if snapshot_sequence is None else snapshot_sequence + 1
            for _, event in self.event_log.read_from(start_sequence):
                self.dispatch(event)
        finally:
            self._replaying = False
        self._replayed = True
        return self.event_log.latest_sequence()

    def _restore_latest_snapshot(self) -> Optional[int]:
        """Load the latest snapshot (if any) and hand each source's state back
        to the component that registered it. Returns the snapshot's sequence
        number, or None if no snapshot has ever been taken.
        """
        record = self.snapshot_store.load()
        if record is None:
            return None
        for name, encoded_items in record["sources"].items():
            if name not in self._snapshot_sources:
                continue
            item_cls, _, restore = self._snapshot_sources[name]
            restore([_decode_dataclass(fields, item_cls) for fields in encoded_items])
        return record["sequence"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_kernel.KernelSnapshotReplayTests -v`
Expected: `OK`

- [ ] **Step 5: Run the full suite to confirm no regression**

Run: `python -m unittest discover -s tests`
Expected: `OK` — in particular every existing `tests/test_replay.py` test must still pass unchanged, since none of them ever call `create_snapshot()` and so `_restore_latest_snapshot()` always returns `None` for them, giving byte-identical old behavior.

- [ ] **Step 6: Commit**

```bash
git add spawn/src/kernel/__init__.py spawn/tests/test_kernel.py
git commit -m "feat: Kernel.replay restores latest snapshot before dispatching the tail"
```

---

## Task 6: Register the 10 real snapshot sources

**Files:**
- Modify: `spawn/src/world_model/__init__.py`
- Modify: `spawn/src/executive/__init__.py`
- Modify: `spawn/src/governor/__init__.py`
- Modify: `spawn/src/executor/__init__.py`
- Modify: `spawn/src/memory/__init__.py`

No new unit tests in this task — correctness is proven by Task 7's integration tests (snapshot-assisted replay producing identical state to full replay is a much stronger check than testing each registration in isolation). Each edit below follows the exact same shape: one `kernel.register_snapshot_source(...)` call added next to the component's existing `kernel.register_subscriber(...)` call, plus a small private `_restore_*` method that calls the store's existing `put`/`append` for each item — no new store methods, no cross-store access, ownership unchanged.

- [ ] **Step 1: World Model — `belief_store`**

In `spawn/src/world_model/__init__.py`, change `WorldModel.__init__` (lines 59-62) from:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.belief_store = BeliefStore()
        kernel.register_subscriber(EventType.OBSERVATION_CREATED, self._on_observation_created)
```

to:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.belief_store = BeliefStore()
        kernel.register_subscriber(EventType.OBSERVATION_CREATED, self._on_observation_created)
        kernel.register_snapshot_source(
            "world_model.beliefs", Belief, self.belief_store.read_all, self._restore_beliefs
        )

    def _restore_beliefs(self, beliefs: list[Belief]) -> None:
        for belief in beliefs:
            self.belief_store.put(belief)
```

- [ ] **Step 2: Executive — `opportunity_store`, `plan_store`, `decision_record_store`**

In `spawn/src/executive/__init__.py`, change `Executive.__init__` (lines 150-157) from:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.goal_store = GoalStore()
        self.opportunity_store = OpportunityStore()
        self.plan_store = PlanStore()
        self.decision_record_store = DecisionRecordStore()
        kernel.register_subscriber(EventType.BELIEF_CREATED, self._on_belief_created)
        kernel.register_subscriber(EventType.BELIEF_UPDATED, self._on_belief_updated)
```

to:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.goal_store = GoalStore()
        self.opportunity_store = OpportunityStore()
        self.plan_store = PlanStore()
        self.decision_record_store = DecisionRecordStore()
        kernel.register_subscriber(EventType.BELIEF_CREATED, self._on_belief_created)
        kernel.register_subscriber(EventType.BELIEF_UPDATED, self._on_belief_updated)
        kernel.register_snapshot_source(
            "executive.opportunities", Opportunity, self.opportunity_store.read_all, self._restore_opportunities
        )
        kernel.register_snapshot_source("executive.plans", Plan, self.plan_store.read_all, self._restore_plans)
        kernel.register_snapshot_source(
            "executive.decision_records",
            DecisionRecord,
            self.decision_record_store.read_all,
            self._restore_decision_records,
        )

    def _restore_opportunities(self, opportunities: list[Opportunity]) -> None:
        for opportunity in opportunities:
            self.opportunity_store.append(opportunity)

    def _restore_plans(self, plans: list[Plan]) -> None:
        for plan in plans:
            self.plan_store.append(plan)

    def _restore_decision_records(self, records: list[DecisionRecord]) -> None:
        for record in records:
            self.decision_record_store.append(record)
```

- [ ] **Step 3: Governor — `budget_store`, `approval_log`**

In `spawn/src/governor/__init__.py`, change `Governor.__init__` (lines 125-132) from:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.constitution_store = ConstitutionStore()
        self.budget_store = BudgetStore()
        self.approval_log = ApprovalLog()
        self._active_constitution_id: Optional[str] = None
        self._active_budget_id: Optional[str] = None
        kernel.register_subscriber(EventType.PLAN_PROPOSED, self._on_plan_proposed)
```

to:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.constitution_store = ConstitutionStore()
        self.budget_store = BudgetStore()
        self.approval_log = ApprovalLog()
        self._active_constitution_id: Optional[str] = None
        self._active_budget_id: Optional[str] = None
        kernel.register_subscriber(EventType.PLAN_PROPOSED, self._on_plan_proposed)
        kernel.register_snapshot_source(
            "governor.budgets", BudgetState, self.budget_store.read_all, self._restore_budgets
        )
        kernel.register_snapshot_source(
            "governor.approvals", ApprovalRecord, self.approval_log.read_all, self._restore_approvals
        )

    def _restore_budgets(self, budgets: list[BudgetState]) -> None:
        for budget in budgets:
            self.budget_store.put(budget)

    def _restore_approvals(self, records: list[ApprovalRecord]) -> None:
        for record in records:
            self.approval_log.append(record)
```

Note: `budget_store` is snapshotted even though its *initial* funding comes from `configure_bootstrap()` (config, re-applied every boot) — because `_on_plan_proposed` → `_grant()` *also* mutates it via `budget_store.put(...)` on approval (reserving attention/capital). That mutation only happens through dispatch, so it's exactly the kind of state snapshotting must capture. Restoring after config re-funds the same `budget_id` correctly overwrites it with the post-events value (see plan's Architecture section).

- [ ] **Step 4: Executor — `action_log`**

In `spawn/src/executor/__init__.py`, change `Executor.__init__` (lines 88-92) from:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.tool_registry = ToolRegistry()
        self.action_log = ActionLog()
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, self._on_approval_granted)
```

to:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.tool_registry = ToolRegistry()
        self.action_log = ActionLog()
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, self._on_approval_granted)
        kernel.register_snapshot_source(
            "executor.actions", ActionRecord, self.action_log.read_all, self._restore_actions
        )

    def _restore_actions(self, records: list[ActionRecord]) -> None:
        for record in records:
            self.action_log.append(record)
```

- [ ] **Step 5: Memory & Ledger — `outcome_store`, `episodic_memory_store`, `financial_ledger`**

In `spawn/src/memory/__init__.py`, change `MemoryLedger.__init__` (lines 132-139) from:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.outcome_store = OutcomeStore()
        self.episodic_memory_store = EpisodicMemoryStore()
        self.financial_ledger = FinancialLedger()
        self.heuristic_store = HeuristicStore()
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, self._on_action_succeeded)
        kernel.register_subscriber(EventType.ACTION_FAILED, self._on_action_failed)
```

to:

```python
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self.outcome_store = OutcomeStore()
        self.episodic_memory_store = EpisodicMemoryStore()
        self.financial_ledger = FinancialLedger()
        self.heuristic_store = HeuristicStore()
        kernel.register_subscriber(EventType.ACTION_SUCCEEDED, self._on_action_succeeded)
        kernel.register_subscriber(EventType.ACTION_FAILED, self._on_action_failed)
        kernel.register_snapshot_source(
            "memory.outcomes", Outcome, self.outcome_store.read_all, self._restore_outcomes
        )
        kernel.register_snapshot_source(
            "memory.episodic_entries",
            EpisodicMemoryEntry,
            self.episodic_memory_store.read_all,
            self._restore_episodic_entries,
        )
        kernel.register_snapshot_source(
            "memory.ledger_entries", LedgerEntry, self.financial_ledger.read_all, self._restore_ledger_entries
        )

    def _restore_outcomes(self, outcomes: list[Outcome]) -> None:
        for outcome in outcomes:
            self.outcome_store.append(outcome)

    def _restore_episodic_entries(self, entries: list[EpisodicMemoryEntry]) -> None:
        for entry in entries:
            self.episodic_memory_store.append(entry)

    def _restore_ledger_entries(self, entries: list[LedgerEntry]) -> None:
        for entry in entries:
            self.financial_ledger.append(entry)
```

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `python -m unittest discover -s tests`
Expected: `OK` — registering sources with no `create_snapshot()` call anywhere yet changes nothing observable.

- [ ] **Step 7: Commit**

```bash
git add spawn/src/world_model/__init__.py spawn/src/executive/__init__.py spawn/src/governor/__init__.py spawn/src/executor/__init__.py spawn/src/memory/__init__.py
git commit -m "feat: register every event-sourced store as a Kernel snapshot source"
```

---

## Task 7: Integration tests (the task's required proof)

**Files:**
- Create: `spawn/tests/test_snapshot.py`

- [ ] **Step 1: Write the integration tests**

Create `spawn/tests/test_snapshot.py`:

```python
import tempfile
import unittest
from pathlib import Path

import main
from src.kernel import EventLog, Kernel


def _boot_fresh(log_path: Path) -> main.Organism:
    kernel = Kernel(event_log=EventLog(path=log_path))
    organism = main.build_organism(kernel=kernel)
    main.configure_bootstrap(organism)
    organism.kernel.start()
    main.run_bootstrap_cycle(organism)
    return organism


def _reboot(log_path: Path) -> main.Organism:
    kernel = Kernel(event_log=EventLog(path=log_path))
    organism = main.build_organism(kernel=kernel)
    main.configure_bootstrap(organism)
    organism.kernel.start()
    return organism


def _state_signature(organism: main.Organism) -> tuple:
    """A comparable snapshot of every store this task's snapshotting covers."""
    return (
        [(b.belief_id, b.confidence, b.claim) for b in organism.world_model.belief_store.read_all()],
        [(o.opportunity_id, o.expected_value) for o in organism.executive.opportunity_store.read_all()],
        [(p.plan_id, p.expected_value) for p in organism.executive.plan_store.read_all()],
        len(organism.executive.decision_record_store.read_all()),
        [(b.budget_id, b.available_attention, b.available_capital) for b in organism.governor.budget_store.read_all()],
        [(a.plan_id, a.decision) for a in organism.governor.approval_log.read_all()],
        [(r.action_id, r.status, r.result) for r in organism.executor.action_log.read_all()],
        [(o.action_id, o.success, o.result) for o in organism.memory_ledger.outcome_store.read_all()],
        [(e.delta_attention, e.delta_capital) for e in organism.memory_ledger.financial_ledger.read_all()],
    )


class SnapshotCreationTests(unittest.TestCase):
    def test_snapshot_creation_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            organism = _boot_fresh(Path(tmpdir) / "events.jsonl")

            sequence = organism.kernel.create_snapshot()
            record = organism.kernel.snapshot_store.load()

            self.assertEqual(sequence, organism.kernel.event_log.latest_sequence())
            self.assertIsNotNone(record)
            self.assertEqual(record["sequence"], sequence)
            self.assertIn("world_model.beliefs", record["sources"])
            self.assertEqual(len(record["sources"]["world_model.beliefs"]), 1)


class SnapshotAssistedRestartTests(unittest.TestCase):
    def test_restart_restores_from_latest_snapshot_plus_remaining_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"
            organism = _boot_fresh(log_path)
            organism.kernel.create_snapshot()
            main.run_bootstrap_cycle(organism)  # second cycle happens after the snapshot

            rebooted = _reboot(log_path)

            self.assertEqual(_state_signature(rebooted), _state_signature(organism))

    def test_replay_after_snapshot_only_dispatches_the_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"
            organism = _boot_fresh(log_path)
            snapshot_sequence = organism.kernel.create_snapshot()
            main.run_bootstrap_cycle(organism)
            total_events = organism.kernel.event_log.latest_sequence()

            rebooted_kernel = Kernel(event_log=EventLog(path=log_path))
            dispatched: list = []
            for event_type in {event.event_type for _, event in rebooted_kernel.event_log.read_all()}:
                rebooted_kernel.register_subscriber(event_type, dispatched.append)
            rebooted_kernel.replay()

            tail_length = total_events - snapshot_sequence
            self.assertEqual(len(dispatched), tail_length)
            self.assertLess(tail_length, total_events)

    def test_snapshot_assisted_replay_matches_full_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with_snapshot_log = Path(tmpdir) / "with_snapshot.jsonl"
            without_snapshot_log = Path(tmpdir) / "without_snapshot.jsonl"

            with_snapshot = _boot_fresh(with_snapshot_log)
            with_snapshot.kernel.create_snapshot()
            main.run_bootstrap_cycle(with_snapshot)

            without_snapshot = _boot_fresh(without_snapshot_log)
            main.run_bootstrap_cycle(without_snapshot)

            rebooted_with_snapshot = _reboot(with_snapshot_log)
            rebooted_without_snapshot = _reboot(without_snapshot_log)

            self.assertEqual(_state_signature(rebooted_with_snapshot), _state_signature(rebooted_without_snapshot))

    def test_multiple_restarts_remain_deterministic_with_a_snapshot_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "events.jsonl"
            organism = _boot_fresh(log_path)
            organism.kernel.create_snapshot()
            main.run_bootstrap_cycle(organism)

            second = _reboot(log_path)
            third = _reboot(log_path)

            self.assertEqual(_state_signature(second), _state_signature(third))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests**

Run: `python -m unittest tests.test_snapshot -v`
Expected: `OK` (5 tests) — if `test_replay_after_snapshot_only_dispatches_the_tail` fails, check that Task 5's `replay()` change actually calls `_restore_latest_snapshot()` before the dispatch loop, and that `read_from(start_sequence)` — not `read_all()` — is what feeds it.

- [ ] **Step 3: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: `OK`, 186 pre-existing tests + all tests added in Tasks 1, 3, 4, 5, 7 (unittest discovers `test_snapshot.py` automatically since it matches the `test_*.py` pattern already used by every other file in `spawn/tests/`).

- [ ] **Step 4: Commit**

```bash
git add spawn/tests/test_snapshot.py
git commit -m "test: prove snapshot-assisted replay matches full replay and stays deterministic"
```

---

## Self-Review

**Spec coverage** — every bullet in Task #19's requirements maps to a task above:
- "Kernel owns snapshot creation and loading" → Tasks 3 & 5 (`register_snapshot_source`, `create_snapshot`, `_restore_latest_snapshot` are all `Kernel` methods).
- "Snapshots capture the organism state required to resume replay efficiently" → Task 6 (the 10 event-sourced stores).
- "EventLog remains append-only" → `SnapshotStore` never touches `EventLog`; `EventLog.append`/`_load_existing` are unmodified.
- "Replay restores the latest snapshot first, then replays only subsequent events" → Task 5's `replay()` rewrite + Task 7's tail-dispatch-count test.
- "Snapshot loading is deterministic" → Task 7's multiple-restart determinism test.
- "Snapshotting must not change component ownership or introduce cross-store access" → every `register_snapshot_source` call in Task 6 closes over exactly one component's own store; the Kernel only ever sees opaque dataclass instances via reflection, never a field it interprets for business meaning.
- "Existing replay semantics remain unchanged" → Task 5's `test_replay_with_no_snapshot_dispatches_every_event` regression pin + the full `test_replay.py` suite staying green throughout.
- All 5 required tests → Task 7 (`test_snapshot_creation_succeeds`, `test_restart_restores_from_latest_snapshot_plus_remaining_log`, `test_snapshot_assisted_replay_matches_full_replay`, `test_multiple_restarts_remain_deterministic_with_a_snapshot_present`, and the full-suite run proving the pre-existing 186 tests still pass).

**Placeholder scan** — no TBD/TODO, every step has literal code, no "similar to Task N" hand-waving.

**Type consistency** — `register_snapshot_source(name, item_cls, capture, restore)` signature is identical across every call site in Task 6; `SnapshotCapture`/`SnapshotRestore` aliases match; `_encode_dataclass_fields`/`_decode_dataclass` names match between Task 2's definition and Tasks 4/5's usage.
