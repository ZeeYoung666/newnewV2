"""Frozen event model for the organism architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class EventType(str, Enum):
    """Architecture-level event types for the frozen model."""

    BELIEF_CREATED = "belief.created"
    BELIEF_UPDATED = "belief.updated"
    OPPORTUNITY_IDENTIFIED = "opportunity.identified"
    OPPORTUNITY_SCORED = "opportunity.scored"
    OPPORTUNITY_GENERATION_STARTED = "opportunity.generation_started"
    OPPORTUNITY_GENERATION_COMPLETED = "opportunity.generation_completed"
    PLAN_PROPOSED = "plan.proposed"
    PLAN_ABANDONED = "plan.abandoned"
    PLAN_SELECTED = "plan.selected"
    POLICY_EVALUATED = "policy.evaluated"
    BUDGET_CHECKED = "budget.checked"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_DENIED = "approval.denied"
    APPROVAL_REQUIRED = "approval.required"
    CONSTITUTION_AMENDMENT_PROPOSED = "constitution.amendment_proposed"
    CONSTITUTION_AMENDED = "constitution.amended"
    CONSTITUTION_AMENDMENT_REJECTED = "constitution.amendment_rejected"
    ESCALATION_CREATED = "escalation.created"
    ESCALATION_RESOLVED = "escalation.resolved"
    ACTION_APPROVED = "action.approved"
    ACTION_ATTEMPTED = "action.attempted"
    SANDBOX_EXECUTION_STARTED = "sandbox.execution_started"
    SANDBOX_EXECUTION_COMPLETED = "sandbox.execution_completed"
    ACTION_RETRY_SCHEDULED = "action.retry_scheduled"
    ACTION_RETRY_STARTED = "action.retry_started"
    ACTION_RETRY_EXHAUSTED = "action.retry_exhausted"
    CREDENTIAL_REGISTERED = "credential.registered"
    CREDENTIAL_UPDATED = "credential.updated"
    CREDENTIAL_REVOKED = "credential.revoked"
    ACTION_SUCCEEDED = "action.succeeded"
    ACTION_FAILED = "action.failed"
    OUTCOME_RECORDED = "outcome.recorded"
    PREDICTION_RECORDED = "prediction.recorded"
    PREDICTION_RESOLVED = "prediction.resolved"
    LEARNING_ITERATION_STARTED = "learning.iteration_started"
    LEARNING_ITERATION_COMPLETED = "learning.iteration_completed"
    KNOWLEDGE_REVISION_STARTED = "knowledge.revision_started"
    KNOWLEDGE_REVISION_COMPLETED = "knowledge.revision_completed"
    SENSOR_RELIABILITY_UPDATED = "sensor.reliability_updated"
    LEDGER_ENTRY_POSTED = "ledger.entry_posted"
    INFERENCE_REQUESTED = "inference.requested"
    INFERENCE_COMPLETED = "inference.completed"
    OBSERVATION_CREATED = "observation.created"
    KERNEL_STARTING = "kernel.starting"
    KERNEL_STARTED = "kernel.started"
    KERNEL_STOPPING = "kernel.stopping"
    KERNEL_STOPPED = "kernel.stopped"


@dataclass(slots=True, kw_only=True)
class Event:
    """Base event definition shared by the entire organism."""

    source_component: str
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[UUID] = None
    event_type: EventType = EventType.BELIEF_UPDATED
    event_version: int = 1


@dataclass(slots=True, kw_only=True)
class BeliefCreatedEvent(Event):
    """Represents a new belief entering the belief store."""

    belief_id: str
    claim: str
    confidence: float
    provenance: str
    event_type: EventType = EventType.BELIEF_CREATED


@dataclass(slots=True, kw_only=True)
class BeliefUpdatedEvent(Event):
    """Represents a belief-state update."""

    belief_id: str
    previous_confidence: float
    new_confidence: float
    provenance: str
    event_type: EventType = EventType.BELIEF_UPDATED


@dataclass(slots=True, kw_only=True)
class OpportunityIdentifiedEvent(Event):
    """Represents a new opportunity discovered from beliefs."""

    opportunity_id: str
    belief_ids: tuple[str, ...]
    confidence: float
    event_type: EventType = EventType.OPPORTUNITY_IDENTIFIED


@dataclass(slots=True, kw_only=True)
class OpportunityScoredEvent(Event):
    """Represents an expected-value estimate assigned to an opportunity."""

    opportunity_id: str
    expected_value: float
    confidence: float
    event_type: EventType = EventType.OPPORTUNITY_SCORED


@dataclass(slots=True, kw_only=True)
class OpportunityGenerationStartedEvent(Event):
    """Represents the Executive beginning an opportunity-generation pass for a signature."""

    generation_id: str
    signature: str
    triggering_belief_id: str
    event_type: EventType = EventType.OPPORTUNITY_GENERATION_STARTED


@dataclass(slots=True, kw_only=True)
class OpportunityGenerationCompletedEvent(Event):
    """Represents an opportunity-generation pass finishing with an aggregation and novelty decision."""

    generation_id: str
    signature: str
    belief_ids: tuple[str, ...]
    accepted: bool
    aggregated_confidence: float
    reason: str
    group_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    event_type: EventType = EventType.OPPORTUNITY_GENERATION_COMPLETED


@dataclass(slots=True, kw_only=True)
class PlanProposedEvent(Event):
    """Represents a plan created during planning."""

    plan_id: str
    opportunity_id: str
    rationale: str
    expected_value: float
    attention_cost: float
    capital_cost: float
    ordered_actions: tuple[str, ...]
    event_type: EventType = EventType.PLAN_PROPOSED


@dataclass(slots=True, kw_only=True)
class PlanAbandonedEvent(Event):
    """Represents a plan that was discarded."""

    plan_id: str
    reason: str
    event_type: EventType = EventType.PLAN_ABANDONED


@dataclass(slots=True, kw_only=True)
class ExecutiveDecisionEvent(Event):
    """Represents an executive decision to commit to a plan."""

    decision_id: str
    plan_id: str
    rationale: str
    event_type: EventType = EventType.PLAN_SELECTED


@dataclass(slots=True, kw_only=True)
class PolicyEvaluatedEvent(Event):
    """Represents the outcome of evaluating a plan against the constitution."""

    plan_id: str
    constitution_id: str
    passed: bool
    reason: str
    event_type: EventType = EventType.POLICY_EVALUATED


@dataclass(slots=True, kw_only=True)
class BudgetCheckedEvent(Event):
    """Represents the outcome of verifying a plan's cost against available budget."""

    plan_id: str
    budget_id: str
    attention_required: float
    attention_available: float
    capital_required: float
    capital_available: float
    sufficient: bool
    event_type: EventType = EventType.BUDGET_CHECKED


