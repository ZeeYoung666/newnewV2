# Aether Roadmap

Status: LIVING · amend freely, no Charter ceremony required.
Answers "in what order," not "what" (Charter.md) or "how it's structured" (Architecture.md).

---

## Milestone board (existing, unchanged)

1. Autonomous experiment — DONE
2. Real-world evidence gathered — DONE
3. Economic Exploration — ACTIVE
   Pass: Aether autonomously produces a ranked list of venture hypotheses (EV, startup cost, barriers, confidence, rationale) from its own research, no human-selected venture or industry, every entry traceable to research events.
4. First revenue through the full decision chain
5. Full decision chain explanation
6. Autonomous reinvestment

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
later EV computation can net out acquisition cost. New tests added (rule
breaches, budget window, snapshot round-trip); full suite green: 453
passed, 4 subtests passed. Commit: `c093b91`.

## Deferred

- Phase 2 knowledge graph — until revenue demonstrated.
- Generic actuators (deploy, publish, list, move money) — after milestone 3, before milestone 4.
