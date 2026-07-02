import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import Event, EventType
from src.inference import (
    InferencePort,
    InferenceProvider,
    InferenceRequest,
    InferenceResponse,
    MockInferenceProvider,
    ProviderRegistry,
)
from src.kernel import Kernel


def make_request(
    *,
    request_id: str = "request-1",
    requester: str = "executive",
    purpose: str = "score_opportunity",
    context: dict[str, str] | None = None,
    constraints: tuple[str, ...] = (),
) -> InferenceRequest:
    return InferenceRequest(
        request_id=request_id,
        requester=requester,
        purpose=purpose,
        context=context or {"belief": "0.5"},
        constraints=constraints,
    )


class InferenceRequestModelTests(unittest.TestCase):
    def test_request_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        request = InferenceRequest(
            request_id="request-1",
            requester="executive",
            purpose="score_opportunity",
            context={"belief": "0.5"},
            constraints=("max_tokens:100",),
            created_at=now,
        )

        self.assertEqual(request.request_id, "request-1")
        self.assertEqual(request.requester, "executive")
        self.assertEqual(request.purpose, "score_opportunity")
        self.assertEqual(request.context, {"belief": "0.5"})
        self.assertEqual(request.constraints, ("max_tokens:100",))
        self.assertEqual(request.created_at, now)

    def test_request_is_immutable(self) -> None:
        request = make_request()

        with self.assertRaises(dataclasses.FrozenInstanceError):
            request.purpose = "other"  # type: ignore[misc]


class InferenceResponseModelTests(unittest.TestCase):
    def test_response_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        response = InferenceResponse(
            response_id="response-1",
            request_id="request-1",
            provider_name="mock",
            output="answer",
            confidence=0.5,
            latency_ms=1.2,
            created_at=now,
        )

        self.assertEqual(response.response_id, "response-1")
        self.assertEqual(response.request_id, "request-1")
        self.assertEqual(response.provider_name, "mock")
        self.assertEqual(response.output, "answer")
        self.assertEqual(response.confidence, 0.5)
        self.assertEqual(response.latency_ms, 1.2)
        self.assertEqual(response.created_at, now)

    def test_response_is_immutable(self) -> None:
        response = InferenceResponse(
            response_id="response-1",
            request_id="request-1",
            provider_name="mock",
            output="answer",
            confidence=0.5,
            latency_ms=1.2,
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            response.output = "other"  # type: ignore[misc]


class InferenceProviderInterfaceTests(unittest.TestCase):
    def test_provider_is_abstract_and_cannot_be_instantiated_directly(self) -> None:
        with self.assertRaises(TypeError):
            InferenceProvider()  # type: ignore[abstract]

    def test_subclass_missing_infer_cannot_be_instantiated(self) -> None:
        class IncompleteProvider(InferenceProvider):
            pass

        with self.assertRaises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]


class MockInferenceProviderTests(unittest.TestCase):
    def test_returns_deterministic_response_for_the_same_request_shape(self) -> None:
        provider = MockInferenceProvider()
        request_a = make_request(request_id="request-1", purpose="score_opportunity")
        request_b = make_request(request_id="request-2", purpose="score_opportunity")

        response_a = provider.infer(request_a)
        response_b = provider.infer(request_b)

        self.assertEqual(response_a.output, response_b.output)
        self.assertEqual(response_a.confidence, response_b.confidence)
        self.assertEqual(response_a.provider_name, "mock")

    def test_response_request_id_matches_request(self) -> None:
        provider = MockInferenceProvider()
        request = make_request(request_id="request-42")

        response = provider.infer(request)

        self.assertEqual(response.request_id, "request-42")

    def test_is_an_inference_provider(self) -> None:
        provider = MockInferenceProvider()

        self.assertIsInstance(provider, InferenceProvider)