@dataclass(slots=True, kw_only=True)
class ApprovalGrantedEvent(Event):
    """Represents a governor approval decision that granted a plan."""

    approval_id: str
    plan_id: str
    reason: str
    ordered_actions: tuple[str, ...]
    event_type: EventType = EventType.APPROVAL_GRANTED


@dataclass(slots=True, kw_only=True)
class ApprovalDeniedEvent(Event):
    """Represents a governor approval decision that denied a plan."""

    approval_id: str
    plan_id: str
    reason: str
    event_type: EventType = EventType.APPROVAL_DENIED


@dataclass(slots=True, kw_only=True)
class ApprovalRequiredEvent(Event):
    """Represents a plan the governor could not decide on automatically; escalates to the owner."""

    plan_id: str
    reason: str
    event_type: EventType = EventType.APPROVAL_REQUIRED


@dataclass(slots=True, kw_only=True)
class ConstitutionAmendmentProposedEvent(Event):
    """Represents a candidate constitution proposed for owner approval."""

    amendment_id: str
    constitution_id: str
    previous_constitution_id: Optional[str]
    version: int
    rules: tuple[str, ...]
    justification: str
    event_type: EventType = EventType.CONSTITUTION_AMENDMENT_PROPOSED


@dataclass(slots=True, kw_only=True)
class ConstitutionAmendedEvent(Event):
    """Represents an owner-approved amendment becoming the active constitution."""

    amendment_id: str
    constitution_id: str
    version: int
    approved_by: str
    event_type: EventType = EventType.CONSTITUTION_AMENDED


