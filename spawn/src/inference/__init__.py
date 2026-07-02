"""Inference Port: uniform, provider-agnostic access to stateless judgment.

Any component may call InferencePort.infer() directly and synchronously — this
is the one exception to the kernel-events-only communication rule, since
judgment requests are stateless. The port never knows which provider (Claude,
GPT, Gemini, local, mock) is behind the active slot; providers are swappable
config, not architecture.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from uuid import uuid4

from src.events import EventType, InferenceCompletedEvent, InferenceRequestedEvent
from src.kernel import Kernel

MOCK_PROVIDER_CONFIDENCE = 0.5


@dataclass(slots=True, kw_only=True, frozen=True)
class InferenceRequest:
    """A stateless request for judgment from an interchangeable provider."""

    request_id: str
    requester: str
    purpose: str
    context: dict[str, str]
    constraints: tuple[str, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True, kw_only=True, frozen=True)
class InferenceResponse:
    """The provider's answer to a single InferenceRequest."""

    response_id: str
    request_id: str
    provider_name: str
    output: str
    confidence: float
    latency_ms: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InferenceProvider(ABC):
    """Uniform interface any judgment provider must implement. No implementation here."""

    @abstractmethod
    def infer(self, request: InferenceRequest) -> InferenceResponse:
        raise NotImplementedError


class MockInferenceProvider(InferenceProvider):
    """Deterministic provider for testing. Never calls an external API."""

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            response_id=str(uuid4()),
            request_id=request.request_id,
            provider_name="mock",
            output=f"mock-response:{request.purpose}",
            confidence=MOCK_PROVIDER_CONFIDENCE,
            latency_ms=0.0,
        )


class ProviderRegistry:
    """Holds registered providers by name; exactly one may be active at a time."""

    def __init__(self) -> None:
        self._providers: dict[str, InferenceProvider] = {}
        self._active_name: str | None = None

    def register(self, name: str, provider: InferenceProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> InferenceProvider:
        return self._providers[name]

    def set_active(self, name: str) -> None:
        if name not in self._providers:
            raise KeyError(name)
        self._active_name = name

    def active(self) -> InferenceProvider:
        if self._active_name is None:
            raise LookupError("no provider is active")
        return self._providers[self._active_name]

    def active_name(self) -> str | None:
        return self._active_name


class InferencePort:
    """Routes inference requests to the currently active provider and announces them."""

    def __init__(self, kernel: Kernel, registry: ProviderRegistry) -> None:
        self._kernel = kernel
        self._registry = registry

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        provider_name = self._registry.active_name() or "unknown"
        self._kernel.publish(
            InferenceRequestedEvent(
                source_component="inference_port",
                request_id=request.request_id,
                requester=request.requester,
                purpose=request.purpose,
                provider_name=provider_name,
            )
        )

        provider = self._registry.active()
        start = time.monotonic()
        response = provider.infer(request)
        elapsed_ms = (time.monotonic() - start) * 1000
        response = replace(response, latency_ms=elapsed_ms)

        self._kernel.publish(
            InferenceCompletedEvent(
                source_component="inference_port",
                request_id=request.request_id,
                response_id=response.response_id,
                provider_name=response.provider_name,
                confidence=response.confidence,
            )
        )
        return response


__all__ = [
    "InferenceRequest",
    "InferenceResponse",
    "InferenceProvider",
    "MockInferenceProvider",
    "ProviderRegistry",
    "InferencePort",
]
