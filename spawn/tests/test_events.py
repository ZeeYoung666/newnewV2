import unittest

from src.events import (
    ActionApprovedEvent,
    ActionAttemptedEvent,
    ActionFailedEvent,
    ActionSucceededEvent,
    ApprovalDeniedEvent,
    ApprovalGrantedEvent,
    ApprovalRequiredEvent,
    BeliefCreatedEvent,
    BeliefUpdatedEvent,
    BudgetCheckedEvent,
    Event,
    EventType,
    ExecutiveDecisionEvent,
    InferenceCompletedEvent,
    InferenceRequestedEvent,
    LedgerEntryPostedEvent,
    ObservationCreatedEvent,
    OpportunityIdentifiedEvent,
    OpportunityScoredEvent,
    OutcomeRecordedEvent,
    PlanAbandonedEvent,
    PlanProposedEvent,
    PolicyEvaluatedEvent,
)


class EventModelTests(unittest.TestCase):
    def test_core_event_models_are_importable_and_instantiable(self) -> None:
        belief_event = BeliefUpdatedEvent(
            source_component="world_model",
            belief_id="belief-1",
            previous_confidence=0.4,
            new_confidence=0.8,
            provenance="sensor-a",
        )
        planning_event = PlanProposedEvent(
            source_component="executive",
            plan_id="plan-1",
            opportunity_id="opp-1",
            rationale="high value",
            expected_value=60.0,
            attention_cost=1.0,
            capital_cost=6.0,
            ordered_actions=("investigate:opp-1", "act_on:opp-1"),
        )
        abandoned_event = PlanAbandonedEvent(
            source_component="executive",
            plan_id="plan-2",
            reason="budget constraint",
        )
        decision_event = ExecutiveDecisionEvent(
            source_component="executive",
            decision_id="decision-1",
            plan_id="plan-1",
            rationale="best option",
        )
        approval_granted_event = ApprovalGrantedEvent(
            source_component="governor",
            approval_id="approval-1",
            plan_id="plan-1",
            reason="within budget and policy",
            ordered_actions=("investigate:opp-1", "act_on:opp-1"),
        )
        approval_denied_event = ApprovalDeniedEvent(
            source_component="governor",
            approval_id="approval-2",
            plan_id="plan-2",
            reason="insufficient capital",
        )
        approval_required_event = ApprovalRequiredEvent(
            source_component="governor",
            plan_id="plan-3",
            reason="no constitution configured",
        )
        policy_evaluated_event = PolicyEvaluatedEvent(
            source_component="governor",
            plan_id="plan-1",
            constitution_id="constitution-1",
            passed=True,
            reason="all rules satisfied",
        )
        budget_checked_event = BudgetCheckedEvent(
            source_component="governor",
            plan_id="plan-1",
            budget_id="budget-1",
            attention_required=1.0,
            attention_available=10.0,
            capital_required=6.0,
            capital_available=100.0,
            sufficient=True,
        )
        execution_event = ActionAttemptedEvent(
            source_component="executor",
            action_id="action-1",
            tool_name="send_email",
            attempt=1,
        )
        action_approved_event = ActionApprovedEvent(
            source_component="executor",
            action_id="action-1",
            plan_id="plan-1",
            action_type="send_email",
        )
        action_succeeded_event = ActionSucceededEvent(
            source_component="executor",
            action_id="action-1",
            plan_id="plan-1",
            result="sent",
        )
        action_failed_event = ActionFailedEvent(
            source_component="executor",
            action_id="action-1",
            plan_id="plan-1",
            error="timeout",
        )
        outcome_recorded_event = OutcomeRecordedEvent(
            source_component="memory_ledger",
            outcome_id="outcome-1",
            action_id="action-1",
            plan_id="plan-1",
            success=True,
            result="sent",
        )
        ledger_entry_posted_event = LedgerEntryPostedEvent(
            source_component="memory_ledger",
            entry_id="entry-1",
            action_id="action-1",
            delta_attention=-1.0,
            delta_capital=-1.0,
        )
        inference_requested_event = InferenceRequestedEvent(
            source_component="inference_port",
            request_id="request-1",
            requester="executive",
            purpose="score_opportunity",
            provider_name="mock",
        )
        inference_completed_event = InferenceCompletedEvent(
            source_component="inference_port",
            request_id="request-1",
            response_id="response-1",
            provider_name="mock",
            confidence=0.5,
        )
        observation_event = ObservationCreatedEvent(
            source_component="perception",
            observation_id="observation-1",
            sensor_id="sensor-1",
            normalized_value=0.5,
            confidence=0.9,
            raw_source_type="market_feed",
        )
        belief_created_event = BeliefCreatedEvent(
            source_component="world_model",
            belief_id="belief-1",
            claim="0.5",
            confidence=0.6,
            provenance="sensor-1",
        )
        opportunity_identified_event = OpportunityIdentifiedEvent(
            source_component="executive",
            opportunity_id="opportunity-1",
            belief_ids=("belief-1",),
            confidence=0.6,
        )
        opportunity_scored_event = OpportunityScoredEvent(
            source_component="executive",
            opportunity_id="opportunity-1",
            expected_value=60.0,
            confidence=0.6,
        )

        self.assertIsInstance(belief_event, Event)
        self.assertEqual(belief_event.event_type, EventType.BELIEF_UPDATED)
        self.assertEqual(planning_event.event_type, EventType.PLAN_PROPOSED)
        self.assertEqual(abandoned_event.event_type, EventType.PLAN_ABANDONED)
        self.assertEqual(decision_event.event_type, EventType.PLAN_SELECTED)
        self.assertEqual(approval_granted_event.event_type, EventType.APPROVAL_GRANTED)
        self.assertEqual(approval_denied_event.event_type, EventType.APPROVAL_DENIED)
        self.assertEqual(approval_required_event.event_type, EventType.APPROVAL_REQUIRED)
        self.assertEqual(policy_evaluated_event.event_type, EventType.POLICY_EVALUATED)
        self.assertEqual(budget_checked_event.event_type, EventType.BUDGET_CHECKED)
        self.assertEqual(execution_event.event_type, EventType.ACTION_ATTEMPTED)
        self.assertEqual(action_approved_event.event_type, EventType.ACTION_APPROVED)
        self.assertEqual(action_succeeded_event.event_type, EventType.ACTION_SUCCEEDED)
        self.assertEqual(action_failed_event.event_type, EventType.ACTION_FAILED)
        self.assertEqual(outcome_recorded_event.event_type, EventType.OUTCOME_RECORDED)
        self.assertEqual(ledger_entry_posted_event.event_type, EventType.LEDGER_ENTRY_POSTED)
        self.assertEqual(inference_requested_event.event_type, EventType.INFERENCE_REQUESTED)
        self.assertEqual(inference_completed_event.event_type, EventType.INFERENCE_COMPLETED)
        self.assertEqual(observation_event.event_type, EventType.OBSERVATION_CREATED)
        self.assertEqual(belief_created_event.event_type, EventType.BELIEF_CREATED)
        self.assertEqual(opportunity_identified_event.event_type, EventType.OPPORTUNITY_IDENTIFIED)
        self.assertEqual(opportunity_scored_event.event_type, EventType.OPPORTUNITY_SCORED)
        self.assertEqual(belief_event.event_version, 1)
        self.assertEqual(planning_event.event_version, 1)


if __name__ == "__main__":
    unittest.main()