@dataclass(slots=True, kw_only=True)
class ConstitutionAmendmentRejectedEvent(Event):
    """Represents an owner rejecting a proposed constitutional amendment."""

    amendment_id: str
    constitution_id: str
    reason: str
    event_type: EventType = EventType.CONSTITUTION_AMENDMENT_REJECTED


@dataclass(slots=True, kw_only=True)
class EscalationCreatedEvent(Event):
    """Represents a plan escalated to the owner for a decision the Governor could not make automatically."""

    escalation_id: str
    plan_id: str
    reason: str
    ordered_actions: tuple[str, ...]
    event_type: EventType = EventType.ESCALATION_CREATED


@dataclass(slots=True, kw_only=True)
class EscalationResolvedEvent(Event):
    """Represents an owner decision resolving a pending escalation."""

    escalation_id: str
    plan_id: str
    decision: str
    resolved_by: str
    reason: str
    event_type: EventType = EventType.ESCALATION_RESOLVED


@dataclass(slots=True, kw_only=True)
class ActionAttemptedEvent(Event):
    """Represents an execution attempt by the executor."""

    action_id: str
    tool_name: str
    attempt: int
    event_type: EventType = EventType.ACTION_ATTEMPTED


@dataclass(slots=True, kw_only=True)
class SandboxExecutionStartedEvent(Event):
    """Represents a tool invocation beginning inside the Executor's sandbox."""

    execution_id: str
    action_id: str
    action_type: str
    event_type: EventType = EventType.SANDBOX_EXECUTION_STARTED


@dataclass(slots=True, kw_only=True)
class SandboxExecutionCompletedEvent(Event):
    """Represents a sandboxed tool invocation finishing, successfully or not."""

    execution_id: str
    action_id: str
    action_type: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    event_type: EventType = EventType.SANDBOX_EXECUTION_COMPLETED


@dataclass(slots=True, kw_only=True)
class ActionRetryScheduledEvent(Event):
    """Represents a retry being queued after a retryable action failure."""

    action_id: str
    plan_id: str
    action_type: str
    attempt: int
    next_attempt: int
    error: str
    event_type: EventType = EventType.ACTION_RETRY_SCHEDULED


@dataclass(slots=True, kw_only=True)
class ActionRetryStartedEvent(Event):
    """Represents a retry attempt beginning execution."""

    action_id: str
    plan_id: str
    action_type: str
    attempt: int
    event_type: EventType = EventType.ACTION_RETRY_STARTED


@dataclass(slots=True, kw_only=True)
class ActionRetryExhaustedEvent(Event):
    """Represents an action running out of retry attempts."""

    action_id: str
    plan_id: str
    action_type: str
    attempts_made: int
    max_attempts: int
    error: str
    event_type: EventType = EventType.ACTION_RETRY_EXHAUSTED


@dataclass(slots=True, kw_only=True)
class CredentialRegisteredEvent(Event):
    """Represents a new credential becoming the active one for an action_type."""

    credential_id: str
    action_type: str
    value: str
    event_type: EventType = EventType.CREDENTIAL_REGISTERED


@dataclass(slots=True, kw_only=True)
class CredentialUpdatedEvent(Event):
    """Represents the active credential for an action_type being replaced with a new value."""

    credential_id: str
    action_type: str
    value: str
    event_type: EventType = EventType.CREDENTIAL_UPDATED


