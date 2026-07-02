---
name: gortex-1-dirs-src-world-model-beliefstore
description: "Work in the . +1 dirs · src.world_model.BeliefStore area — 7 symbols across 3 files (73% cohesion)"
---

# . +1 dirs · src.world_model.BeliefStore

7 symbols | 3 files | 73% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `external-call::dep:src.world_model.BeliefStore`
- `tests\test_world_model.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | dataclasses, replace |
| `external-call::dep:src.world_model.BeliefStore` | src.world_model.BeliefStore |
| `tests\test_world_model.py` | test_put_replaces_existing_belief_and_read_all_reflects_current_state, test_get_raises_for_unknown_belief, test_exists_returns_false_for_unknown_belief, BeliefStoreTests |

## Entry Points

- `tests\test_world_model.py::BeliefStoreTests.test_put_replaces_existing_belief_and_read_all_reflects_current_state`

## Connected Communities

- **. +1 dirs · now** (2 cross-edges)

## How to Explore

```
get_communities with id: "community-50"
smart_context with task: "understand . +1 dirs · src.world_model.BeliefStore", format: "gcx"
find_usages with id: "tests\test_world_model.py::BeliefStoreTests.test_put_replaces_existing_belief_and_read_all_reflects_current_state", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
