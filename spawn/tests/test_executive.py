import dataclasses
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.events import (
    BeliefCreatedEvent,
    BeliefUpdatedEvent,
    Event,
    EventType,
    ExecutiveDecisionEvent,
    InferenceCompletedEvent,
    InferenceRequestedEvent,
    OpportunityGenerationCompletedEvent,
    OpportunityGenerationStartedEvent,
    OpportunityIdentifiedEvent,
    OpportunityScoredEvent,
    OutcomeRecordedEvent,
    PlanAbandonedEvent,
    PlanProposedEvent,
)
from src.executive import (
    DecisionRecord,
    DecisionRecordStore,
    Executive,
    Goal,
    GoalStore,
    Opportunity,
    OpportunityGenerationLedger,
    OpportunityGenerationRecord,
    OpportunityGenerator,
    OpportunityGroup,
    OpportunityGroupStore,
    OpportunityStore,
    Plan,
    PlanStore,
)
from src.inference import (
    InferencePort,
    InferenceProvider,
    InferenceRequest,
    InferenceResponse,
    MockInferenceProvider,
    ProviderRegistry,
)
from src.kernel import EventLog, Kernel


class ScriptedInferenceProvider(InferenceProvider):
    """Deterministic provider whose confidence is keyed by an opportunity's raw
    expected value, so a test can dictate exactly how the Inference Port scores
    each competing opportunity — including scoring a lower raw value higher.
    """

    def __init__(self, confidence_by_raw_value: dict[str, float]) -> None:
        self._confidence_by_raw_value = confidence_by_raw_value

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        confidence = self._confidence_by_raw_value[request.context["raw_expected_value"]]
        return InferenceResponse(
            response_id=str(uuid4()),
            request_id=request.request_id,
            provider_name="scripted",
            output=f"scripted:{request.purpose}",
            confidence=confidence,
            latency_ms=0.0,
        )


def _make_executive(provider: InferenceProvider | None = None) -> tuple[Kernel, Executive]:
    """Build a started Kernel with an Executive wired to an Inference Port."""
    kernel = Kernel()
    registry = ProviderRegistry()
    registry.register("provider", provider if provider is not None else MockInferenceProvider())
    registry.set_active("provider")
    port = InferencePort(kernel, registry)
    executive = Executive(kernel, inference_port=port)
    kernel.start()
    return kernel, executive


def _publish_belief(kernel: Kernel, belief_id: str, confidence: float) -> None:
    kernel.publish(
        BeliefCreatedEvent(
            source_component="world_model",
            belief_id=belief_id,
            claim=str(confidence),
            confidence=confidence,
            provenance="sensor",
        )
    )
    kernel.run_until_idle()


def _belief_of(executive: Executive, plan_id: str) -> str:
    plan = executive.plan_store.get(plan_id)
    return executive.opportunity_store.get(plan.opportunity_id).belief_ids[0]


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