@dataclass(slots=True, kw_only=True)
class CredentialRevokedEvent(Event):
    """Represents the active credential for an action_type being revoked."""

    credential_id: str
    action_type: str
    event_type: EventType = EventType.CREDENTIAL_REVOKED


@dataclass(slots=True, kw_only=True)
class ActionApprovedEvent(Event):
    """Represents an action authorized to run as part of an approved plan."""

    action_id: str
    plan_id: str
    action_type: str
    event_type: EventType = EventType.ACTION_APPROVED


@dataclass(slots=True, kw_only=True)
class ActionSucceededEvent(Event):
    """Represents an action that completed successfully."""

    action_id: str
    plan_id: str
    result: str
    event_type: EventType = EventType.ACTION_SUCCEEDED


@dataclass(slots=True, kw_only=True)
class ActionFailedEvent(Event):
    """Represents an action that failed during execution."""

    action_id: str
    plan_id: str
    error: str
    event_type: EventType = EventType.ACTION_FAILED


@dataclass(slots=True, kw_only=True)
class OutcomeRecordedEvent(Event):
    """Represents an outcome recorded by Memory & Ledger from an action's result."""

    outcome_id: str
    action_id: str
    plan_id: str
    success: bool
    result: str
    event_type: EventType = EventType.OUTCOME_RECORDED


@dataclass(slots=True, kw_only=True)
class PredictionRecordedEvent(Event):
    """Represents a prediction recorded before execution, for later comparison against its outcome."""

    prediction_id: str
    plan_id: str
    predicted_value: float
    event_type: EventType = EventType.PREDICTION_RECORDED


@dataclass(slots=True, kw_only=True)
class PredictionResolvedEvent(Event):
    """Represents a prediction resolved against its matching outcome."""

    prediction_id: str
    plan_id: str
    outcome_id: str
    predicted_value: float
    actual_value: float
    prediction_error: float
    event_type: EventType = EventType.PREDICTION_RESOLVED


@dataclass(slots=True, kw_only=True)
class LearningIterationStartedEvent(Event):
    """Represents one Medium Learning Loop pass beginning over accumulated prediction history."""

    iteration_id: str
    predictions_considered: int
    event_type: EventType = EventType.LEARNING_ITERATION_STARTED


@dataclass(slots=True, kw_only=True)
class LearningIterationCompletedEvent(Event):
    """Represents a Medium Learning Loop pass finishing with a computed heuristic revision."""

    iteration_id: str
    predictions_considered: int
    mean_prediction_error: float
    heuristic_id: str
    event_type: EventType = EventType.LEARNING_ITERATION_COMPLETED


@dataclass(slots=True, kw_only=True)
class KnowledgeRevisionStartedEvent(Event):
    """Represents the Slow Learning Loop beginning a consolidation pass over accumulated heuristic history."""

    revision_id: str
    heuristics_considered: int
    event_type: EventType = EventType.KNOWLEDGE_REVISION_STARTED


@dataclass(slots=True, kw_only=True)
class KnowledgeRevisionCompletedEvent(Event):
    """Represents the Slow Learning Loop finishing a consolidation pass with newly distilled long-term knowledge."""

    revision_id: str
    heuristics_considered: int
    consensus_confidence: float
    knowledge_id: str
    event_type: EventType = EventType.KNOWLEDGE_REVISION_COMPLETED


@dataclass(slots=True, kw_only=True)
class SensorReliabilityUpdatedEvent(Event):
    """Represents the Fast Learning Loop revising one sensor's learned reliability."""

    sensor_id: str
    reliability: float
    predictions_considered: int
    event_type: EventType = EventType.SENSOR_RELIABILITY_UPDATED


