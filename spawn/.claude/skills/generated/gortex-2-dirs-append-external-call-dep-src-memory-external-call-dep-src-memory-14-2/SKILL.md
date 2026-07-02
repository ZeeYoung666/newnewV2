---
name: gortex-2-dirs-append-external-call-dep-src-memory-external-call-dep-src-memory-14-2
description: "Work in the . +2 dirs · append · external-call::dep:src.memory · external-call::dep:src.memory (14) #2 area — 14 symbols across 4 files (89% cohesion)"
---

# . +2 dirs · append · external-call::dep:src.memory · external-call::dep:src.memory (14) #2

14 symbols | 4 files | 89% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.memory.EpisodicMemoryEntry`
- `external-call::dep:src.memory.EpisodicMemoryStore`
- `src\memory\__init__.py`
- `tests\test_memory.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.memory.EpisodicMemoryEntry` | src.memory.EpisodicMemoryEntry |
| `external-call::dep:src.memory.EpisodicMemoryStore` | src.memory.EpisodicMemoryStore |
| `src\memory\__init__.py` | __init__, entry, EpisodicMemoryStore, EpisodicMemoryEntry, append, ... |
| `tests\test_memory.py` | EpisodicMemoryEntryModelTests, test_entry_is_immutable, test_store_has_no_mutation_methods_other_than_append, EpisodicMemoryStoreTests, test_append_and_read_all, ... |

## Connected Communities

- **. +1 dirs · now** (3 cross-edges)

## How to Explore

```
get_communities with id: "community-99"
smart_context with task: "understand . +2 dirs · append · external-call::dep:src.memory · external-call::dep:src.memory (14) #2", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