class ProviderRegistryTests(unittest.TestCase):
    def test_register_and_set_active(self) -> None:
        registry = ProviderRegistry()
        provider = MockInferenceProvider()

        registry.register("mock", provider)
        registry.set_active("mock")

        self.assertIs(registry.active(), provider)
        self.assertEqual(registry.active_name(), "mock")

    def test_set_active_raises_for_unregistered_provider(self) -> None:
        registry = ProviderRegistry()

        with self.assertRaises(KeyError):
            registry.set_active("unknown")

    def test_active_raises_when_none_set(self) -> None:
        registry = ProviderRegistry()

        with self.assertRaises(LookupError):
            registry.active()

    def test_only_one_provider_active_at_a_time(self) -> None:
        registry = ProviderRegistry()
        provider_a = MockInferenceProvider()
        provider_b = MockInferenceProvider()
        registry.register("a", provider_a)
        registry.register("b", provider_b)

        registry.set_active("a")
        self.assertIs(registry.active(), provider_a)

        registry.set_active("b")
        self.assertIs(registry.active(), provider_b)


class InferencePortTests(unittest.TestCase):
    def test_infer_routes_to_active_provider_and_returns_matching_response(self) -> None:
        kernel = Kernel()
        registry = ProviderRegistry()
        registry.register("mock", MockInferenceProvider())
        registry.set_active("mock")
        port = InferencePort(kernel, registry)

        request = make_request(request_id="request-1")
        response = port.infer(request)

        self.assertEqual(response.request_id, "request-1")
        self.assertEqual(response.provider_name, "mock")

    def test_infer_emits_inference_requested_and_inference_completed(self) -> None:
        kernel = Kernel()
        registry = ProviderRegistry()
        registry.register("mock", MockInferenceProvider())
        registry.set_active("mock")
        port = InferencePort(kernel, registry)

        requested: list[Event] = []
        completed: list[Event] = []
        kernel.register_subscriber(EventType.INFERENCE_REQUESTED, requested.append)
        kernel.register_subscriber(EventType.INFERENCE_COMPLETED, completed.append)

        request = make_request(request_id="request-1", requester="executive", purpose="score_opportunity")
        response = port.infer(request)

        self.assertEqual(len(requested), 1)
        self.assertEqual(requested[0].request_id, "request-1")
        self.assertEqual(requested[0].requester, "executive")
        self.assertEqual(requested[0].purpose, "score_opportunity")
        self.assertEqual(requested[0].provider_name, "mock")

        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].request_id, "request-1")
        self.assertEqual(completed[0].response_id, response.response_id)
        self.assertEqual(completed[0].provider_name, "mock")

    def test_provider_can_be_replaced_and_subsequent_requests_route_to_new_provider(self) -> None:
        kernel = Kernel()
        registry = ProviderRegistry()

        class NamedMockProvider(MockInferenceProvider):
            def __init__(self, name: str) -> None:
                self._name = name

            def infer(self, request: InferenceRequest) -> InferenceResponse:
                response = super().infer(request)
                return dataclasses.replace(response, provider_name=self._name)

        registry.register("first", NamedMockProvider("first"))
        registry.register("second", NamedMockProvider("second"))
        registry.set_active("first")
        port = InferencePort(kernel, registry)

        first_response = port.infer(make_request(request_id="request-1"))
        self.assertEqual(first_response.provider_name, "first")

        registry.set_active("second")
        second_response = port.infer(make_request(request_id="request-2"))
        self.assertEqual(second_response.provider_name, "second")

    def test_port_does_not_know_about_any_specific_provider(self) -> None:
        kernel = Kernel()
        registry = ProviderRegistry()
        registry.register("mock", MockInferenceProvider())
        registry.set_active("mock")
        port = InferencePort(kernel, registry)

        self.assertFalse(hasattr(port, "openai_api_key"))
        self.assertFalse(hasattr(port, "anthropic_api_key"))


if __name__ == "__main__":
    unittest.main()