@dataclass(slots=True, kw_only=True)
class LedgerEntryPostedEvent(Event):
    """Represents a financial ledger entry posted for an executed action."""

    entry_id: str
    action_id: str
    delta_attention: float
    delta_capital: float
    event_type: EventType = EventType.LEDGER_ENTRY_POSTED


@dataclass(slots=True, kw_only=True)
class InferenceRequestedEvent(Event):
    """Represents a judgment request sent to the inference port."""

    request_id: str
    requester: str
    purpose: str
    provider_name: str
    event_type: EventType = EventType.INFERENCE_REQUESTED


@dataclass(slots=True, kw_only=True)
class InferenceCompletedEvent(Event):
    """Represents a judgment response returned by the inference port."""

    request_id: str
    response_id: str
    provider_name: str
    confidence: float
    event_type: EventType = EventType.INFERENCE_COMPLETED


@dataclass(slots=True, kw_only=True)
class ObservationCreatedEvent(Event):
    """Represents a normalized observation accepted by perception."""

    observation_id: str
    sensor_id: str
    normalized_value: float
    confidence: float
    raw_source_type: str
    event_type: EventType = EventType.OBSERVATION_CREATED


@dataclass(slots=True, kw_only=True)
class KernelStartingEvent(Event):
    """Represents the kernel beginning startup."""

    event_type: EventType = EventType.KERNEL_STARTING


@dataclass(slots=True, kw_only=True)
class KernelStartedEvent(Event):
    """Represents the kernel entering the running state."""

    event_type: EventType = EventType.KERNEL_STARTED


@dataclass(slots=True, kw_only=True)
class KernelStoppingEvent(Event):
    """Represents the kernel beginning shutdown."""

    event_type: EventType = EventType.KERNEL_STOPPING


@dataclass(slots=True, kw_only=True)
class KernelStoppedEvent(Event):
    """Represents the kernel entering the stopped state."""

    event_type: EventType = EventType.KERNEL_STOPPED


__all__ = [
    "Event",
    "EventType",
    "BeliefCreatedEvent",
    "BeliefUpdatedEvent",
    "OpportunityIdentifiedEvent",
    "OpportunityScoredEvent",
    "OpportunityGenerationStartedEvent",
    "OpportunityGenerationCompletedEvent",
    "PlanProposedEvent",
    "PlanAbandonedEvent",
    "ExecutiveDecisionEvent",
    "PolicyEvaluatedEvent",
    "BudgetCheckedEvent",
    "ApprovalGrantedEvent",
    "ApprovalDeniedEvent",
    "ApprovalRequiredEvent",
    "ConstitutionAmendmentProposedEvent",
    "ConstitutionAmendedEvent",
    "ConstitutionAmendmentRejectedEvent",
    "EscalationCreatedEvent",
    "EscalationResolvedEvent",
    "SandboxExecutionStartedEvent",
    "SandboxExecutionCompletedEvent",
    "ActionRetryScheduledEvent",
    "ActionRetryStartedEvent",
    "ActionRetryExhaustedEvent",
    "CredentialRegisteredEvent",
    "CredentialUpdatedEvent",
    "CredentialRevokedEvent",
    "ActionApprovedEvent",
    "ActionAttemptedEvent",
    "ActionSucceededEvent",
    "ActionFailedEvent",
    "OutcomeRecordedEvent",
    "PredictionRecordedEvent",
    "PredictionResolvedEvent",
    "LearningIterationStartedEvent",
    "LearningIterationCompletedEvent",
    "KnowledgeRevisionStartedEvent",
    "KnowledgeRevisionCompletedEvent",
    "SensorReliabilityUpdatedEvent",
    "LedgerEntryPostedEvent",
    "InferenceRequestedEvent",
    "InferenceCompletedEvent",
    "ObservationCreatedEvent",
    "KernelStartingEvent",
    "KernelStartedEvent",
    "KernelStoppingEvent",
    "KernelStoppedEvent",
]
