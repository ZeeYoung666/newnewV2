# Governor Rule Engine & Owner-Approved Amendment Path — Design

Task #23. Roadmap item 11 ("Governor: real rule engine + owner-approved
amendment path"), the next item after #16/#17/#18/#19/#22 per the 7/2/26
6:31pm architecture audit and its 10:40pm update pass.

## Problem

`Governor._evaluate_policy` is a single hardcoded `if "non_negative_costs" in
constitution.rules` branch — every other string in `Constitution.rules` is
silently ignored. `adopt_constitution()` is a raw, unaudited method call: no
version history is meaningfully used, no owner-approval gate exists, and
`Constitution`/amendment state is not event-sourced, so it does not
reconstruct correctly on `Kernel.replay()` (a gap the audit called out
explicitly: "Governor's constitution/budget are supplied as boot config, not
replayed").

## Goals

1. Deterministic rule engine evaluating plans against the Constitution,
   order-independent across rule declaration order.
2. Owner-approved constitutional amendments (propose → approve/reject),
   replacing raw activation with an audited, gated flow.
3. Constitution versioning/history preserved in `ConstitutionStore`.
4. Amendment audit trail (`AmendmentLog`), append-only.
5. Governor decisions always read the active Constitution via
   `constitution_store.current()` — no separately cached "active id" that can
   desync.
6. Replay/snapshot-correct: amendment lifecycle is event-sourced so
   `Kernel.replay()` reconstructs constitutional state from the log alone.

Non-goals: budget event-sourcing (`fund_budget` stays a raw boot call, same
precedent as before — out of scope for this task), real owner escalation UI
(roadmap item 12, still pending), Executive/Executor changes, execution of
actions.

## Rule engine

`Constitution.rules` stays `tuple[str, ...]` — bootstrap config in
`main.py` and all existing tests that construct `Constitution(rules=(...))`
keep working unchanged. Parameterized rules use `"name:arg1,arg2"` syntax.

```python
RuleEvaluator = Callable[[PlanProposedEvent, tuple[str, ...]], Optional[str]]
```

`RuleRegistry` maps rule name → evaluator. Built-in rules:
- `non_negative_costs` — unchanged semantics (attention_cost/capital_cost >= 0).
- `max_capital_cost:<limit>` — new, proves parameterized rules work.
- `max_attention_cost:<limit>` — new, proves >1 rule composes.

Evaluation walks every rule string in the constitution (whatever order it's
stored in), evaluates each independently, collects **all** violations (not
first-match), and sorts them before joining into the `reason` string. Overall
pass/fail is the AND of independent per-rule predicates — this is what makes
the result provably independent of declaration order. Unknown rule names are
ignored (same behavior as today).

`Governor.__init__` accepts an optional `rule_registry: RuleRegistry` so
callers can register custom rules — same extensibility shape as Perception's
adapter registry elsewhere in this codebase.

## Amendment path

Two new lifecycle steps, both event-sourced (state mutates only inside the
subscriber handler for the event the method publishes, never inside the
public method body):

```python
def propose_amendment(self, *, rules: tuple[str, ...], justification: str) -> str: ...
def approve_amendment(self, amendment_id: str, *, approved_by: str = "owner") -> None: ...
def reject_amendment(self, amendment_id: str, *, reason: str) -> None: ...
```

New events in `src/events`:
- `ConstitutionAmendmentProposedEvent` (amendment_id, constitution_id,
  previous_constitution_id, version, rules, justification)
- `ConstitutionAmendedEvent` (amendment_id, constitution_id, version,
  approved_by)
- `ConstitutionAmendmentRejectedEvent` (amendment_id, constitution_id, reason)

Governor subscribes to all three of its own event types. `_on_amendment_proposed`
builds the candidate `Constitution`, stashes it in an in-memory pending dict,
and appends a `"proposed"` `Amendment` record to `AmendmentLog`.
`_on_amendment_approved` pops the pending candidate, appends it to
`ConstitutionStore` (this becomes the new `current()`), and appends an
`"approved"` `Amendment` record. `_on_amendment_rejected` pops the pending
candidate and appends a `"rejected"` record. Because these are ordinary
Kernel-dispatched events, replaying the log re-runs the same handlers in the
same order and rebuilds identical state — no special-cased replay code.

`adopt_constitution()` is unchanged: still a raw call, still how `main.py`
bootstraps the first constitution. This is intentional — same precedent as
`fund_budget()` — and keeps every existing caller and test working.

Governor drops the `_active_constitution_id` field entirely. Decisions read
`constitution_store.current()` directly.

## Versioning, history, snapshots

`Constitution.version` (already exists) auto-increments from
`constitution_store.current().version` (or `1` if none adopted yet) each time
`propose_amendment` is called. `ConstitutionStore` is already append-only and
keeps full history; `current()` (last-appended) is the active version.

`Amendment` (new frozen dataclass): `amendment_id`, `constitution_id`,
`previous_constitution_id`, `version`, `proposed_rules`, `justification`,
`status` (`"proposed" | "approved" | "rejected"`), `proposed_at`,
`decided_at`, `decided_by`, `reason`. `AmendmentLog` (new, append-only, same
shape as `ApprovalLog`) stores one record per lifecycle transition — never
mutates a prior record, so the full audit trail survives.

Both `ConstitutionStore` and `AmendmentLog` register as Kernel snapshot
sources (`governor.constitutions`, `governor.amendments`), matching the
existing `governor.budgets` / `governor.approvals` registrations. The
`AmendmentLog` restore callback also re-derives the in-memory pending-amendment
dict from the latest record per `amendment_id` whose status is `"proposed"`.

## Testing

- Rule engine determinism: same constitution + same plan → same verdict,
  repeated calls.
- Order independence: two constitutions with the same rule set in different
  tuple order → identical verdict and violation set.
- Amendment changes future decisions only: plan proposed under v1 evaluated
  against v1; propose v2 (not yet approved) — still evaluated against v1;
  approve v2 — subsequent plans evaluated against v2.
- Replay correctness: propose/approve/reject a sequence of amendments plus
  interleaved plan proposals against a persistent `EventLog`; rebuild a fresh
  `Kernel`/`Governor` from that log; assert identical `ConstitutionStore`,
  `AmendmentLog`, and decisions to the original run.
- Amendment audit trail preserved: full lifecycle (proposed → approved, and
  separately proposed → rejected) leaves all records queryable, none
  overwritten.
- Full suite (251 existing) still green.

## Constraints preserved

- Governor still owns policy evaluation, approval decisions, budget
  authorization exclusively; still never executes actions or touches
  Executive state.
- No cross-store access — everything above lives inside `src/governor`.
- No changes to Executive, Executor, Perception, Memory & Ledger, or the
  Kernel's public API.
