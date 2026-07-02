---
name: gortex-2-dirs-src-memory-ledgerentry
description: "Work in the . +2 dirs · src.memory.LedgerEntry area — 15 symbols across 4 files (89% cohesion)"
---

# . +2 dirs · src.memory.LedgerEntry

15 symbols | 4 files | 89% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.memory.FinancialLedger`
- `external-call::dep:src.memory.LedgerEntry`
- `src\memory\__init__.py`
- `tests\test_memory.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.memory.FinancialLedger` | src.memory.FinancialLedger |
| `external-call::dep:src.memory.LedgerEntry` | src.memory.LedgerEntry |
| `src\memory\__init__.py` | FinancialLedger, LedgerEntry, append, read_all, __init__, ... |
| `tests\test_memory.py` | LedgerEntryModelTests, test_read_all_returns_a_copy, FinancialLedgerTests, test_ledger_entry_is_immutable, test_ledger_entry_carries_required_fields, ... |

## Connected Communities

- **. +1 dirs · now** (4 cross-edges)

## How to Explore

```
get_communities with id: "community-101"
smart_context with task: "understand . +2 dirs · src.memory.LedgerEntry", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
