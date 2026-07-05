# Aether-class system architecture

**Status: v1.0.0, frozen.** This is the living architecture document —
kept in sync with `src/`, unlike `Architecture.pdf`/`Architecture.txt`,
which are the unedited transcript of the original design conversation and
stay historical. Where the two differ, this file is the corrected one.
Amendment process and rationale: [`docs/adr/0000-architecture-freeze-v1.0.0.md`](docs/adr/0000-architecture-freeze-v1.0.0.md).
Known gaps referenced inline below are tracked in [`docs/adr/`](docs/adr/).

## 1. Fundamental computational model

The system is a persistent stochastic control loop over durable state.
Formally: a controller for a partially observable environment (the
economy), where policy = code + accumulated knowledge + stateless judgment
calls.

Three axioms drive everything:

1. **Identity is state, not code.** The organism is its durable data:
   beliefs, goals, ledger, memories, decision records. Code and models are
   replaceable organs. Kill every process, swap every LLM provider, restart
   from disk, same organism. (Internal surrogate IDs — `action_id` and
   similar — are explicitly *not* part of this identity; see
   [ADR-0001](docs/adr/0001-replay-time-id-nondeterminism.md).)
2. **Cognition is a pure function.** `(durable state, observation) →
   (new state, proposed actions)`. LLMs are stateless evaluators invoked
   inside this function. They hold no state, own no data, make no final
   decisions.
3. **Authority must be separated.** Proposing, approving, and executing are
   different powers. Anything touching money or irreversibility passes a
   gate that the proposing component cannot bypass.

This rules out chat loops (identity dies with context), workflow engines
(task graph must be known upfront, but opportunity discovery is
open-ended), and pure reactive scripts (no belief accumulation).

## 2–4. Core components, responsibilities, data ownership

