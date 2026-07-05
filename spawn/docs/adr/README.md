# Architecture Decision Records

Records of decisions about `spawn`'s architecture — what shape it takes,
and what's deliberately deferred within that shape. Format follows Michael
Nygard's ADR pattern: Status, Context, Decision, Consequences.

| # | Title | Status |
|---|-------|--------|
| [0000](0000-architecture-freeze-v1.0.0.md) | Freeze the architecture at v1.0.0 | Accepted |
| [0001](0001-replay-time-id-nondeterminism.md) | Replay produces different internal record IDs than the original run | Accepted (not a defect) |
| [0002](0002-slow-learning-loop-consolidation-cadence.md) | Slow Learning Loop consolidation cadence is count-based, not time-based | Accepted |
| [0003](0003-medium-loop-calibration-not-fed-back-to-executive.md) | Medium Learning Loop calibration signal is not consumed by the Executive | Open / deferred |
| [0004](0004-goal-tree-not-wired-to-attention-allocation.md) | Goal tree exists as scaffolding; attention allocation is caller-supplied | Open / deferred |
| [0005](0005-belief-decay-not-automated-via-scheduler.md) | Belief decay remains manually invoked despite the Kernel now having a timer/scheduler | Open / deferred |

Per ADR-0000: any change to the component set, the event-only communication
rule, or store ownership needs a new numbered ADR here before merging.
Filling in an "Open / deferred" item above does not — it's pre-approved
backlog within the frozen shape.
