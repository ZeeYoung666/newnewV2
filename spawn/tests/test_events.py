import unittest

from src.events import (
    ActionAttemptedEvent,
    ApprovalGrantedEvent,
    BeliefUpdatedEvent,
    Event,
    EventType,
    ExecutiveDecisionEvent,
    PlanAbandonedEvent,
    PlanProposedEvent,
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
        approval_event = ApprovalGrantedEvent(
            source_component="governor",
            approval_id="approval-1",
            policy_id="policy-1",
            decision_id="decision-1",
        )
        execution_event = ActionAttemptedEvent(
            source_component="executor",
            action_id="action-1",
            tool_name="send_email",
            attempt=1,
        )

        self.assertIsInstance(belief_event, Event)
        self.assertEqual(belief_event.event_type, EventType.BELIEF_UPDATED)
        self.assertEqual(planning_event.event_type, EventType.PLAN_PROPOSED)
        self.assertEqual(abandoned_event.event_type, EventType.PLAN_ABANDONED)
        self.assertEqual(decision_event.event_type, EventType.PLAN_SELECTED)
        self.assertEqual(approval_event.event_type, EventType.APPROVAL_GRANTED)
        self.assertEqual(execution_event.event_type, EventType.ACTION_ATTEMPTED)
        self.assertEqual(belief_event.event_version, 1)
        self.assertEqual(planning_event.event_version, 1)


if __name__ == "__main__":
    unittest.main()
