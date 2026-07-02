---
name: gortex-2-dirs-approvalrecord
description: "Work in the . +2 dirs · ApprovalRecord area — 14 symbols across 4 files (85% cohesion)"
---

# . +2 dirs · ApprovalRecord

14 symbols | 4 files | 85% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.governor.ApprovalLog`
- `external-call::dep:src.governor.ApprovalRecord`
- `src\governor\__init__.py`
- `tests\test_governor.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.governor.ApprovalLog` | src.governor.ApprovalLog |
| `external-call::dep:src.governor.ApprovalRecord` | src.governor.ApprovalRecord |
| `src\governor\__init__.py` | get, ApprovalRecord, __init__, ApprovalLog, read_all, ... |
| `tests\test_governor.py` | ApprovalRecordModelTests, test_approval_record_carries_required_fields, ApprovalLogTests, test_append_and_read_all, test_approval_record_is_immutable, ... |

## Connected Communities

- **. +1 dirs · now** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-94"
smart_context with task: "understand . +2 dirs · ApprovalRecord", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