Eight units — the Kernel, seven cognitive components, and the Inference
Port infrastructure piece. Each cognitive component owns exactly one set of
stores; no shared mutable state; verified by grep across every
`src/*/__init__.py` (no component imports another component's module).

| Component | Responsibility | Owns |
|---|---|---|
| **Kernel** | Event loop, scheduling, timers, crash recovery, lifecycle | Append-only `EventLog` (disk-persisted JSONL), `Scheduler` timer table, snapshot registry |
| **Perception** | Turn external signals into normalized, timestamped observations | `SensorRegistry`, `ObservationLog`, `AdapterRegistry` (per-payload-shape normalization) |
| **World Model** | Convert observations into beliefs with confidence, provenance, decay | `BeliefStore`, `SensorReliabilityStore` (event-sourced cache of Memory & Ledger's learned reliability) |
| **Executive** | Generate opportunities, estimate expected value, allocate attention and capital, plan | `OpportunityStore`, `PlanStore`, decision records with rationale, `GoalStore` (**scaffolded, unused** — see [ADR-0004](docs/adr/0004-goal-tree-not-wired-to-attention-allocation.md)) |
| **Governor** | Enforce invariants: budgets, legality rules, approval policy, owner escalation | `ConstitutionStore`, `AmendmentLog`, `BudgetStore`, `ApprovalLog`, `EscalationStore`, `KnowledgeApplicationLedger` (advisory knowledge from the Slow Learning Loop) |
| **Executor** | Translate approved plans into tool calls, handle retries and sandboxing | `ToolRegistry`, `CredentialStore`, action log, sandbox boundary |
| **Memory & Ledger** | Record outcomes, financial ledger, distilled lessons and playbooks | Episodic memory, ledger, `HeuristicStore`, `PredictionLedger`, `LearningLedger`, `KnowledgeLedger`, `LongTermKnowledgeStore`, `SensorReliabilityLedger` |

Plus the **Inference Port**: a uniform interface any component uses to
request judgment from an interchangeable LLM provider. Providers are
config, not architecture. As of v1.0.0 it has a real caller — `Executive`
attaches it (`attach_inference_port`, `main.py`) and uses it during
deliberation for EV estimation, closing the "zero callers" gap noted at
baseline.

```
                              Kernel
                   Event bus, scheduler, recovery

    Perception                                   World model
    Signals to observations                      Beliefs with confidence

    Executive                                     Governor
    Opportunities, EV, plans                      Invariants, approvals

    Executor                                       Memory and ledger
    Tool calls, sandboxing                         Outcomes, lessons

                            Inference port
                        Swappable LLM providers
```

Teal = boundary with the world, purple = cognition and state, coral =
authority, gray = infrastructure. External world connects only through
Perception (in) and Executor (out). Owner connects only through Governor.

## 5. Communication

One mechanism: typed events on the Kernel's append-only bus. No component
calls another directly, no shared mutable state. Each component subscribes
to event types, reads only its own store, emits new events.

Verified, not just intended: every addition since baseline follows this
rule explicitly, including in its own doc comments — Governor's
`KnowledgeAdvisor` is "[p]opulated exclusively by the Governor's
`KnowledgeRevisionCompletedEvent` subscriber — never by reading Memory's
`LongTermKnowledgeStore`," and World Model's `SensorReliabilityStore` is
"[p]opulated only via `SensorReliabilityUpdatedEvent` — World Model never
reads Memory & Ledger's `SensorReliabilityLedger` directly."

Justification:

- Append-only log gives crash recovery and replay for free. Restart =
  re-read log tail (`Kernel.replay()`, run automatically and exactly once
  by `Kernel.start()` before the first `KERNEL_STARTING` event).
- Decoupling: adding a sensor or tool touches nothing else.
- Auditability: every belief, decision, and dirham movement traces to an
  event chain via `correlation_id`, populated on every publish.

Direct calls are allowed for exactly one thing: the inference port, since
judgment requests are synchronous and stateless.

## 6. What persists between cycles

Everything constituting identity: belief store, in-flight plans, decision
records with rationale, episodic memory, financial ledger, learned
heuristics, event log, tool registry, budgets, constitution — all
disk-persisted via the Kernel's `EventLog` and reconstructed on restart via
`Kernel.replay()` plus a snapshot at each Kernel-owned snapshot source. What
does not persist: LLM contexts, prompts, working computations. If it only
lives in a context window, it does not exist.

## 7. How learning changes behavior — current state

Three loops at three timescales, as designed. Status below reflects what
is actually wired, corrected from the original design conversation's
aspirational phrasing.

1. **Fast, per observation — implemented.** World Model updates belief
   confidence on each observation, weighted by
   `SensorReliabilityStore.get(sensor_id)` (`event.confidence * reliability`,
   `src/world_model/__init__.py`). Reliability itself is learned in Memory &
   Ledger's `SensorReliabilityLedger`, computed from resolved predictions,
   and propagated to World Model via `SensorReliabilityUpdatedEvent`.

2. **Medium, per outcome — partially implemented.** Every decision record
   stores a predicted value (`PredictionLedger`); Memory scores prediction
   vs. reality (`MediumLearner.compute_mean_error`,
   `compute_confidence`) and distills the result into a `Heuristic`. **This
   is where the original design's specific claim doesn't hold**: the
   Executive does not read `HeuristicStore` and has no optimism-bias
   correction of any kind — the "EV estimates run 3x optimistic, future
   estimates get discounted 3x" mechanism described in the original
   conversation was never built as a spec, let alone implemented. See
   [ADR-0003](docs/adr/0003-medium-loop-calibration-not-fed-back-to-executive.md).

3. **Slow, per pattern — implemented.** Every 3 accumulated heuristics
   (count-based trigger, not time-based — see
   [ADR-0002](docs/adr/0002-slow-learning-loop-consolidation-cadence.md)),
   `SlowLearner` consolidates them into `LongTermKnowledge` (playbooks and
   anti-patterns) via consensus confidence. The Governor's `KnowledgeAdvisor`
   consumes these: anti-patterns at or above `ANTI_PATTERN_CONFIDENCE_THRESHOLD`
   veto a plan that already cleared the Constitution and budget gates;
   playbooks at or above `PLAYBOOK_CONFIDENCE_THRESHOLD` reinforce an
   approval but never grant one on their own. Constitution and budget
   always take precedence over learned knowledge.

## 8. Why this beats common agent architectures

Unchanged from the original design — see `Architecture.txt` §8. Nothing
about the comparison to chat loops, multi-agent frameworks, workflow
engines, or microservices depends on implementation details that have
since changed.

## 9. Trade-offs and failure modes

Unchanged from the original design (`Architecture.txt` §9), with one status
update: "degenerate opportunity generation" (LLMs converging on generic
ideas) — the named mitigation was novelty penalty against episodic memory.
As of v1.0.0, `Executive`'s `OpportunityGenerator` aggregates related
beliefs into one opportunity and suppresses duplicate/stale signatures
(`src/executive/__init__.py`), which addresses the mechanical half of this
failure mode (no more one-opportunity-per-belief-update). It does not yet
check against episodic memory for genuinely novel-but-similar ideas —
that half of the original mitigation remains open, not separately tracked
by an ADR because it was never picked up as a scoped task.

## 10. Execution flow

Unchanged from the original design (`Architecture.txt` §10): Observe →
Update beliefs → Deliberate → Governor gate → Execute → Measure → Learn,
event-triggered rather than lockstep, returning to Observe continuously. A
denied plan is data and feeds the same learning loop as an executed one.

---

## Known gaps at v1.0.0

Everything below is deliberately deferred, not an oversight discovered
after the fact — each has an ADR recording the reasoning:

- [ADR-0001](docs/adr/0001-replay-time-id-nondeterminism.md) — replay
  produces different internal record IDs than the original run (accepted,
  not a defect).
- [ADR-0002](docs/adr/0002-slow-learning-loop-consolidation-cadence.md) —
  Slow Learning Loop consolidates every 3 heuristics (count), not on a
  timer (accepted).
- [ADR-0003](docs/adr/0003-medium-loop-calibration-not-fed-back-to-executive.md) —
  calibration signal computed but not consumed by Executive (open).
- [ADR-0004](docs/adr/0004-goal-tree-not-wired-to-attention-allocation.md) —
  `GoalStore` scaffolded, unused; attention allocation is static config
  (open).
- [ADR-0005](docs/adr/0005-belief-decay-not-automated-via-scheduler.md) —
  belief decay still manually invoked despite the Kernel's timer/scheduler
  existing (open).
