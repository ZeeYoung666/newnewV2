# Aether Roadmap

Status: LIVING · amend freely, no Charter ceremony required.
Answers "in what order," not "what" (Charter.md) or "how it's structured" (Architecture.md).

---

## Milestone board (existing, unchanged)

1. Autonomous experiment — DONE
2. Real-world evidence gathered — DONE
3. First Breath — ACTIVE
   Pass: a single command starts one exploration cycle; the complete cognitive pipeline (research → observation → belief → opportunity → plan → Governor approval → execution → outcome) executes end to end; the operator observes every significant state transition live through the Observatory. Task D (`Executive.deliberate()` integration) remains deferred, non-blocking.
4. Economic Exploration — ACTIVE
   Pass: Aether autonomously produces a ranked list of venture hypotheses (EV, startup cost, barriers, confidence, rationale) from its own research, no human-selected venture or industry, every entry traceable to research events.
5. First revenue through the full decision chain
6. Full decision chain explanation
7. Autonomous reinvestment

## Standing rule (post-1.0)

Every new implementation must either connect Aether to reality or improve an existing real-world feedback loop.

## Build sequence — Economic Exploration

0. **Research governance** — Governor spend category for information acquisition: budget, max searches per deliberation, max depth, hard stop conditions. ROI accounting lands in Memory & Ledger, not Governor.
1. **Research intent events** — Executive emits ResearchIntentEvent. Cold start derives first intents from objective inside Executive. Schema defined here.
2. **Research sensor** — Perception adapter fulfilling intents via inference port, emits ResearchObservationEvent. Never invents directions.
3. **Niche belief schema** — World Model belief types: TAM, barriers, startup cost, competition density. Schema only.
4. **Opportunity generation upgrade** — cluster niche beliefs into venture hypotheses carrying EV, cost, confidence, rationale. Base: 2adc1ca aggregator.
5. **Economic Exploration harness** — dumps ranked venture list with rationale chain. Pass criteria per milestone 3.

## Pre-flight (before Task #0)

- Real pytest run. 431 is a static count, never executed. Green run required.

## Task #0 — done

Governor now enforces a `research` spend category before any research
sensor exists. Research limits (`research_budget` with a rolling window,
`max_searches_per_deliberation`, `max_search_depth`) are declared as
constitution rules — the same `RuleRegistry`/`Constitution` mechanism that
already gated `max_capital_cost`/`max_attention_cost` — so a future change
to any research limit goes through the existing amendment path
(`propose_amendment`/`approve_amendment`), with no new mechanism. A new
`ResearchSpendRequestedEvent` gates on category + estimated cost, never on
a concrete event type, so it is callable by a future ResearchIntentEvent
fulfillment (Task #1) without the Governor knowing that event's schema.
Governor tracks its own rolling-window `ResearchSpendLedger` (never reads
Memory & Ledger's store); Memory & Ledger separately records approved
research spend per `correlation_id` from `ResearchSpendApprovedEvent`, so a
later EV computation can net out acquisition cost. Every recorded entry
carries `estimate_only: bool = True` — as of Task #0 no
ResearchObservationEvent exists to report actual spend, so cost is always
the Governor-approved estimate. `ResearchSpendLedger.estimate_only_records()`
gives Task #2 a direct query target: reconciling actuals means flipping
these records, not silently trusting them as final. New tests added (rule
breaches, budget window, snapshot round-trip, estimate-only marker); full
suite green: 455 passed, 4 subtests passed. Commit: `c093b91` (core),
`bc9cf16` (Charter.md tracked), `e67a682` (estimate_only marker).

## Task #1 — done

Executive now owns `ResearchIntentEvent` (query, estimated_cost,
search_depth, priority, rationale, request_id) — the concrete schema
Task #0's gate deliberately stayed blind to. Before emitting one, Executive
publishes `ResearchSpendRequestedEvent` and waits for the Governor's async
`ResearchSpendApprovedEvent`/`ResearchSpendDeniedEvent` (matched by
request_id via a `PendingResearchIntent` correlation map, never a new
store); on denial it records a `research_intent_denied` DecisionRecord and
never emits the intent. Cold start: with zero prior beliefs, Executive
seeds 3 fixed, industry-agnostic queries derived from Charter §2 (e.g.
"emerging profitable online business models 2026") on `KERNEL_STARTED` —
these discover the venture *space*, they don't select *within* it (Charter
§4/§6), so they don't count as a human-selected venture or industry.
Soft stop (Executive's own call, distinct from Task #0's hard caps): a
sliding window of `SOFT_STOP_WINDOW_SEARCHES` (5) searches closes with a
novel-opportunity rate; below `SOFT_STOP_MIN_NOVEL_RATE` (0.2), further
requests are refused with a `research_soft_stopped` decision record until
revisited — no Charter/Architecture amendment needed to retune this.
Competing research candidates are ranked priority-descending (FIFO
tie-break), mirroring `deliberate()`'s ranking shape rather than a second
ranking mechanism; Task #0's hard caps still decide what actually clears.

One correctness fix load-bearing for replay: `request_id` is derived
deterministically (`sha256(deliberation_id:query:search_depth)`) rather
than `uuid4()`, because `_on_kernel_started` (and any future event-driven
caller of `request_research`) re-fires identically on every replay of its
triggering event — a random id would differ from the one already baked
into the historical `ResearchSpendApprovedEvent`/`DeniedEvent`, breaking
the correlation lookup on replay. New tests added (cold start, gate
approve/deny, soft stop, priority ranking, replay determinism); full suite
green: 466 passed, 4 subtests passed. Commit: `681c63d`.

**Ambiguity resolved, not guessed**: cold-start seed queries, their fixed
priorities, and the soft-stop window/threshold numbers are stated
constants in `src/executive/__init__.py`, chosen as reasonable defaults
per the task's "do not over-engineer" instruction — revisable later
without Charter/Architecture ceremony, same as Task #0's research budget
numbers.

## Deferred

- Phase 2 knowledge graph — until revenue demonstrated.
- Generic actuators (deploy, publish, list, move money) — after milestone 3, before milestone 4.
