import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import (
    BeliefCreatedEvent,
    BeliefUpdatedEvent,
    Event,
    EventType,
    OpportunityIdentifiedEvent,
    OpportunityScoredEvent,
    PlanProposedEvent,
)
from src.executive import (
    DecisionRecord,
    DecisionRecordStore,
    Executive,
    Goal,
    GoalStore,
    Opportunity,
    OpportunityStore,
    Plan,
    PlanStore,
)
from src.kernel import Kernel


class GoalModelTests(unittest.TestCase):
    def test_goal_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        goal = Goal(
            goal_id="goal-1",
            description="Grow capital",
            priority=1,
            parent_goal_id=None,
            created_at=now,
        )

        self.assertEqual(goal.goal_id, "goal-1")
        self.assertEqual(goal.description, "Grow capital")
        self.assertEqual(goal.priority, 1)
        self.assertIsNone(goal.parent_goal_id)
        self.assertEqual(goal.created_at, now)

    def test_goal_is_immutable(self) -> None:
        goal = Goal(
            goal_id="goal-1",
            description="Grow capital",
            priority=1,
            parent_goal_id=None,
            created_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            goal.priority = 2  # type: ignore[misc]


class OpportunityModelTests(unittest.TestCase):
    def test_opportunity_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        opportunity = Opportunity(
            opportunity_id="opportunity-1",
            belief_ids=("belief-1", "belief-2"),
            expected_value=60.0,
            confidence=0.6,
            created_at=now,
        )

        self.assertEqual(opportunity.opportunity_id, "opportunity-1")
        self.assertEqual(opportunity.belief_ids, ("belief-1", "belief-2"))
        self.assertEqual(opportunity.expected_value, 60.0)
        self.assertEqual(opportunity.confidence, 0.6)
        self.assertEqual(opportunity.created_at, now)

    def test_opportunity_is_immutable(self) -> None:
        opportunity = Opportunity(
            opportunity_id="opportunity-1",
            belief_ids=("belief-1",),
            expected_value=60.0,
            confidence=0.6,
            created_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            opportunity.expected_value = 1.0  # type: ignore[misc]


class PlanModelTests(unittest.TestCase):
    def test_plan_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        plan = Plan(
            plan_id="plan-1",
            opportunity_id="opportunity-1",
            ordered_actions=("investigate:opportunity-1", "act_on:opportunity-1"),
            expected_value=60.0,
            attention_cost=1.0,
            capital_cost=6.0,
            created_at=now,
        )

        self.assertEqual(plan.plan_id, "plan-1")
        self.assertEqual(plan.opportunity_id, "opportunity-1")
        self.assertEqual(plan.ordered_actions, ("investigate:opportunity-1", "act_on:opportunity-1"))
        self.assertEqual(plan.expected_value, 60.0)
        self.assertEqual(plan.attention_cost, 1.0)
        self.assertEqual(plan.capital_cost, 6.0)
        self.assertEqual(plan.created_at, now)

    def test_plan_is_immutable(self) -> None:
        plan = Plan(
            plan_id="plan-1",
            opportunity_id="opportunity-1",
            ordered_actions=("investigate:opportunity-1",),
            expected_value=60.0,
            attention_cost=1.0,
            capital_cost=6.0,
            created_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.capital_cost = 0.0  # type: ignore[misc]


class GoalStoreTests(unittest.TestCase):
    def test_append_and_get_round_trip(self) -> None:
        store = GoalStore()
        goal = Goal(
            goal_id="goal-1",
            description="Grow capital",
            priority=1,
            parent_goal_id=None,
            created_at=datetime.now(timezone.utc),
        )

        store.append(goal)

        self.assertEqual(store.get("goal-1"), goal)
        self.assertEqual(store.read_all(), [goal])

    def test_get_raises_for_unknown_goal(self) -> None:
        store = GoalStore()

        with self.assertRaises(KeyError):
            store.get("unknown")


class OpportunityStoreTests(unittest.TestCase):
    def test_append_and_get_round_trip(self) -> None:
        store = OpportunityStore()
        opportunity = Opportunity(
            opportunity_id="opportunity-1",
            belief_ids=("belief-1",),
            expected_value=60.0,
            confidence=0.6,
            created_at=datetime.now(timezone.utc),
        )

        store.append(opportunity)

        self.assertEqual(store.get("opportunity-1"), opportunity)
        self.assertEqual(store.read_all(), [opportunity])

    def test_get_raises_for_unknown_opportunity(self) -> None:
        store = OpportunityStore()

        with self.assertRaises(KeyError):
            store.get("unknown")


class PlanStoreTests(unittest.TestCase):
    def test_append_and_get_round_trip(self) -> None:
        store = PlanStore()
        plan = Plan(
            plan_id="plan-1",
            opportunity_id="opportunity-1",
            ordered_actions=("investigate:opportunity-1",),
            expected_value=60.0,
            attention_cost=1.0,
            capital_cost=6.0,
            created_at=datetime.now(timezone.utc),
        )

        store.append(plan)

        self.assertEqual(store.get("plan-1"), plan)
        self.assertEqual(store.read_all(), [plan])

    def test_get_raises_for_unknown_plan(self) -> None:
        store = PlanStore()

        with self.assertRaises(KeyError):
            store.get("unknown")


class DecisionRecordStoreTests(unittest.TestCase):
    def test_append_and_read_all(self) -> None:
        store = DecisionRecordStore()
        record = DecisionRecord(
            decision_id="decision-1",
            decision_type="opportunity_identified",
            subject_id="opportunity-1",
            rationale="belief-1 observed",
            created_at=datetime.now(timezone.utc),
        )

        store.append(record)

        self.assertEqual(store.read_all(), [record])
        self.assertEqual(store.get("decision-1"), record)

    def test_get_raises_for_unknown_decision(self) -> None:
        store = DecisionRecordStore()

        with self.assertRaises(KeyError):
            store.get("unknown")


class ExecutiveBeliefCreatedPipelineTests(unittest.TestCase):
    def test_belief_created_generates_opportunity_scores_it_and_proposes_plan(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)

        identified: list[Event] = []
        scored: list[Event] = []
        proposed: list[Event] = []
        kernel.register_subscriber(EventType.OPPORTUNITY_IDENTIFIED, identified.append)
        kernel.register_subscriber(EventType.OPPORTUNITY_SCORED, scored.append)
        kernel.register_subscriber(EventType.PLAN_PROPOSED, proposed.append)

        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="belief-1",
                claim="0.5",
                confidence=0.6,
                provenance="sensor-1",
            )
        )

        # Opportunity created and stored
        opportunities = executive.opportunity_store.read_all()
        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.belief_ids, ("belief-1",))
        self.assertEqual(opportunity.confidence, 0.6)
        self.assertGreater(opportunity.expected_value, 0.0)

        # OpportunityIdentified published
        self.assertEqual(len(identified), 1)
        identified_event = identified[0]
        self.assertIsInstance(identified_event, OpportunityIdentifiedEvent)
        self.assertEqual(identified_event.opportunity_id, opportunity.opportunity_id)
        self.assertEqual(identified_event.belief_ids, ("belief-1",))
        self.assertEqual(identified_event.confidence, 0.6)

        # OpportunityScored published
        self.assertEqual(len(scored), 1)
        scored_event = scored[0]
        self.assertIsInstance(scored_event, OpportunityScoredEvent)
        self.assertEqual(scored_event.opportunity_id, opportunity.opportunity_id)
        self.assertEqual(scored_event.expected_value, opportunity.expected_value)
        self.assertEqual(scored_event.confidence, 0.6)

        # Plan created and stored
        plans = executive.plan_store.read_all()
        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan.opportunity_id, opportunity.opportunity_id)
        self.assertEqual(plan.expected_value, opportunity.expected_value)
        self.assertGreater(len(plan.ordered_actions), 0)
        self.assertGreaterEqual(plan.attention_cost, 0.0)
        self.assertGreaterEqual(plan.capital_cost, 0.0)

        # PlanProposed published
        self.assertEqual(len(proposed), 1)
        proposed_event = proposed[0]
        self.assertIsInstance(proposed_event, PlanProposedEvent)
        self.assertEqual(proposed_event.plan_id, plan.plan_id)
        self.assertEqual(proposed_event.opportunity_id, opportunity.opportunity_id)

        # Every step recorded a decision
        decisions = executive.decision_record_store.read_all()
        self.assertEqual(len(decisions), 3)
        self.assertEqual(
            [decision.decision_type for decision in decisions],
            ["opportunity_identified", "opportunity_scored", "plan_proposed"],
        )
        self.assertEqual(decisions[0].subject_id, opportunity.opportunity_id)
        self.assertEqual(decisions[1].subject_id, opportunity.opportunity_id)
        self.assertEqual(decisions[2].subject_id, plan.plan_id)

    def test_belief_updated_also_triggers_pipeline(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)

        kernel.publish(
            BeliefUpdatedEvent(
                source_component="world_model",
                belief_id="belief-1",
                previous_confidence=0.4,
                new_confidence=0.8,
                provenance="sensor-1",
            )
        )

        opportunities = executive.opportunity_store.read_all()
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].confidence, 0.8)
        self.assertEqual(len(executive.plan_store.read_all()), 1)
        self.assertEqual(len(executive.decision_record_store.read_all()), 3)

    def test_each_belief_event_produces_a_separate_opportunity_and_plan(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)

        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="belief-1",
                claim="0.5",
                confidence=0.5,
                provenance="sensor-1",
            )
        )
        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="belief-2",
                claim="0.9",
                confidence=0.9,
                provenance="sensor-2",
            )
        )

        self.assertEqual(len(executive.opportunity_store.read_all()), 2)
        self.assertEqual(len(executive.plan_store.read_all()), 2)
        self.assertEqual(len(executive.decision_record_store.read_all()), 6)

    def test_executive_does_not_approve_or_execute(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)

        self.assertFalse(hasattr(executive, "approve"))
        self.assertFalse(hasattr(executive, "execute"))


if __name__ == "__main__":
    unittest.main()