class ExecutiveDeliberationTests(unittest.TestCase):
    """Integration tests for the full deliberation pipeline: rank, estimate EV
    through the Inference Port, allocate attention and capital, select one
    winning plan, and abandon the rest.
    """

    GENEROUS_ATTENTION = 1_000.0
    GENEROUS_CAPITAL = 1_000_000.0

    def test_multiple_opportunities_are_ranked_deterministically(self) -> None:
        # Raw expected value is confidence * 100; the mock provider scales
        # every estimate by a constant 0.5, so estimated value is monotonic in
        # confidence. Ranking must therefore be strictly confidence-descending.
        def run() -> tuple[str, ...]:
            kernel, executive = _make_executive()
            _publish_belief(kernel, "low", 0.3)
            _publish_belief(kernel, "high", 0.9)
            _publish_belief(kernel, "mid", 0.6)
            result = executive.deliberate(
                available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
            )
            kernel.run_until_idle()
            assert result is not None
            return tuple(_belief_of(executive, plan_id) for plan_id in result.ranked_plan_ids)

        first = run()
        second = run()
        self.assertEqual(first, ("high", "mid", "low"))
        self.assertEqual(first, second)

    def test_equal_value_opportunities_rank_fifo(self) -> None:
        kernel, executive = _make_executive()
        _publish_belief(kernel, "first", 0.5)
        _publish_belief(kernel, "second", 0.5)
        _publish_belief(kernel, "third", 0.5)

        result = executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        kernel.run_until_idle()

        assert result is not None
        # All estimates tie, so ranking falls back to proposal (FIFO) order.
        self.assertEqual(
            tuple(_belief_of(executive, plan_id) for plan_id in result.ranked_plan_ids),
            ("first", "second", "third"),
        )
        self.assertEqual(_belief_of(executive, result.winning_plan_id), "first")

    def test_ev_estimation_flows_through_the_inference_port(self) -> None:
        kernel, executive = _make_executive()
        requested: list[InferenceRequestedEvent] = []
        completed: list[InferenceCompletedEvent] = []
        kernel.register_subscriber(EventType.INFERENCE_REQUESTED, requested.append)
        kernel.register_subscriber(EventType.INFERENCE_COMPLETED, completed.append)

        _publish_belief(kernel, "a", 0.4)
        _publish_belief(kernel, "b", 0.8)
        executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        kernel.run_until_idle()

        # One inference round-trip per competing opportunity, all issued by the
        # Executive for expected-value estimation.
        self.assertEqual(len(requested), 2)
        self.assertEqual(len(completed), 2)
        self.assertTrue(all(event.requester == "executive" for event in requested))
        self.assertTrue(all(event.purpose == "estimate_expected_value" for event in requested))

    def test_inference_judgment_not_raw_value_drives_ranking(self) -> None:
        # The lower raw value (belief 0.4 -> raw 40) is judged far more
        # promising than the higher raw value (belief 0.9 -> raw 90). If EV
        # estimation truly flows through the port, the ranking must follow the
        # judgment (40 wins), not the raw formula (which would pick 90).
        provider = ScriptedInferenceProvider({"40.0": 1.0, "90.0": 0.1})
        kernel, executive = _make_executive(provider)
        _publish_belief(kernel, "raw-high", 0.9)
        _publish_belief(kernel, "raw-low", 0.4)

        result = executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        kernel.run_until_idle()

        assert result is not None
        self.assertEqual(_belief_of(executive, result.winning_plan_id), "raw-low")

    def test_attention_allocation_affects_which_plan_wins(self) -> None:
        # Two opportunities, estimated value 45 (belief 0.9) and 40 (belief
        # 0.8) under the mock's 0.5 scaling. Attention demand is 5% of estimate:
        # 2.25 vs 2.0. With ample attention the higher-value plan wins; with
        # only enough attention for the cheaper plan, the winner flips.
        def winning_belief(available_attention: float) -> str:
            kernel, executive = _make_executive()
            _publish_belief(kernel, "richer", 0.9)
            _publish_belief(kernel, "leaner", 0.8)
            result = executive.deliberate(
                available_attention=available_attention, available_capital=self.GENEROUS_CAPITAL
            )
            kernel.run_until_idle()
            assert result is not None
            return _belief_of(executive, result.winning_plan_id)

        self.assertEqual(winning_belief(self.GENEROUS_ATTENTION), "richer")
        self.assertEqual(winning_belief(2.1), "leaner")

    def test_capital_allocation_respects_the_current_budget(self) -> None:
        # Estimated values 45 and 40; capital demand is 10% of estimate: 4.5
        # vs 4.0. A budget of 4.2 cannot fund the richer plan (needs 4.5) but
        # can fund the leaner one (needs 4.0).
        kernel, executive = _make_executive()
        _publish_belief(kernel, "richer", 0.9)
        _publish_belief(kernel, "leaner", 0.8)

        result = executive.deliberate(available_attention=self.GENEROUS_ATTENTION, available_capital=4.2)
        kernel.run_until_idle()

        assert result is not None
        self.assertEqual(_belief_of(executive, result.winning_plan_id), "leaner")
        # No allocation may ever exceed the stated budget, and the total
        # capital committed across funded plans stays within it.
        total_committed = sum(a.capital_allocated for a in result.allocations)
        self.assertLessEqual(total_committed, 4.2)
        for allocation in result.allocations:
            self.assertLessEqual(allocation.capital_allocated, 4.2)
        # The unaffordable richer plan was abandoned for lack of capital.
        richer_alloc = next(
            a for a in result.allocations if _belief_of(executive, a.plan_id) == "richer"
        )
        self.assertFalse(richer_alloc.funded)

    def test_exactly_one_winning_plan_is_proposed(self) -> None:
        kernel, executive = _make_executive()
        selected: list[ExecutiveDecisionEvent] = []
        kernel.register_subscriber(EventType.PLAN_SELECTED, selected.append)

        for i, confidence in enumerate((0.3, 0.9, 0.6, 0.5)):
            _publish_belief(kernel, f"belief-{i}", confidence)
        result = executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        kernel.run_until_idle()

        assert result is not None
        self.assertIsNotNone(result.winning_plan_id)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].plan_id, result.winning_plan_id)
        # The winner is the single highest-value plan (belief 0.9).
        self.assertEqual(_belief_of(executive, result.winning_plan_id), "belief-1")

    def test_losing_plans_emit_plan_abandoned(self) -> None:
        kernel, executive = _make_executive()
        abandoned: list[PlanAbandonedEvent] = []
        kernel.register_subscriber(EventType.PLAN_ABANDONED, abandoned.append)

        for i, confidence in enumerate((0.3, 0.9, 0.6)):
            _publish_belief(kernel, f"belief-{i}", confidence)
        result = executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        kernel.run_until_idle()

        assert result is not None
        # Three candidates, one winner, two abandoned.
        self.assertEqual(len(abandoned), 2)
        self.assertEqual(len(result.abandoned_plan_ids), 2)
        self.assertNotIn(result.winning_plan_id, result.abandoned_plan_ids)
        self.assertEqual(
            {event.plan_id for event in abandoned}, set(result.abandoned_plan_ids)
        )

    def test_winning_plan_emits_executive_decision(self) -> None:
        kernel, executive = _make_executive()
        selected: list[ExecutiveDecisionEvent] = []
        kernel.register_subscriber(EventType.PLAN_SELECTED, selected.append)

        _publish_belief(kernel, "only", 0.7)
        result = executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        kernel.run_until_idle()

        assert result is not None
        self.assertEqual(len(selected), 1)
        decision_event = selected[0]
        self.assertIsInstance(decision_event, ExecutiveDecisionEvent)
        self.assertEqual(decision_event.plan_id, result.winning_plan_id)
        self.assertEqual(decision_event.event_type, EventType.PLAN_SELECTED)
        # A single-candidate deliberation commits it and abandons nothing.
        self.assertEqual(result.abandoned_plan_ids, ())
        # The commitment is recorded in the decision audit trail.
        selection_records = [
            record
            for record in executive.decision_record_store.read_all()
            if record.decision_type == "plan_selected"
        ]
        self.assertEqual(len(selection_records), 1)
        self.assertEqual(selection_records[0].subject_id, result.winning_plan_id)

    def test_deliberation_records_one_decision_per_outcome(self) -> None:
        kernel, executive = _make_executive()
        for i, confidence in enumerate((0.9, 0.6, 0.3)):
            _publish_belief(kernel, f"belief-{i}", confidence)

        executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        kernel.run_until_idle()

        outcome_records = [
            record.decision_type
            for record in executive.decision_record_store.read_all()
            if record.decision_type in ("plan_selected", "plan_abandoned")
        ]
        self.assertEqual(outcome_records.count("plan_selected"), 1)
        self.assertEqual(outcome_records.count("plan_abandoned"), 2)

    def test_deliberation_stays_proposal_only(self) -> None:
        # Even when no plan is affordable, the Executive only ever proposes —
        # it must never emit approval, budget, or execution events, and must
        # never mutate a budget of its own.
        kernel, executive = _make_executive()
        forbidden: list[Event] = []
        for event_type in (
            EventType.APPROVAL_GRANTED,
            EventType.APPROVAL_DENIED,
            EventType.APPROVAL_REQUIRED,
            EventType.BUDGET_CHECKED,
            EventType.ACTION_APPROVED,
            EventType.ACTION_ATTEMPTED,
        ):
            kernel.register_subscriber(event_type, forbidden.append)

        _publish_belief(kernel, "a", 0.9)
        _publish_belief(kernel, "b", 0.6)
        result = executive.deliberate(available_attention=0.0, available_capital=0.0)
        kernel.run_until_idle()

        assert result is not None
        self.assertEqual(forbidden, [])
        # Nothing was executable, so there is no winner and both are abandoned.
        self.assertIsNone(result.winning_plan_id)
        self.assertEqual(len(result.abandoned_plan_ids), 2)

    def test_deliberate_clears_pending_and_is_idempotent(self) -> None:
        kernel, executive = _make_executive()
        _publish_belief(kernel, "a", 0.9)
        _publish_belief(kernel, "b", 0.6)

        first = executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        kernel.run_until_idle()
        self.assertEqual(executive.pending_plan_ids(), [])

        # A second pass with nothing pending is a no-op.
        second = executive.deliberate(
            available_attention=self.GENEROUS_ATTENTION, available_capital=self.GENEROUS_CAPITAL
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_deliberate_without_inference_port_raises(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)
        kernel.start()
        _publish_belief(kernel, "a", 0.9)

        with self.assertRaises(RuntimeError):
            executive.deliberate(available_attention=10.0, available_capital=10.0)


class ExecutiveDeliberationReplayTests(unittest.TestCase):
    """Deliberation commits and abandonments are appended in response to the
    emitted PLAN_SELECTED / PLAN_ABANDONED events, so a full replay of the log
    reconstructs the same decision-record structure a live run produced —
    without re-running deliberation.
    """

    def setUp(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.log_path = Path(tmpdir.name) / "events.jsonl"

    @staticmethod
    def _build(kernel: Kernel) -> Executive:
        registry = ProviderRegistry()
        registry.register("mock", MockInferenceProvider())
        registry.set_active("mock")
        return Executive(kernel, inference_port=InferencePort(kernel, registry))

    @staticmethod
    def _decision_types(executive: Executive) -> list[str]:
        return [record.decision_type for record in executive.decision_record_store.read_all()]

    def _run_live(self) -> list[str]:
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        executive = self._build(kernel)
        kernel.start()
        for i, confidence in enumerate((0.9, 0.6, 0.3)):
            _publish_belief(kernel, f"b{i}", confidence)
        executive.deliberate(available_attention=1_000.0, available_capital=1_000_000.0)
        kernel.run_until_idle()
        kernel.stop()
        return self._decision_types(executive)

    def _replay(self) -> list[str]:
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        executive = self._build(kernel)
        kernel.replay()
        return self._decision_types(executive)

    def test_full_replay_reconstructs_deliberation_records(self) -> None:
        live = self._run_live()
        # Three competing candidates: one committed, two abandoned.
        self.assertEqual(live.count("plan_selected"), 1)
        self.assertEqual(live.count("plan_abandoned"), 2)

        replayed = self._replay()
        self.assertEqual(replayed, live)

    def test_replay_is_deterministic_across_restarts(self) -> None:
        self._run_live()

        self.assertEqual(self._replay(), self._replay())


class OpportunityGroupModelTests(unittest.TestCase):
    def test_opportunity_group_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        group = OpportunityGroup(
            group_id="group-1",
            signature="sig-1",
            belief_ids=("belief-1", "belief-2"),
            aggregated_confidence=0.65,
            created_at=now,
        )

        self.assertEqual(group.group_id, "group-1")
        self.assertEqual(group.signature, "sig-1")
        self.assertEqual(group.belief_ids, ("belief-1", "belief-2"))
        self.assertEqual(group.aggregated_confidence, 0.65)
        self.assertEqual(group.created_at, now)

    def test_opportunity_group_is_immutable(self) -> None:
        group = OpportunityGroup(
            group_id="group-1",
            signature="sig-1",
            belief_ids=("belief-1",),
            aggregated_confidence=0.5,
            created_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            group.aggregated_confidence = 0.9  # type: ignore[misc]


class OpportunityGroupStoreTests(unittest.TestCase):
    def test_append_and_read_all(self) -> None:
        store = OpportunityGroupStore()
        group = OpportunityGroup(
            group_id="group-1", signature="sig-1", belief_ids=("belief-1",), aggregated_confidence=0.5
        )

        store.append(group)

        self.assertEqual(store.read_all(), [group])


class OpportunityGenerationLedgerTests(unittest.TestCase):
    def test_append_read_all_and_history_for(self) -> None:
        ledger = OpportunityGenerationLedger()
        started = OpportunityGenerationRecord(
            generation_id="gen-1",
            status="started",
            signature="sig-1",
            belief_ids=("belief-1",),
            started_at=datetime.now(timezone.utc),
        )
        completed = OpportunityGenerationRecord(
            generation_id="gen-1",
            status="completed",
            signature="sig-1",
            belief_ids=("belief-1",),
            started_at=started.started_at,
            completed_at=datetime.now(timezone.utc),
            accepted=True,
            reason="novel aggregated situation",
            group_id="group-1",
            opportunity_id="opportunity-1",
        )

        ledger.append(started)
        ledger.append(completed)

        self.assertEqual(ledger.read_all(), [started, completed])
        self.assertEqual(ledger.history_for("gen-1"), [started, completed])
        self.assertEqual(ledger.history_for("unknown"), [])


class OpportunityGeneratorTests(unittest.TestCase):
    """Unit tests for the stateless aggregation/novelty computation."""

    def setUp(self) -> None:
        self.generator = OpportunityGenerator()

    def test_aggregate_confidence_is_the_mean(self) -> None:
        self.assertEqual(self.generator.aggregate_confidence([0.4, 0.8]), 0.6)

    def test_decide_accepts_a_brand_new_signature(self) -> None:
        accepted, reason = self.generator.decide(
            belief_ids=("a",), previously_generated_belief_ids=None, already_resolved=False
        )

        self.assertTrue(accepted)
        self.assertIn("novel", reason)

    def test_decide_rejects_an_identical_cluster_already_generated(self) -> None:
        accepted, reason = self.generator.decide(
            belief_ids=("a", "b"), previously_generated_belief_ids=("a", "b"), already_resolved=False
        )

        self.assertFalse(accepted)
        self.assertIn("duplicate", reason)

    def test_decide_accepts_a_grown_cluster_not_yet_resolved(self) -> None:
        accepted, reason = self.generator.decide(
            belief_ids=("a", "b"), previously_generated_belief_ids=("a",), already_resolved=False
        )

        self.assertTrue(accepted)

    def test_decide_rejects_a_resolved_signature_even_if_the_cluster_grew(self) -> None:
        accepted, reason = self.generator.decide(
            belief_ids=("a", "b"), previously_generated_belief_ids=("a",), already_resolved=True
        )

        self.assertFalse(accepted)
        self.assertIn("not novel", reason)


def _publish_related_beliefs(
    kernel: Kernel, signals: list[tuple[str, float]], correlation_id, claim: str = "shared-situation"
) -> None:
    """Queue several belief signals about the same claim, sharing one signature,
    without draining between them, so a single run_until_idle() processes them
    as one batch — exercising real aggregation rather than isolated
    one-at-a-time pipelines. A signature is (correlation_id, claim): sharing
    just a correlation_id is not enough (see the decay-sweep note on
    `Executive._register_belief_signal`), so related beliefs must also agree
    on the claim they corroborate.
    """
    for belief_id, confidence in signals:
        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id=belief_id,
                claim=claim,
                confidence=confidence,
                provenance="sensor",
                correlation_id=correlation_id,
            )
        )


class ExecutiveOpportunityAggregationTests(unittest.TestCase):
    def test_multiple_related_beliefs_produce_a_single_aggregated_opportunity(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)
        kernel.start()
        correlation_id = uuid4()

        _publish_related_beliefs(kernel, [("a", 0.4), ("b", 0.8)], correlation_id)
        kernel.run_until_idle()

        opportunities = executive.opportunity_store.read_all()
        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].belief_ids, ("a", "b"))
        self.assertAlmostEqual(opportunities[0].confidence, 0.6)
        self.assertEqual(len(executive.plan_store.read_all()), 1)
        self.assertEqual(executive.pending_plan_ids(), [executive.plan_store.read_all()[0].plan_id])

    def test_aggregation_is_independent_of_arrival_order(self) -> None:
        def run(order: list[tuple[str, float]]) -> Opportunity:
            kernel = Kernel()
            executive = Executive(kernel)
            kernel.start()
            _publish_related_beliefs(kernel, order, uuid4())
            kernel.run_until_idle()
            opportunities = executive.opportunity_store.read_all()
            self.assertEqual(len(opportunities), 1)
            return opportunities[0]

        forward = run([("a", 0.4), ("b", 0.8)])
        backward = run([("b", 0.8), ("a", 0.4)])

        self.assertEqual(forward.belief_ids, backward.belief_ids)
        self.assertEqual(forward.confidence, backward.confidence)
        self.assertEqual(forward.expected_value, backward.expected_value)

    def test_a_shared_correlation_id_alone_does_not_relate_unrelated_beliefs(self) -> None:
        # World Model's apply_decay() sweeps every belief in one call, publishing
        # a BeliefUpdatedEvent per belief with no drain in between; once the
        # Kernel is started those all share one active correlation_id purely as
        # an artifact of being dispatched in the same batch. Two genuinely
        # unrelated beliefs (different claims) must not be folded into one
        # opportunity just because that batch-sweep coincidence put them under
        # the same correlation_id.
        kernel = Kernel()
        executive = Executive(kernel)
        kernel.start()
        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="sensor:1",
                claim="5.2",
                confidence=0.5,
                provenance="s1",
                correlation_id=uuid4(),
            )
        )
        kernel.run_until_idle()
        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="sensor:2",
                claim="9.9",
                confidence=0.5,
                provenance="s2",
                correlation_id=uuid4(),
            )
        )
        kernel.run_until_idle()
        baseline_opportunity_count = len(executive.opportunity_store.read_all())

        decay_correlation_id = uuid4()
        kernel.publish(
            BeliefUpdatedEvent(
                source_component="world_model",
                belief_id="sensor:1",
                previous_confidence=0.5,
                new_confidence=0.49,
                provenance="s1",
                correlation_id=decay_correlation_id,
            )
        )
        kernel.publish(
            BeliefUpdatedEvent(
                source_component="world_model",
                belief_id="sensor:2",
                previous_confidence=0.5,
                new_confidence=0.48,
                provenance="s2",
                correlation_id=decay_correlation_id,
            )
        )
        kernel.run_until_idle()

        new_opportunities = executive.opportunity_store.read_all()[baseline_opportunity_count:]
        self.assertEqual(len(new_opportunities), 2)
        self.assertEqual({o.belief_ids for o in new_opportunities}, {("sensor:1",), ("sensor:2",)})

    def test_a_belief_re_signatured_twice_within_one_batch_does_not_crash(self) -> None:
        # If the same belief_id is re-signatured twice before either pending
        # generation pass is processed, the first pass's signature is left
        # with zero members (they all moved to the second signature) by the
        # time it runs — aggregate_confidence must handle that gracefully
        # instead of dividing by zero over an empty belief cluster.
        kernel = Kernel()
        executive = Executive(kernel)
        kernel.start()

        kernel.publish(
            BeliefUpdatedEvent(
                source_component="world_model",
                belief_id="a",
                previous_confidence=0.4,
                new_confidence=0.4,
                provenance="sensor",
                correlation_id=uuid4(),
            )
        )
        kernel.publish(
            BeliefUpdatedEvent(
                source_component="world_model",
                belief_id="a",
                previous_confidence=0.4,
                new_confidence=0.6,
                provenance="sensor",
                correlation_id=uuid4(),
            )
        )

        kernel.run_until_idle()

        stale = [
            record
            for record in executive.opportunity_generation_ledger.read_all()
            if record.status == "completed" and record.reason.startswith("stale")
        ]
        self.assertEqual(len(stale), 1)
        self.assertEqual(len(executive.opportunity_store.read_all()), 1)

    def test_unrelated_beliefs_produce_separate_opportunities(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)
        kernel.start()

        _publish_related_beliefs(kernel, [("a", 0.4)], uuid4())
        _publish_related_beliefs(kernel, [("b", 0.8)], uuid4())
        kernel.run_until_idle()

        opportunities = executive.opportunity_store.read_all()
        self.assertEqual(len(opportunities), 2)
        self.assertEqual({o.belief_ids for o in opportunities}, {("a",), ("b",)})

    def test_duplicate_generation_for_an_identical_cluster_is_rejected(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)
        correlation_id = uuid4()

        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="a",
                claim="0.4",
                confidence=0.4,
                provenance="sensor",
                correlation_id=correlation_id,
            )
        )
        # Re-publishing the identical belief cluster under the same signature
        # must not mint a second opportunity for the same situation.
        kernel.publish(
            BeliefUpdatedEvent(
                source_component="world_model",
                belief_id="a",
                previous_confidence=0.4,
                new_confidence=0.4,
                provenance="sensor",
                correlation_id=correlation_id,
            )
        )

        self.assertEqual(len(executive.opportunity_store.read_all()), 1)
        rejected = [
            record
            for record in executive.opportunity_generation_ledger.read_all()
            if record.status == "completed" and not record.accepted
        ]
        self.assertEqual(len(rejected), 1)
        self.assertIn("duplicate", rejected[0].reason)

    def test_previously_seen_situations_are_rejected_by_novelty_detection(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)
        correlation_id = uuid4()

        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="a",
                claim="market-signal",
                confidence=0.4,
                provenance="sensor",
                correlation_id=correlation_id,
            )
        )
        plan_id = executive.plan_store.read_all()[0].plan_id

        # Memory records an outcome for that plan — the sole sanctioned path
        # through which Executive learns a situation was already resolved.
        kernel.publish(
            OutcomeRecordedEvent(
                source_component="memory_ledger",
                outcome_id=str(uuid4()),
                action_id="action-1",
                plan_id=plan_id,
                success=True,
                result="done",
            )
        )

        # The same signature recurs with a new corroborating belief; without
        # novelty detection this would be accepted as a grown cluster.
        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="c",
                claim="market-signal",
                confidence=0.7,
                provenance="sensor",
                correlation_id=correlation_id,
            )
        )

        self.assertEqual(len(executive.opportunity_store.read_all()), 1)
        rejected = [
            record
            for record in executive.opportunity_generation_ledger.read_all()
            if record.status == "completed" and not record.accepted
        ]
        self.assertEqual(len(rejected), 1)
        self.assertIn("not novel", rejected[0].reason)


class OpportunityGenerationReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.log_path = Path(tmpdir.name) / "events.jsonl"

    def _run_live(self) -> Executive:
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        executive = Executive(kernel)
        kernel.start()
        _publish_related_beliefs(kernel, [("a", 0.4), ("b", 0.8)], uuid4())
        kernel.run_until_idle()
        kernel.stop()
        return executive

    def _replay(self) -> Executive:
        kernel = Kernel(event_log=EventLog(path=self.log_path))
        executive = Executive(kernel)
        kernel.replay()
        return executive

    def test_replay_reconstructs_opportunity_generation(self) -> None:
        live = self._run_live()
        replayed = self._replay()

        self.assertEqual(
            [g.belief_ids for g in replayed.opportunity_group_store.read_all()],
            [g.belief_ids for g in live.opportunity_group_store.read_all()],
        )
        self.assertEqual(
            [(r.status, r.accepted) for r in replayed.opportunity_generation_ledger.read_all()],
            [(r.status, r.accepted) for r in live.opportunity_generation_ledger.read_all()],
        )
        self.assertEqual(len(replayed.opportunity_store.read_all()), 1)
        self.assertEqual(replayed.opportunity_store.read_all()[0].belief_ids, ("a", "b"))

    def test_replay_is_deterministic_across_restarts(self) -> None:
        self._run_live()

        first = self._replay()
        second = self._replay()
        self.assertEqual(
            [g.belief_ids for g in first.opportunity_group_store.read_all()],
            [g.belief_ids for g in second.opportunity_group_store.read_all()],
        )


class OpportunityGenerationSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_opportunity_generation_state(self) -> None:
        kernel = Kernel()
        executive = Executive(kernel)
        correlation_id = uuid4()

        kernel.publish(
            BeliefCreatedEvent(
                source_component="world_model",
                belief_id="a",
                claim="0.4",
                confidence=0.4,
                provenance="sensor",
                correlation_id=correlation_id,
            )
        )
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_executive = Executive(rebuilt_kernel)
        rebuilt_kernel.replay()

        self.assertEqual(len(rebuilt_executive.opportunity_store.read_all()), 1)
        restored_opportunity = rebuilt_executive.opportunity_store.read_all()[0]
        self.assertEqual(restored_opportunity.belief_ids, ("a",))
        self.assertEqual(
            [g.belief_ids for g in rebuilt_executive.opportunity_group_store.read_all()],
            [("a",)],
        )

        # Duplicate detection must survive the snapshot boundary: re-observing
        # the identical belief cluster after restore is still rejected.
        rebuilt_kernel.publish(
            BeliefUpdatedEvent(
                source_component="world_model",
                belief_id="a",
                previous_confidence=0.4,
                new_confidence=0.4,
                provenance="sensor",
                correlation_id=correlation_id,
            )
        )

        self.assertEqual(len(rebuilt_executive.opportunity_store.read_all()), 1)
        rejected = [
            record
            for record in rebuilt_executive.opportunity_generation_ledger.read_all()
            if record.status == "completed" and not record.accepted
        ]
        self.assertEqual(len(rejected), 1)
        self.assertIn("duplicate", rejected[0].reason)


if __name__ == "__main__":
    unittest.main()
