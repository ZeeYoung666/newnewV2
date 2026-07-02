---
name: gortex-2-dirs-make-request
description: "Work in the . +2 dirs · make_request area — 53 symbols across 6 files (91% cohesion)"
---

# . +2 dirs · make_request

53 symbols | 6 files | 91% cohesion

## When to Use

Use this skill when working on files in:
- `external-call::dep:src.inference.InferencePort`
- `external-call::dep:src.inference.InferenceRequest`
- `external-call::dep:src.inference.MockInferenceProvider`
- `external-call::dep:src.inference.ProviderRegistry`
- `src\inference\__init__.py`
- `tests\test_inference.py`

## Key Files

| File | Symbols |
|------|---------|
| `external-call::dep:src.inference.InferencePort` | src.inference.InferencePort |
| `external-call::dep:src.inference.InferenceRequest` | src.inference.InferenceRequest |
| `external-call::dep:src.inference.MockInferenceProvider` | src.inference.MockInferenceProvider |
| `external-call::dep:src.inference.ProviderRegistry` | src.inference.ProviderRegistry |
| `src\inference\__init__.py` | request, __init__, InferenceProvider, ProviderRegistry, __init__, ... |
| `tests\test_inference.py` | test_request_carries_required_fields, NamedMockProvider, test_response_request_id_matches_request, test_provider_can_be_replaced_and_subsequent_requests_route_to_new_provider, test_request_is_immutable, ... |

## Entry Points

- `tests\test_inference.py::InferencePortTests.test_infer_emits_inference_requested_and_inference_completed`
- `tests\test_inference.py::InferencePortTests.test_provider_can_be_replaced_and_subsequent_requests_route_to_new_provider`
- `tests\test_inference.py::ProviderRegistryTests.test_only_one_provider_active_at_a_time`
- `tests\test_inference.py::InferencePortTests.test_port_does_not_know_about_any_specific_provider`
- `tests\test_inference.py::InferencePortTests.test_infer_routes_to_active_provider_and_returns_matching_response`

## Connected Communities

- **. +3 dirs · EventType** (4 cross-edges)
- **. +3 dirs · _on_observation_created** (1 cross-edges)
- **. +1 dirs · now** (1 cross-edges)
- **. +2 dirs · _identify_opportunity** (1 cross-edges)

## How to Explore

```
get_communities with id: "community-96"
smart_context with task: "understand . +2 dirs · make_request", format: "gcx"
find_usages with id: "tests\test_inference.py::InferencePortTests.test_infer_emits_inference_requested_and_inference_completed", format: "gcx"
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
