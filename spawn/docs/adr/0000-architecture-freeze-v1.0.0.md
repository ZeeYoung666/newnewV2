# ADR-0000: Freeze the architecture at v1.0.0

- Status: Accepted
- Date: 2026-07-05
- Tag: `v1.0.0`

## Context

Five audit passes (baseline 7/2 6:31pm → repass.pdf 7/2 10:40pm → three
further passes through 7/5) tracked `spawn/` against the original
first-principles design (`Architecture.pdf`). As of this tag:

- All 18 roadmap items from the baseline audit are implemented and verified
  against source (not just commit titles).
- All 8 architectural components score complete against their own
  sub-responsibility checklists.
- 431 tests pass (`pytest -q` in `spawn/`, run 2026-07-05).
- Every cross-component data flow goes through typed events on the Kernel's
  bus; no component reads another's store directly (verified by grep across
  `src/*/__init__.py` and spot-checked in the newest additions — Governor's
  `KnowledgeAdvisor` and World Model's sensor-reliability cache both carry
  explicit comments confirming they're populated only from events).

This is the point the organism described in `Architecture.pdf` is fully
built, not just scaffolded.

## Decision

Freeze the architecture as implemented at `v1.0.0`:

- The seven cognitive components (Perception, World Model, Executive,
  Governor, Executor, Memory & Ledger) plus the Kernel and Inference Port —
  no new components, no merging or splitting existing ones — without a new
  ADR.
- Event-only cross-component communication. No component may call another
  component's methods or read another component's store directly.
- Each component owns exactly one set of stores, per the original
  responsibility table (now updated in `spawn/Architecture.md` §3 to list
  every store actually implemented).

Freezing the architecture does **not** freeze feature work. Filling in a
gap within the existing shape (e.g. wiring a store that's already owned by
the right component into a decision it should influence) is normal
development. Changing the shape itself — a new component, a direct
cross-component read, a store moving owners — requires a new ADR, following
the same propose → record → accept/reject pattern the Governor already
enforces on its own Constitution (`ConstitutionAmendmentProposedEvent` →
`ConstitutionAmendedEvent` / `ConstitutionAmendmentRejectedEvent`,
`src/governor/__init__.py`).

## Consequences

- ADR-0001 through ADR-0005 are the known, deliberately deferred gaps as of
  this freeze. They are pre-approved backlog: implementing any of them fills
  in the frozen shape and does not itself require a new ADR unless the fix
  would violate one of the three points above.
- Any future PR that adds a component, a direct store read across a
  component boundary, or a new persistent store must link a new ADR in its
  description, or it should be rejected in review on architectural grounds
  alone — independent of whether the code itself is correct.
- `spawn/Architecture.md` is the living document going forward.
  `spawn/Architecture.pdf` / `Architecture.txt` remain as the historical
  record of the original design conversation and are not edited to match
  implementation drift — `Architecture.md` is.
