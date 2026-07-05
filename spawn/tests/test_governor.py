import dataclasses
import unittest
from datetime import datetime, timedelta, timezone

from src.events import (
    ApprovalDeniedEvent,
    ApprovalGrantedEvent,
    ApprovalRequiredEvent,
    BudgetCheckedEvent,
    ConstitutionAmendedEvent,
    ConstitutionAmendmentProposedEvent,
    ConstitutionAmendmentRejectedEvent,
    EscalationCreatedEvent,
    EscalationResolvedEvent,
    Event,
    EventType,
    KnowledgeAppliedEvent,
    KnowledgeIgnoredEvent,
    KnowledgeRevisionCompletedEvent,
    PlanProposedEvent,
    PolicyEvaluatedEvent,
    ResearchSpendApprovedEvent,
    ResearchSpendDeniedEvent,
    ResearchSpendRequestedEvent,
)
from src.governor import (
    ANTI_PATTERN_CONFIDENCE_THRESHOLD,
    DEFAULT_RESEARCH_BUDGET_WINDOW_SECONDS,
    PLAYBOOK_CONFIDENCE_THRESHOLD,
    Amendment,
    AmendmentLog,
    ApprovalLog,
    ApprovalRecord,
    BudgetState,
    BudgetStore,
    Constitution,
    ConstitutionStore,
    EscalationRecord,
    EscalationStore,
    Governor,
    KnowledgeAdvisor,
    KnowledgeApplicationLedger,
    KnowledgeApplicationRecord,
    LearnedKnowledge,
    ResearchRuleContext,
    ResearchSpendLedger,
    ResearchSpendRecord,
    RuleRegistry,
)
from src.kernel import EventLog, Kernel


def publish_research_spend_requested(
    kernel: Kernel,
    *,
    request_id: str = "request-1",
    deliberation_id: str = "deliberation-1",
    category: str = "research",
    estimated_cost: float = 5.0,
    search_depth: int = 1,
) -> None:
    kernel.publish(
        ResearchSpendRequestedEvent(
            source_component="executive",
            request_id=request_id,
            deliberation_id=deliberation_id,
            category=category,
            estimated_cost=estimated_cost,
            search_depth=search_depth,
        )
    )


def publish_plan_proposed(
    kernel: Kernel,
    *,
    plan_id: str = "plan-1",
    opportunity_id: str = "opportunity-1",
    expected_value: float = 60.0,
    attention_cost: float = 1.0,
    capital_cost: float = 6.0,
    ordered_actions: tuple[str, ...] = ("investigate:opportunity-1", "act_on:opportunity-1"),
) -> None:
    kernel.publish(
        PlanProposedEvent(
            source_component="executive",
            plan_id=plan_id,
            opportunity_id=opportunity_id,
            rationale="test plan",
            expected_value=expected_value,
            attention_cost=attention_cost,
            capital_cost=capital_cost,
            ordered_actions=ordered_actions,
        )
    )


def publish_knowledge_revision_completed(
    kernel: Kernel,
    *,
    revision_id: str = "revision-1",
    heuristics_considered: int = 3,
    consensus_confidence: float = 0.9,
    knowledge_id: str,
    knowledge_type: str,
    summary: str = "test knowledge",
) -> None:
    kernel.publish(
        KnowledgeRevisionCompletedEvent(
            source_component="memory_ledger",
            revision_id=revision_id,
            heuristics_considered=heuristics_considered,
            consensus_confidence=consensus_confidence,
            knowledge_id=knowledge_id,
            knowledge_type=knowledge_type,
            summary=summary,
        )
    )


class ConstitutionModelTests(unittest.TestCase):
    def test_constitution_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        constitution = Constitution(
            constitution_id="constitution-1",
            version=1,
            rules=("non_negative_costs",),
            created_at=now,
        )

        self.assertEqual(constitution.constitution_id, "constitution-1")
        self.assertEqual(constitution.version, 1)
        self.assertEqual(constitution.rules, ("non_negative_costs",))
        self.assertEqual(constitution.created_at, now)

    def test_constitution_is_immutable(self) -> None:
        constitution = Constitution(
            constitution_id="constitution-1", version=1, rules=(), created_at=datetime.now(timezone.utc)
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            constitution.version = 2  # type: ignore[misc]


class BudgetStateModelTests(unittest.TestCase):
    def test_budget_state_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        budget = BudgetState(
            budget_id="budget-1", available_attention=10.0, available_capital=100.0, updated_at=now
        )

        self.assertEqual(budget.budget_id, "budget-1")
        self.assertEqual(budget.available_attention, 10.0)
        self.assertEqual(budget.available_capital, 100.0)
        self.assertEqual(budget.updated_at, now)

    def test_budget_state_is_immutable(self) -> None:
        budget = BudgetState(
            budget_id="budget-1",
            available_attention=10.0,
            available_capital=100.0,
            updated_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            budget.available_capital = 0.0  # type: ignore[misc]


class ApprovalRecordModelTests(unittest.TestCase):
    def test_approval_record_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        record = ApprovalRecord(
            approval_id="approval-1",
            plan_id="plan-1",
            decision="approved",
            reason="within budget and policy",
            timestamp=now,
        )

        self.assertEqual(record.approval_id, "approval-1")
        self.assertEqual(record.plan_id, "plan-1")
        self.assertEqual(record.decision, "approved")
        self.assertEqual(record.reason, "within budget and policy")
        self.assertEqual(record.timestamp, now)

    def test_approval_record_is_immutable(self) -> None:
        record = ApprovalRecord(
            approval_id="approval-1",
            plan_id="plan-1",
            decision="approved",
            reason="ok",
            timestamp=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.decision = "rejected"  # type: ignore[misc]


class ConstitutionStoreTests(unittest.TestCase):
    def test_append_get_and_current(self) -> None:
        store = ConstitutionStore()
        constitution = Constitution(
            constitution_id="constitution-1", version=1, rules=(), created_at=datetime.now(timezone.utc)
        )

        store.append(constitution)

        self.assertEqual(store.get("constitution-1"), constitution)
        self.assertEqual(store.current(), constitution)
        self.assertEqual(store.read_all(), [constitution])

    def test_current_raises_when_empty(self) -> None:
        store = ConstitutionStore()

        with self.assertRaises(LookupError):
            store.current()

    def test_get_raises_for_unknown_constitution(self) -> None:
        store = ConstitutionStore()

        with self.assertRaises(KeyError):
            store.get("unknown")


class BudgetStoreTests(unittest.TestCase):
    def test_put_get_and_exists(self) -> None:
        store = BudgetStore()
        budget = BudgetState(
            budget_id="budget-1",
            available_attention=10.0,
            available_capital=100.0,
            updated_at=datetime.now(timezone.utc),
        )

        store.put(budget)

        self.assertEqual(store.get("budget-1"), budget)
        self.assertTrue(store.exists("budget-1"))
        self.assertEqual(store.read_all(), [budget])

    def test_get_raises_for_unknown_budget(self) -> None:
        store = BudgetStore()

        with self.assertRaises(KeyError):
            store.get("unknown")


class ApprovalLogTests(unittest.TestCase):
    def test_append_and_read_all(self) -> None:
        log = ApprovalLog()
        record = ApprovalRecord(
            approval_id="approval-1",
            plan_id="plan-1",
            decision="approved",
            reason="ok",
            timestamp=datetime.now(timezone.utc),
        )

        log.append(record)

        self.assertEqual(log.read_all(), [record])
        self.assertEqual(log.get("approval-1"), record)

    def test_get_raises_for_unknown_approval(self) -> None:
        log = ApprovalLog()

        with self.assertRaises(KeyError):
            log.get("unknown")


class GovernorApprovalRequiredTests(unittest.TestCase):
    def test_plan_proposed_without_constitution_or_budget_emits_approval_required(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)

        required: list[Event] = []
        granted: list[Event] = []
        denied: list[Event] = []
        policy_evaluated: list[Event] = []
        budget_checked: list[Event] = []
        kernel.register_subscriber(EventType.APPROVAL_REQUIRED, required.append)
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, granted.append)
        kernel.register_subscriber(EventType.APPROVAL_DENIED, denied.append)
        kernel.register_subscriber(EventType.POLICY_EVALUATED, policy_evaluated.append)
        kernel.register_subscriber(EventType.BUDGET_CHECKED, budget_checked.append)

        publish_plan_proposed(kernel, plan_id="plan-1")

        self.assertEqual(len(required), 1)
        self.assertIsInstance(required[0], ApprovalRequiredEvent)
        self.assertEqual(required[0].plan_id, "plan-1")
        self.assertEqual(granted, [])
        self.assertEqual(denied, [])
        self.assertEqual(policy_evaluated, [])
        self.assertEqual(budget_checked, [])
        self.assertEqual(governor.approval_log.read_all(), [])

    def test_plan_proposed_with_constitution_but_no_budget_emits_approval_required(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(
                constitution_id="constitution-1",
                version=1,
                rules=("non_negative_costs",),
                created_at=datetime.now(timezone.utc),
            )
        )

        required: list[Event] = []
        kernel.register_subscriber(EventType.APPROVAL_REQUIRED, required.append)

        publish_plan_proposed(kernel)

        self.assertEqual(len(required), 1)
        self.assertEqual(governor.approval_log.read_all(), [])


class GovernorApprovalGrantedTests(unittest.TestCase):
    def _configured_governor(self, kernel: Kernel) -> Governor:
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(
                constitution_id="constitution-1",
                version=1,
                rules=("non_negative_costs",),
                created_at=datetime.now(timezone.utc),
            )
        )
        governor.fund_budget(
            BudgetState(
                budget_id="budget-1",
                available_attention=10.0,
                available_capital=100.0,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return governor

    def test_valid_plan_within_budget_is_granted_and_reserves_budget(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)

        policy_events: list[Event] = []
        budget_events: list[Event] = []
        granted: list[Event] = []
        kernel.register_subscriber(EventType.POLICY_EVALUATED, policy_events.append)
        kernel.register_subscriber(EventType.BUDGET_CHECKED, budget_events.append)
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, granted.append)

        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=6.0)

        self.assertEqual(len(policy_events), 1)
        self.assertIsInstance(policy_events[0], PolicyEvaluatedEvent)
        self.assertTrue(policy_events[0].passed)
        self.assertEqual(policy_events[0].plan_id, "plan-1")

        self.assertEqual(len(budget_events), 1)
        self.assertIsInstance(budget_events[0], BudgetCheckedEvent)
        self.assertTrue(budget_events[0].sufficient)

        self.assertEqual(len(granted), 1)
        self.assertIsInstance(granted[0], ApprovalGrantedEvent)
        self.assertEqual(granted[0].plan_id, "plan-1")

        records = governor.approval_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].decision, "approved")
        self.assertEqual(records[0].plan_id, "plan-1")

        budget = governor.budget_store.get("budget-1")
        self.assertAlmostEqual(budget.available_attention, 9.0)
        self.assertAlmostEqual(budget.available_capital, 94.0)


class GovernorApprovalDeniedTests(unittest.TestCase):
    def _configured_governor(self, kernel: Kernel) -> Governor:
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(
                constitution_id="constitution-1",
                version=1,
                rules=("non_negative_costs",),
                created_at=datetime.now(timezone.utc),
            )
        )
        governor.fund_budget(
            BudgetState(
                budget_id="budget-1",
                available_attention=10.0,
                available_capital=100.0,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return governor

    def test_plan_violating_constitution_is_denied_without_checking_budget(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)

        policy_events: list[Event] = []
        budget_events: list[Event] = []
        denied: list[Event] = []
        kernel.register_subscriber(EventType.POLICY_EVALUATED, policy_events.append)
        kernel.register_subscriber(EventType.BUDGET_CHECKED, budget_events.append)
        kernel.register_subscriber(EventType.APPROVAL_DENIED, denied.append)

        publish_plan_proposed(kernel, plan_id="plan-1", capital_cost=-1.0)

        self.assertEqual(len(policy_events), 1)
        self.assertFalse(policy_events[0].passed)

        self.assertEqual(budget_events, [])  # short-circuited before budget check

        self.assertEqual(len(denied), 1)
        self.assertIsInstance(denied[0], ApprovalDeniedEvent)
        self.assertEqual(denied[0].plan_id, "plan-1")

        records = governor.approval_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].decision, "rejected")

        # budget untouched
        budget = governor.budget_store.get("budget-1")
        self.assertEqual(budget.available_capital, 100.0)

    def test_plan_within_policy_but_over_budget_is_denied_and_budget_untouched(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)

        budget_events: list[Event] = []
        denied: list[Event] = []
        kernel.register_subscriber(EventType.BUDGET_CHECKED, budget_events.append)
        kernel.register_subscriber(EventType.APPROVAL_DENIED, denied.append)

        publish_plan_proposed(kernel, plan_id="plan-1", capital_cost=1000.0)

        self.assertEqual(len(budget_events), 1)
        self.assertFalse(budget_events[0].sufficient)

        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0].plan_id, "plan-1")

        records = governor.approval_log.read_all()
        self.assertEqual(records[0].decision, "rejected")

        budget = governor.budget_store.get("budget-1")
        self.assertEqual(budget.available_capital, 100.0)
        self.assertEqual(budget.available_attention, 10.0)


class GovernorAuthorityBoundaryTests(unittest.TestCase):
    def test_governor_does_not_create_or_execute_plans(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)

        self.assertFalse(hasattr(governor, "create_plan"))
        self.assertFalse(hasattr(governor, "execute"))


class RuleEngineOrderIndependenceTests(unittest.TestCase):
    def _governor_with_budget(self, kernel: Kernel, rules: tuple[str, ...]) -> Governor:
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=rules)
        )
        governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )
        return governor

    def test_rule_verdict_independent_of_declaration_order(self) -> None:
        kernel_a = Kernel()
        governor_a = self._governor_with_budget(
            kernel_a, ("max_capital_cost:50", "non_negative_costs")
        )
        kernel_b = Kernel()
        governor_b = self._governor_with_budget(
            kernel_b, ("non_negative_costs", "max_capital_cost:50")
        )

        policy_a: list[Event] = []
        policy_b: list[Event] = []
        kernel_a.register_subscriber(EventType.POLICY_EVALUATED, policy_a.append)
        kernel_b.register_subscriber(EventType.POLICY_EVALUATED, policy_b.append)

        publish_plan_proposed(kernel_a, plan_id="plan-1", attention_cost=-1.0, capital_cost=100.0)
        publish_plan_proposed(kernel_b, plan_id="plan-1", attention_cost=-1.0, capital_cost=100.0)

        self.assertFalse(policy_a[0].passed)
        self.assertFalse(policy_b[0].passed)
        self.assertEqual(policy_a[0].reason, policy_b[0].reason)

        self.assertEqual(governor_a.approval_log.read_all()[0].reason, governor_b.approval_log.read_all()[0].reason)

    def test_all_rule_violations_collected_not_short_circuited(self) -> None:
        kernel = Kernel()
        governor = self._governor_with_budget(kernel, ("non_negative_costs", "max_capital_cost:50"))

        policy_events: list[Event] = []
        kernel.register_subscriber(EventType.POLICY_EVALUATED, policy_events.append)

        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=-1.0, capital_cost=100.0)

        self.assertFalse(policy_events[0].passed)
        self.assertIn("non_negative_costs", policy_events[0].reason)
        self.assertIn("max_capital_cost", policy_events[0].reason)

    def test_deterministic_repeated_evaluation(self) -> None:
        registry = RuleRegistry()
        constitution = Constitution(
            constitution_id="constitution-1", version=1, rules=("max_attention_cost:5",)
        )
        event = PlanProposedEvent(
            source_component="executive",
            plan_id="plan-1",
            opportunity_id="opportunity-1",
            rationale="test",
            expected_value=10.0,
            attention_cost=6.0,
            capital_cost=1.0,
            ordered_actions=(),
        )

        first = registry.evaluate(constitution, event)
        second = registry.evaluate(constitution, event)

        self.assertEqual(first, second)
        self.assertFalse(first[0])

    def test_custom_rule_registration(self) -> None:
        registry = RuleRegistry()
        registry.register("always_fails", lambda event, args: "custom rule fired")
        constitution = Constitution(constitution_id="constitution-1", version=1, rules=("always_fails",))
        event = PlanProposedEvent(
            source_component="executive",
            plan_id="plan-1",
            opportunity_id="opportunity-1",
            rationale="test",
            expected_value=10.0,
            attention_cost=1.0,
            capital_cost=1.0,
            ordered_actions=(),
        )

        passed, reason = registry.evaluate(constitution, event)

        self.assertFalse(passed)
        self.assertIn("custom rule fired", reason)

    def test_unknown_rule_names_are_ignored(self) -> None:
        registry = RuleRegistry()
        constitution = Constitution(constitution_id="constitution-1", version=1, rules=("no_such_rule",))
        event = PlanProposedEvent(
            source_component="executive",
            plan_id="plan-1",
            opportunity_id="opportunity-1",
            rationale="test",
            expected_value=10.0,
            attention_cost=1.0,
            capital_cost=1.0,
            ordered_actions=(),
        )

        passed, reason = registry.evaluate(constitution, event)

        self.assertTrue(passed)


class AmendmentLifecycleTests(unittest.TestCase):
    def _governor_with_v1(self, kernel: Kernel) -> Governor:
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-v1", version=1, rules=("non_negative_costs",))
        )
        governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )
        return governor

    def test_propose_amendment_does_not_activate_it(self) -> None:
        kernel = Kernel()
        governor = self._governor_with_v1(kernel)
        proposed: list[Event] = []
        kernel.register_subscriber(EventType.CONSTITUTION_AMENDMENT_PROPOSED, proposed.append)

        amendment_id = governor.propose_amendment(
            rules=("non_negative_costs", "max_capital_cost:10"), justification="tighten capital exposure"
        )

        self.assertEqual(len(proposed), 1)
        self.assertIsInstance(proposed[0], ConstitutionAmendmentProposedEvent)
        self.assertEqual(proposed[0].version, 2)
        self.assertEqual(governor.constitution_store.current().constitution_id, "constitution-v1")
        self.assertEqual(governor.constitution_store.current().version, 1)
        history = governor.amendment_log.history_for(amendment_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, "proposed")

    def test_approve_amendment_activates_new_constitution_and_bumps_version(self) -> None:
        kernel = Kernel()
        governor = self._governor_with_v1(kernel)
        approved: list[Event] = []
        kernel.register_subscriber(EventType.CONSTITUTION_AMENDED, approved.append)

        amendment_id = governor.propose_amendment(
            rules=("non_negative_costs", "max_capital_cost:10"), justification="tighten capital exposure"
        )
        governor.approve_amendment(amendment_id, approved_by="owner")

        self.assertEqual(len(approved), 1)
        self.assertIsInstance(approved[0], ConstitutionAmendedEvent)
        current = governor.constitution_store.current()
        self.assertEqual(current.version, 2)
        self.assertEqual(current.rules, ("non_negative_costs", "max_capital_cost:10"))
        history = governor.amendment_log.history_for(amendment_id)
        self.assertEqual([record.status for record in history], ["proposed", "approved"])
        self.assertEqual(history[-1].decided_by, "owner")

    def test_reject_amendment_leaves_constitution_unchanged(self) -> None:
        kernel = Kernel()
        governor = self._governor_with_v1(kernel)
        rejected: list[Event] = []
        kernel.register_subscriber(EventType.CONSTITUTION_AMENDMENT_REJECTED, rejected.append)

        amendment_id = governor.propose_amendment(rules=("max_capital_cost:1",), justification="too strict")
        governor.reject_amendment(amendment_id, reason="would block normal operation")

        self.assertEqual(len(rejected), 1)
        self.assertEqual(governor.constitution_store.current().version, 1)
        history = governor.amendment_log.history_for(amendment_id)
        self.assertEqual([record.status for record in history], ["proposed", "rejected"])
        self.assertEqual(history[-1].reason, "would block normal operation")

    def test_approving_unknown_amendment_raises_keyerror(self) -> None:
        kernel = Kernel()
        governor = self._governor_with_v1(kernel)

        with self.assertRaises(KeyError):
            governor.approve_amendment("no-such-amendment")

    def test_approving_already_decided_amendment_raises_keyerror(self) -> None:
        kernel = Kernel()
        governor = self._governor_with_v1(kernel)
        amendment_id = governor.propose_amendment(rules=("non_negative_costs",), justification="noop")
        governor.approve_amendment(amendment_id)

        with self.assertRaises(KeyError):
            governor.approve_amendment(amendment_id)

    def test_amendment_changes_future_decisions_only(self) -> None:
        kernel = Kernel()
        governor = self._governor_with_v1(kernel)
        policy_events: list[Event] = []
        kernel.register_subscriber(EventType.POLICY_EVALUATED, policy_events.append)

        # Under v1 (non_negative_costs only), a plan with capital_cost=60 passes.
        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=60.0)
        self.assertTrue(policy_events[0].passed)
        self.assertEqual(policy_events[0].constitution_id, "constitution-v1")

        amendment_id = governor.propose_amendment(
            rules=("non_negative_costs", "max_capital_cost:10"), justification="tighten capital exposure"
        )

        # Still pending: v1 remains active, same plan shape still passes.
        publish_plan_proposed(kernel, plan_id="plan-2", attention_cost=1.0, capital_cost=60.0)
        self.assertTrue(policy_events[1].passed)
        self.assertEqual(policy_events[1].constitution_id, "constitution-v1")

        governor.approve_amendment(amendment_id)

        # Now under v2, the same plan shape is denied by the new rule.
        publish_plan_proposed(kernel, plan_id="plan-3", attention_cost=1.0, capital_cost=60.0)
        self.assertFalse(policy_events[2].passed)
        self.assertNotEqual(policy_events[2].constitution_id, "constitution-v1")


class AmendmentAuditTrailTests(unittest.TestCase):
    def test_full_history_preserved_across_multiple_amendments(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-v1", version=1, rules=("non_negative_costs",))
        )

        first_id = governor.propose_amendment(rules=("non_negative_costs", "max_capital_cost:10"), justification="a")
        governor.reject_amendment(first_id, reason="too strict")
        second_id = governor.propose_amendment(rules=("non_negative_costs", "max_capital_cost:50"), justification="b")
        governor.approve_amendment(second_id)

        all_records = governor.amendment_log.read_all()
        self.assertEqual(len(all_records), 4)  # proposed+rejected, proposed+approved
        self.assertEqual(
            [record.status for record in governor.amendment_log.history_for(first_id)],
            ["proposed", "rejected"],
        )
        self.assertEqual(
            [record.status for record in governor.amendment_log.history_for(second_id)],
            ["proposed", "approved"],
        )
        # Rejection never touched the active constitution; approval did.
        self.assertEqual(governor.constitution_store.current().version, 2)
        self.assertEqual(governor.constitution_store.current().rules, ("non_negative_costs", "max_capital_cost:50"))


class GovernorReplayTests(unittest.TestCase):
    def test_replay_reconstructs_constitution_and_amendment_history(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        governor = Governor(kernel)
        v1_created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        governor.adopt_constitution(
            Constitution(
                constitution_id="constitution-v1", version=1, rules=("non_negative_costs",), created_at=v1_created_at
            )
        )
        governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )

        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=60.0)
        amendment_id = governor.propose_amendment(
            rules=("non_negative_costs", "max_capital_cost:10"), justification="tighten capital exposure"
        )
        publish_plan_proposed(kernel, plan_id="plan-2", attention_cost=1.0, capital_cost=60.0)
        governor.approve_amendment(amendment_id)
        publish_plan_proposed(kernel, plan_id="plan-3", attention_cost=1.0, capital_cost=60.0)

        second_id = governor.propose_amendment(rules=("max_capital_cost:5",), justification="never approved")

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_governor = Governor(rebuilt_kernel)
        # Bootstrap config (constitution v1, budget) is boot-time setup, not
        # event-sourced — same precedent as main.configure_bootstrap redoing
        # it on every reboot. Amendment events layered on top by replay()
        # bring the constitution the rest of the way to v2.
        rebuilt_governor.adopt_constitution(
            Constitution(
                constitution_id="constitution-v1", version=1, rules=("non_negative_costs",), created_at=v1_created_at
            )
        )
        rebuilt_governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_governor.constitution_store.read_all(), governor.constitution_store.read_all()
        )
        self.assertEqual(
            rebuilt_governor.amendment_log.read_all(), governor.amendment_log.read_all()
        )
        self.assertEqual(rebuilt_governor.constitution_store.current().version, 2)
        self.assertIn(second_id, rebuilt_governor._pending_amendments)
        self.assertEqual(
            rebuilt_governor._pending_amendments[second_id].rules, ("max_capital_cost:5",)
        )

    def test_replay_reproduces_identical_decisions_across_constitution_versions(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-v1", version=1, rules=("non_negative_costs",))
        )
        governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )

        original_policy: list[Event] = []
        original_decisions: list[Event] = []
        kernel.register_subscriber(EventType.POLICY_EVALUATED, original_policy.append)
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, original_decisions.append)
        kernel.register_subscriber(EventType.APPROVAL_DENIED, original_decisions.append)

        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=60.0)
        amendment_id = governor.propose_amendment(
            rules=("non_negative_costs", "max_capital_cost:10"), justification="tighten"
        )
        governor.approve_amendment(amendment_id)
        publish_plan_proposed(kernel, plan_id="plan-2", attention_cost=1.0, capital_cost=60.0)

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_governor = Governor(rebuilt_kernel)
        rebuilt_governor.adopt_constitution(
            Constitution(constitution_id="constitution-v1", version=1, rules=("non_negative_costs",))
        )
        rebuilt_governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )
        replayed_policy: list[Event] = []
        rebuilt_kernel.register_subscriber(EventType.POLICY_EVALUATED, replayed_policy.append)
        rebuilt_kernel.replay()

        self.assertEqual(len(replayed_policy), len(original_policy))
        for original, replayed in zip(original_policy, replayed_policy):
            self.assertEqual(original.passed, replayed.passed)
            self.assertEqual(original.constitution_id, replayed.constitution_id)
            self.assertEqual(original.reason, replayed.reason)


class EscalationRecordModelTests(unittest.TestCase):
    def test_escalation_record_carries_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        record = EscalationRecord(
            escalation_id="escalation-1",
            plan_id="plan-1",
            reason="no constitution configured",
            ordered_actions=("investigate:opportunity-1",),
            status="pending",
            created_at=now,
        )

        self.assertEqual(record.escalation_id, "escalation-1")
        self.assertEqual(record.plan_id, "plan-1")
        self.assertEqual(record.reason, "no constitution configured")
        self.assertEqual(record.ordered_actions, ("investigate:opportunity-1",))
        self.assertEqual(record.status, "pending")
        self.assertEqual(record.created_at, now)
        self.assertIsNone(record.decision)
        self.assertIsNone(record.resolved_at)
        self.assertIsNone(record.resolved_by)

    def test_escalation_record_is_immutable(self) -> None:
        record = EscalationRecord(
            escalation_id="escalation-1",
            plan_id="plan-1",
            reason="no budget configured",
            ordered_actions=(),
            status="pending",
            created_at=datetime.now(timezone.utc),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.status = "resolved"  # type: ignore[misc]


class EscalationStoreTests(unittest.TestCase):
    def test_append_read_all_and_history_for(self) -> None:
        store = EscalationStore()
        pending = EscalationRecord(
            escalation_id="escalation-1",
            plan_id="plan-1",
            reason="no budget configured",
            ordered_actions=(),
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        resolved = EscalationRecord(
            escalation_id="escalation-1",
            plan_id="plan-1",
            reason="no budget configured",
            ordered_actions=(),
            status="resolved",
            created_at=pending.created_at,
            decision="approved",
            resolved_at=datetime.now(timezone.utc),
            resolved_by="owner",
        )

        store.append(pending)
        store.append(resolved)

        self.assertEqual(store.read_all(), [pending, resolved])
        self.assertEqual(store.history_for("escalation-1"), [pending, resolved])
        self.assertEqual(store.history_for("no-such-escalation"), [])


class GovernorEscalationLifecycleTests(unittest.TestCase):
    def test_plan_without_constitution_creates_exactly_one_escalation(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        created: list[Event] = []
        kernel.register_subscriber(EventType.ESCALATION_CREATED, created.append)

        publish_plan_proposed(kernel, plan_id="plan-1")

        self.assertEqual(len(created), 1)
        self.assertIsInstance(created[0], EscalationCreatedEvent)
        self.assertEqual(created[0].plan_id, "plan-1")
        self.assertEqual(created[0].reason, "no constitution configured")

        history = governor.escalation_store.read_all()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, "pending")
        self.assertEqual(history[0].plan_id, "plan-1")

    def test_plan_without_budget_creates_exactly_one_escalation(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )
        created: list[Event] = []
        kernel.register_subscriber(EventType.ESCALATION_CREATED, created.append)

        publish_plan_proposed(kernel, plan_id="plan-1")

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].reason, "no budget configured")
        self.assertEqual(len(governor.escalation_store.read_all()), 1)

    def test_approving_escalation_resumes_normal_pipeline_and_grants_plan(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        created: list[EscalationCreatedEvent] = []
        granted: list[Event] = []
        resolved: list[Event] = []
        kernel.register_subscriber(EventType.ESCALATION_CREATED, created.append)
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, granted.append)
        kernel.register_subscriber(EventType.ESCALATION_RESOLVED, resolved.append)

        publish_plan_proposed(
            kernel, plan_id="plan-1", ordered_actions=("investigate:opportunity-1", "act_on:opportunity-1")
        )
        escalation_id = created[0].escalation_id

        governor.approve_escalation(escalation_id, approved_by="owner")

        self.assertEqual(len(resolved), 1)
        self.assertIsInstance(resolved[0], EscalationResolvedEvent)
        self.assertEqual(resolved[0].decision, "approved")

        self.assertEqual(len(granted), 1)
        self.assertIsInstance(granted[0], ApprovalGrantedEvent)
        self.assertEqual(granted[0].plan_id, "plan-1")
        self.assertEqual(granted[0].ordered_actions, ("investigate:opportunity-1", "act_on:opportunity-1"))

        records = governor.approval_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].decision, "approved")

        history = governor.escalation_store.history_for(escalation_id)
        self.assertEqual([record.status for record in history], ["pending", "resolved"])
        self.assertEqual(history[-1].decision, "approved")
        self.assertEqual(history[-1].resolved_by, "owner")
        self.assertNotIn(escalation_id, governor._pending_escalations)

    def test_denying_escalation_permanently_rejects_the_plan(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        created: list[EscalationCreatedEvent] = []
        denied: list[Event] = []
        kernel.register_subscriber(EventType.ESCALATION_CREATED, created.append)
        kernel.register_subscriber(EventType.APPROVAL_DENIED, denied.append)

        publish_plan_proposed(kernel, plan_id="plan-1")
        escalation_id = created[0].escalation_id

        governor.deny_escalation(escalation_id, reason="owner does not trust this plan")

        self.assertEqual(len(denied), 1)
        self.assertIsInstance(denied[0], ApprovalDeniedEvent)
        self.assertEqual(denied[0].plan_id, "plan-1")
        self.assertEqual(denied[0].reason, "owner does not trust this plan")

        records = governor.approval_log.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].decision, "rejected")

        history = governor.escalation_store.history_for(escalation_id)
        self.assertEqual([record.status for record in history], ["pending", "resolved"])
        self.assertEqual(history[-1].decision, "denied")

        # Denial is final: the escalation can't be resolved a second time.
        with self.assertRaises(KeyError):
            governor.approve_escalation(escalation_id)

    def test_approving_unknown_escalation_raises_keyerror(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)

        with self.assertRaises(KeyError):
            governor.approve_escalation("no-such-escalation")

    def test_denying_unknown_escalation_raises_keyerror(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)

        with self.assertRaises(KeyError):
            governor.deny_escalation("no-such-escalation", reason="n/a")


class GovernorEscalationReplayTests(unittest.TestCase):
    def test_replay_reconstructs_pending_and_resolved_escalations(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )

        created: list[EscalationCreatedEvent] = []
        kernel.register_subscriber(EventType.ESCALATION_CREATED, created.append)

        # No budget configured yet: both plans escalate.
        publish_plan_proposed(kernel, plan_id="plan-1")
        publish_plan_proposed(kernel, plan_id="plan-2")
        approved_id = created[0].escalation_id
        denied_id = created[1].escalation_id

        governor.approve_escalation(approved_id, approved_by="owner")
        governor.deny_escalation(denied_id, reason="not worth the risk")

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_governor = Governor(rebuilt_kernel)
        rebuilt_governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_governor.escalation_store.read_all(), governor.escalation_store.read_all()
        )
        self.assertEqual(rebuilt_governor._pending_escalations, {})

        approved_history = rebuilt_governor.escalation_store.history_for(approved_id)
        self.assertEqual([record.status for record in approved_history], ["pending", "resolved"])
        self.assertEqual(approved_history[-1].decision, "approved")

        denied_history = rebuilt_governor.escalation_store.history_for(denied_id)
        self.assertEqual([record.status for record in denied_history], ["pending", "resolved"])
        self.assertEqual(denied_history[-1].decision, "denied")

    def test_replay_leaves_still_pending_escalation_in_pending_dict(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        governor = Governor(kernel)

        created: list[EscalationCreatedEvent] = []
        kernel.register_subscriber(EventType.ESCALATION_CREATED, created.append)
        publish_plan_proposed(kernel, plan_id="plan-1")
        pending_id = created[0].escalation_id

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_governor = Governor(rebuilt_kernel)
        rebuilt_kernel.replay()

        self.assertIn(pending_id, rebuilt_governor._pending_escalations)
        self.assertEqual(rebuilt_governor._pending_escalations[pending_id].status, "pending")


class GovernorEscalationSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_escalation_state(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)

        created: list[EscalationCreatedEvent] = []
        kernel.register_subscriber(EventType.ESCALATION_CREATED, created.append)
        publish_plan_proposed(kernel, plan_id="plan-1")
        publish_plan_proposed(kernel, plan_id="plan-2")
        resolved_id = created[0].escalation_id
        still_pending_id = created[1].escalation_id

        governor.approve_escalation(resolved_id, approved_by="owner")
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_governor = Governor(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored = {record.escalation_id: record for record in rebuilt_governor.escalation_store.read_all()}
        self.assertEqual(restored[resolved_id].status, "resolved")
        self.assertEqual(restored[resolved_id].decision, "approved")
        self.assertEqual(restored[still_pending_id].status, "pending")
        self.assertIn(still_pending_id, rebuilt_governor._pending_escalations)
        self.assertNotIn(resolved_id, rebuilt_governor._pending_escalations)


class KnowledgeApplicationRecordModelTests(unittest.TestCase):
    def test_record_carries_required_fields(self) -> None:
        record = KnowledgeApplicationRecord(
            application_id="application-1",
            knowledge_id="knowledge-1",
            knowledge_type="playbook",
            plan_id="plan-1",
            applied=True,
            reason="playbook knowledge-1 applied",
        )

        self.assertEqual(record.application_id, "application-1")
        self.assertEqual(record.knowledge_id, "knowledge-1")
        self.assertEqual(record.knowledge_type, "playbook")
        self.assertEqual(record.plan_id, "plan-1")
        self.assertTrue(record.applied)
        self.assertEqual(record.reason, "playbook knowledge-1 applied")

    def test_record_is_immutable(self) -> None:
        record = KnowledgeApplicationRecord(
            application_id="application-1",
            knowledge_id="knowledge-1",
            knowledge_type="playbook",
            plan_id="plan-1",
            applied=True,
            reason="ok",
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.applied = False  # type: ignore[misc]


class KnowledgeApplicationLedgerTests(unittest.TestCase):
    def test_append_read_all_and_history_for(self) -> None:
        ledger = KnowledgeApplicationLedger()
        first = KnowledgeApplicationRecord(
            application_id="application-1",
            knowledge_id="knowledge-1",
            knowledge_type="playbook",
            plan_id="plan-1",
            applied=True,
            reason="ok",
        )
        second = KnowledgeApplicationRecord(
            application_id="application-2",
            knowledge_id="knowledge-2",
            knowledge_type="anti_pattern",
            plan_id="plan-2",
            applied=False,
            reason="below threshold",
        )

        ledger.append(first)
        ledger.append(second)

        self.assertEqual(ledger.read_all(), [first, second])
        self.assertEqual(ledger.history_for("plan-1"), [first])
        self.assertEqual(ledger.history_for("plan-2"), [second])
        self.assertEqual(ledger.history_for("no-such-plan"), [])

    def test_ledger_has_no_mutation_methods_other_than_append(self) -> None:
        ledger = KnowledgeApplicationLedger()

        self.assertFalse(hasattr(ledger, "update"))
        self.assertFalse(hasattr(ledger, "remove"))
        self.assertFalse(hasattr(ledger, "clear"))


class KnowledgeAdvisorTests(unittest.TestCase):
    def test_record_classifies_by_knowledge_type(self) -> None:
        advisor = KnowledgeAdvisor()
        playbook = LearnedKnowledge(
            knowledge_id="knowledge-1",
            knowledge_type="playbook",
            summary="playbook summary",
            consensus_confidence=0.9,
            heuristics_considered=3,
            learned_at=datetime.now(timezone.utc),
        )
        anti_pattern = LearnedKnowledge(
            knowledge_id="knowledge-2",
            knowledge_type="anti_pattern",
            summary="anti-pattern summary",
            consensus_confidence=0.9,
            heuristics_considered=3,
            learned_at=datetime.now(timezone.utc),
        )

        advisor.record(playbook)
        advisor.record(anti_pattern)

        self.assertEqual(advisor.playbooks(), [playbook])
        self.assertEqual(advisor.anti_patterns(), [anti_pattern])
        self.assertEqual(set(advisor.read_all()), {playbook, anti_pattern})


class GovernorKnowledgeStateTests(unittest.TestCase):
    def test_knowledge_revision_completed_updates_governor_knowledge_state(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)

        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-playbook-1",
            knowledge_type="playbook",
            consensus_confidence=0.8,
            summary="repeated successes distilled into a playbook",
        )

        playbooks = governor.knowledge_advisor.playbooks()
        self.assertEqual(len(playbooks), 1)
        self.assertEqual(playbooks[0].knowledge_id, "knowledge-playbook-1")
        self.assertEqual(playbooks[0].knowledge_type, "playbook")
        self.assertEqual(playbooks[0].consensus_confidence, 0.8)
        self.assertEqual(playbooks[0].summary, "repeated successes distilled into a playbook")
        self.assertEqual(governor.knowledge_advisor.anti_patterns(), [])

    def test_knowledge_revision_completed_never_reads_memory_store(self) -> None:
        # The Governor's KnowledgeAdvisor is populated exclusively from the
        # event's own fields; Governor carries no reference to Memory at all.
        kernel = Kernel()
        governor = Governor(kernel)

        self.assertFalse(hasattr(governor, "memory_ledger"))
        self.assertFalse(hasattr(governor, "long_term_knowledge_store"))


class GovernorKnowledgeInfluenceTests(unittest.TestCase):
    def _configured_governor(self, kernel: Kernel) -> Governor:
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )
        governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )
        return governor

    def test_learned_playbook_influences_approval_decision(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)
        applied: list[Event] = []
        granted: list[Event] = []
        kernel.register_subscriber(EventType.KNOWLEDGE_APPLIED, applied.append)
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, granted.append)

        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-playbook-1",
            knowledge_type="playbook",
            consensus_confidence=PLAYBOOK_CONFIDENCE_THRESHOLD,
            summary="proven procedure",
        )
        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=6.0)

        self.assertEqual(len(granted), 1)
        self.assertIsInstance(granted[0], ApprovalGrantedEvent)
        self.assertIn("playbook knowledge-playbook-1 applied", granted[0].reason)

        self.assertEqual(len(applied), 1)
        self.assertIsInstance(applied[0], KnowledgeAppliedEvent)
        self.assertEqual(applied[0].knowledge_id, "knowledge-playbook-1")
        self.assertEqual(applied[0].knowledge_type, "playbook")
        self.assertEqual(applied[0].decision, "support")
        self.assertEqual(applied[0].plan_id, "plan-1")

        history = governor.knowledge_application_ledger.history_for("plan-1")
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0].applied)
        self.assertEqual(history[0].knowledge_id, "knowledge-playbook-1")

    def test_low_confidence_playbook_is_ignored_not_applied(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)
        ignored: list[Event] = []
        granted: list[Event] = []
        kernel.register_subscriber(EventType.KNOWLEDGE_IGNORED, ignored.append)
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, granted.append)

        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-playbook-1",
            knowledge_type="playbook",
            consensus_confidence=PLAYBOOK_CONFIDENCE_THRESHOLD - 0.1,
        )
        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=6.0)

        self.assertEqual(len(granted), 1)
        self.assertEqual(granted[0].reason, "within policy and budget")

        self.assertEqual(len(ignored), 1)
        self.assertIsInstance(ignored[0], KnowledgeIgnoredEvent)
        history = governor.knowledge_application_ledger.history_for("plan-1")
        self.assertEqual(len(history), 1)
        self.assertFalse(history[0].applied)

    def test_learned_anti_pattern_influences_approval_decision(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)
        applied: list[Event] = []
        denied: list[Event] = []
        granted: list[Event] = []
        kernel.register_subscriber(EventType.KNOWLEDGE_APPLIED, applied.append)
        kernel.register_subscriber(EventType.APPROVAL_DENIED, denied.append)
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, granted.append)

        # Before the anti-pattern is learned, this exact plan shape is approved.
        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=6.0)
        self.assertEqual(len(granted), 1)

        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-anti-1",
            knowledge_type="anti_pattern",
            consensus_confidence=ANTI_PATTERN_CONFIDENCE_THRESHOLD,
            summary="repeated failure pattern",
        )

        # Same plan shape, proposed again after the anti-pattern was learned,
        # is now vetoed even though it still satisfies policy and budget.
        publish_plan_proposed(kernel, plan_id="plan-2", attention_cost=1.0, capital_cost=6.0)

        self.assertEqual(len(granted), 1)  # unchanged: no second approval
        self.assertEqual(len(denied), 1)
        self.assertIsInstance(denied[0], ApprovalDeniedEvent)
        self.assertEqual(denied[0].plan_id, "plan-2")
        self.assertIn("anti-pattern knowledge-anti-1 enforced", denied[0].reason)

        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0].decision, "deny")
        self.assertEqual(applied[0].knowledge_type, "anti_pattern")

        records = governor.approval_log.read_all()
        self.assertEqual(records[-1].decision, "rejected")
        # Budget was never touched by the vetoed plan.
        budget = governor.budget_store.get("budget-1")
        self.assertEqual(budget.available_capital, 94.0)  # only plan-1's spend

    def test_low_confidence_anti_pattern_does_not_veto(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)
        granted: list[Event] = []
        kernel.register_subscriber(EventType.APPROVAL_GRANTED, granted.append)

        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-anti-1",
            knowledge_type="anti_pattern",
            consensus_confidence=ANTI_PATTERN_CONFIDENCE_THRESHOLD - 0.1,
        )
        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=6.0)

        self.assertEqual(len(granted), 1)
        history = governor.knowledge_application_ledger.history_for("plan-1")
        self.assertEqual(len(history), 1)
        self.assertFalse(history[0].applied)

    def test_constitution_overrides_conflicting_learned_knowledge(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)
        denied: list[Event] = []
        kernel.register_subscriber(EventType.APPROVAL_DENIED, denied.append)

        # A high-confidence playbook is on record, but this plan violates the
        # Constitution outright (negative capital_cost). The playbook must
        # not rescue it.
        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-playbook-1",
            knowledge_type="playbook",
            consensus_confidence=0.99,
        )
        publish_plan_proposed(kernel, plan_id="plan-1", capital_cost=-1.0)

        self.assertEqual(len(denied), 1)
        self.assertIn("non_negative_costs", denied[0].reason)
        self.assertNotIn("playbook", denied[0].reason)

        # Knowledge is only ever consulted once policy and budget already
        # passed, so a constitution-denied plan never reaches the knowledge
        # gate at all.
        self.assertEqual(governor.knowledge_application_ledger.history_for("plan-1"), [])

    def test_constitution_overrides_even_with_anti_pattern_present(self) -> None:
        kernel = Kernel()
        governor = self._configured_governor(kernel)
        denied: list[Event] = []
        kernel.register_subscriber(EventType.APPROVAL_DENIED, denied.append)

        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-anti-1",
            knowledge_type="anti_pattern",
            consensus_confidence=0.99,
        )
        publish_plan_proposed(kernel, plan_id="plan-1", capital_cost=-1.0)

        self.assertEqual(len(denied), 1)
        self.assertIn("non_negative_costs", denied[0].reason)
        self.assertNotIn("anti-pattern", denied[0].reason)
        self.assertEqual(governor.knowledge_application_ledger.history_for("plan-1"), [])


class KnowledgeApplicationLedgerAppendOnlyTests(unittest.TestCase):
    def test_application_history_accumulates_across_plans_without_mutation(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )
        governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=100.0, available_capital=1000.0)
        )
        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-playbook-1",
            knowledge_type="playbook",
            consensus_confidence=PLAYBOOK_CONFIDENCE_THRESHOLD,
        )

        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=6.0)
        publish_plan_proposed(kernel, plan_id="plan-2", attention_cost=1.0, capital_cost=6.0)

        all_records = governor.knowledge_application_ledger.read_all()
        self.assertEqual(len(all_records), 2)
        self.assertEqual([record.plan_id for record in all_records], ["plan-1", "plan-2"])
        # Earlier plans' records are untouched by later ones.
        self.assertEqual(governor.knowledge_application_ledger.history_for("plan-1")[0].plan_id, "plan-1")
        self.assertEqual(governor.knowledge_application_ledger.history_for("plan-2")[0].plan_id, "plan-2")


class GovernorKnowledgeReplayTests(unittest.TestCase):
    def test_replay_reconstructs_knowledge_state_and_application_history(self) -> None:
        event_log = EventLog()
        kernel = Kernel(event_log=event_log)
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )
        governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )

        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=6.0)
        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-anti-1",
            knowledge_type="anti_pattern",
            consensus_confidence=ANTI_PATTERN_CONFIDENCE_THRESHOLD,
        )
        publish_plan_proposed(kernel, plan_id="plan-2", attention_cost=1.0, capital_cost=6.0)

        rebuilt_kernel = Kernel(event_log=event_log)
        rebuilt_governor = Governor(rebuilt_kernel)
        rebuilt_governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )
        rebuilt_governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )
        rebuilt_kernel.replay()

        self.assertEqual(
            rebuilt_governor.knowledge_advisor.anti_patterns(), governor.knowledge_advisor.anti_patterns()
        )
        self.assertEqual(rebuilt_governor.knowledge_advisor.playbooks(), governor.knowledge_advisor.playbooks())

        # application_id is minted fresh at decision time (like approval_id),
        # so replay reproduces the same decisions but not the same IDs —
        # compare the meaningful fields instead, same precedent as the
        # existing approval-decision replay test above.
        def _application_shape(record: KnowledgeApplicationRecord) -> tuple[str, str, str, bool, str]:
            return (record.knowledge_id, record.knowledge_type, record.plan_id, record.applied, record.reason)

        self.assertEqual(
            [_application_shape(record) for record in rebuilt_governor.knowledge_application_ledger.read_all()],
            [_application_shape(record) for record in governor.knowledge_application_ledger.read_all()],
        )
        self.assertEqual(
            [record.decision for record in rebuilt_governor.approval_log.read_all()],
            [record.decision for record in governor.approval_log.read_all()],
        )
        self.assertEqual(rebuilt_governor.approval_log.read_all()[-1].decision, "rejected")


class GovernorKnowledgeSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_knowledge_state(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )
        governor.fund_budget(
            BudgetState(budget_id="budget-1", available_attention=10.0, available_capital=100.0)
        )

        publish_knowledge_revision_completed(
            kernel,
            knowledge_id="knowledge-playbook-1",
            knowledge_type="playbook",
            consensus_confidence=PLAYBOOK_CONFIDENCE_THRESHOLD,
        )
        publish_plan_proposed(kernel, plan_id="plan-1", attention_cost=1.0, capital_cost=6.0)
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_governor = Governor(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored_playbooks = {k.knowledge_id: k for k in rebuilt_governor.knowledge_advisor.playbooks()}
        self.assertIn("knowledge-playbook-1", restored_playbooks)
        self.assertEqual(restored_playbooks["knowledge-playbook-1"].consensus_confidence, PLAYBOOK_CONFIDENCE_THRESHOLD)

        restored_applications = rebuilt_governor.knowledge_application_ledger.read_all()
        self.assertEqual(len(restored_applications), 1)
        self.assertEqual(restored_applications[0].plan_id, "plan-1")
        self.assertEqual(
            restored_applications,
            governor.knowledge_application_ledger.read_all(),
        )


def _adopt_research_constitution(
    governor: Governor,
    *,
    constitution_id: str = "research-constitution-1",
    research_budget: float = 50.0,
    window_seconds: float = DEFAULT_RESEARCH_BUDGET_WINDOW_SECONDS,
    max_searches_per_deliberation: int = 5,
    max_search_depth: int = 3,
    extra_rules: tuple[str, ...] = (),
) -> None:
    governor.adopt_constitution(
        Constitution(
            constitution_id=constitution_id,
            version=1,
            rules=(
                "non_negative_costs",
                f"research_budget:{research_budget},{window_seconds}",
                f"max_searches_per_deliberation:{max_searches_per_deliberation}",
                f"max_search_depth:{max_search_depth}",
                *extra_rules,
            ),
        )
    )


class ResearchRuleContextModelTests(unittest.TestCase):
    def test_context_carries_required_fields(self) -> None:
        context = ResearchRuleContext(search_depth=2, searches_this_deliberation=3, research_spend_in_window=10.0)

        self.assertEqual(context.search_depth, 2)
        self.assertEqual(context.searches_this_deliberation, 3)
        self.assertEqual(context.research_spend_in_window, 10.0)

    def test_context_is_immutable(self) -> None:
        context = ResearchRuleContext(search_depth=2, searches_this_deliberation=3, research_spend_in_window=10.0)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            context.search_depth = 5  # type: ignore[misc]


class ResearchSpendRecordModelTests(unittest.TestCase):
    def test_record_carries_required_fields(self) -> None:
        record = ResearchSpendRecord(
            request_id="request-1",
            deliberation_id="deliberation-1",
            category="research",
            estimated_cost=5.0,
            search_depth=1,
            decision="approved",
            reason="within research budget and caps",
        )

        self.assertEqual(record.request_id, "request-1")
        self.assertEqual(record.deliberation_id, "deliberation-1")
        self.assertEqual(record.category, "research")
        self.assertEqual(record.estimated_cost, 5.0)
        self.assertEqual(record.search_depth, 1)
        self.assertEqual(record.decision, "approved")

    def test_record_is_immutable(self) -> None:
        record = ResearchSpendRecord(
            request_id="request-1",
            deliberation_id="deliberation-1",
            category="research",
            estimated_cost=5.0,
            search_depth=1,
            decision="approved",
            reason="ok",
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.decision = "denied"  # type: ignore[misc]


class ResearchSpendLedgerTests(unittest.TestCase):
    def test_for_deliberation_filters_by_deliberation_id(self) -> None:
        ledger = ResearchSpendLedger()
        ledger.append(
            ResearchSpendRecord(
                request_id="r1", deliberation_id="d1", category="research",
                estimated_cost=1.0, search_depth=1, decision="approved", reason="ok",
            )
        )
        ledger.append(
            ResearchSpendRecord(
                request_id="r2", deliberation_id="d2", category="research",
                estimated_cost=1.0, search_depth=1, decision="approved", reason="ok",
            )
        )

        self.assertEqual([r.request_id for r in ledger.for_deliberation("d1")], ["r1"])

    def test_approved_within_excludes_denied_and_out_of_window_entries(self) -> None:
        ledger = ResearchSpendLedger()
        now = datetime.now(timezone.utc)
        ledger.append(
            ResearchSpendRecord(
                request_id="in-window", deliberation_id="d1", category="research",
                estimated_cost=1.0, search_depth=1, decision="approved", reason="ok", timestamp=now,
            )
        )
        ledger.append(
            ResearchSpendRecord(
                request_id="denied", deliberation_id="d1", category="research",
                estimated_cost=1.0, search_depth=1, decision="denied", reason="no", timestamp=now,
            )
        )
        ledger.append(
            ResearchSpendRecord(
                request_id="stale",
                deliberation_id="d1",
                category="research",
                estimated_cost=1.0,
                search_depth=1,
                decision="approved",
                reason="ok",
                timestamp=now - timedelta(seconds=1000),
            )
        )

        within = ledger.approved_within(now=now, window_seconds=100)

        self.assertEqual([r.request_id for r in within], ["in-window"])


class GovernorResearchSpendGateTests(unittest.TestCase):
    def test_denies_when_no_constitution_configured(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)

        denied: list[ResearchSpendDeniedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_DENIED, denied.append)
        publish_research_spend_requested(kernel)

        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0].reason, "no constitution configured")

    def test_denies_when_constitution_has_no_research_budget_rule(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(constitution_id="constitution-1", version=1, rules=("non_negative_costs",))
        )

        denied: list[ResearchSpendDeniedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_DENIED, denied.append)
        publish_research_spend_requested(kernel)

        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0].reason, "no research policy configured")

    def test_approves_request_within_budget_and_caps(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        _adopt_research_constitution(governor, research_budget=50.0, max_searches_per_deliberation=5, max_search_depth=3)

        approved: list[ResearchSpendApprovedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_APPROVED, approved.append)
        publish_research_spend_requested(kernel, request_id="request-1", estimated_cost=5.0, search_depth=2)

        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0].request_id, "request-1")
        self.assertEqual(approved[0].approved_cost, 5.0)
        self.assertEqual(governor.research_spend_ledger.read_all()[-1].decision, "approved")

    def test_denies_when_search_depth_exceeds_cap(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        _adopt_research_constitution(governor, max_search_depth=3)

        denied: list[ResearchSpendDeniedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_DENIED, denied.append)
        publish_research_spend_requested(kernel, search_depth=4)

        self.assertEqual(len(denied), 1)
        self.assertIn("search_depth=4", denied[0].reason)
        self.assertIn("exceeds limit=3", denied[0].reason)
        self.assertEqual(governor.research_spend_ledger.read_all()[-1].decision, "denied")

    def test_denies_when_deliberation_search_cap_exceeded(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        _adopt_research_constitution(governor, max_searches_per_deliberation=2)

        denied: list[ResearchSpendDeniedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_DENIED, denied.append)
        publish_research_spend_requested(kernel, request_id="r1", deliberation_id="deliberation-x")
        publish_research_spend_requested(kernel, request_id="r2", deliberation_id="deliberation-x")
        publish_research_spend_requested(kernel, request_id="r3", deliberation_id="deliberation-x")

        self.assertEqual(len(denied), 1)
        self.assertIn("searches_this_deliberation=3", denied[0].reason)
        self.assertIn("exceeds limit=2", denied[0].reason)

    def test_different_deliberations_have_independent_search_counts(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        _adopt_research_constitution(governor, max_searches_per_deliberation=1)

        denied: list[ResearchSpendDeniedEvent] = []
        approved: list[ResearchSpendApprovedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_DENIED, denied.append)
        kernel.register_subscriber(EventType.RESEARCH_SPEND_APPROVED, approved.append)
        publish_research_spend_requested(kernel, request_id="r1", deliberation_id="deliberation-a")
        publish_research_spend_requested(kernel, request_id="r2", deliberation_id="deliberation-b")

        self.assertEqual(len(approved), 2)
        self.assertEqual(len(denied), 0)

    def test_denies_when_rolling_window_budget_exhausted(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        _adopt_research_constitution(governor, research_budget=10.0, window_seconds=3600.0, max_searches_per_deliberation=10)

        denied: list[ResearchSpendDeniedEvent] = []
        approved: list[ResearchSpendApprovedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_DENIED, denied.append)
        kernel.register_subscriber(EventType.RESEARCH_SPEND_APPROVED, approved.append)

        publish_research_spend_requested(kernel, request_id="r1", deliberation_id="d1", estimated_cost=6.0)
        publish_research_spend_requested(kernel, request_id="r2", deliberation_id="d2", estimated_cost=6.0)

        self.assertEqual(len(approved), 1)
        self.assertEqual(len(denied), 1)
        self.assertIn("exceeds research_budget=10.0", denied[0].reason)

    def test_entries_outside_rolling_window_do_not_count_toward_budget(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        _adopt_research_constitution(governor, research_budget=10.0, window_seconds=100.0, max_searches_per_deliberation=10)

        # Simulate a previously-approved spend that has already aged out of
        # the rolling window (Governor's own ledger, never Memory's).
        governor.research_spend_ledger.append(
            ResearchSpendRecord(
                request_id="stale-request",
                deliberation_id="d0",
                category="research",
                estimated_cost=9.0,
                search_depth=1,
                decision="approved",
                reason="ok",
                timestamp=datetime.now(timezone.utc) - timedelta(seconds=1000),
            )
        )

        approved: list[ResearchSpendApprovedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_APPROVED, approved.append)
        publish_research_spend_requested(kernel, request_id="fresh-request", estimated_cost=9.0)

        self.assertEqual(len(approved), 1)

    def test_default_window_used_when_rule_omits_window_argument(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        governor.adopt_constitution(
            Constitution(
                constitution_id="constitution-1",
                version=1,
                rules=("research_budget:10", "max_searches_per_deliberation:5", "max_search_depth:3"),
            )
        )

        approved: list[ResearchSpendApprovedEvent] = []
        kernel.register_subscriber(EventType.RESEARCH_SPEND_APPROVED, approved.append)
        publish_research_spend_requested(kernel, estimated_cost=5.0)

        self.assertEqual(len(approved), 1)


class GovernorResearchSpendSnapshotTests(unittest.TestCase):
    def test_snapshot_restore_reconstructs_research_spend_ledger(self) -> None:
        kernel = Kernel()
        governor = Governor(kernel)
        _adopt_research_constitution(governor, research_budget=10.0, max_searches_per_deliberation=5)

        publish_research_spend_requested(kernel, request_id="r1", deliberation_id="d1", estimated_cost=5.0)
        publish_research_spend_requested(kernel, request_id="r2", deliberation_id="d1", estimated_cost=20.0)
        kernel.create_snapshot()

        rebuilt_kernel = Kernel(event_log=kernel.event_log, snapshot_store=kernel.snapshot_store)
        rebuilt_governor = Governor(rebuilt_kernel)
        rebuilt_kernel.replay()

        restored = {record.request_id: record for record in rebuilt_governor.research_spend_ledger.read_all()}
        self.assertEqual(restored["r1"].decision, "approved")
        self.assertEqual(restored["r2"].decision, "denied")
        self.assertEqual(
            [r.request_id for r in rebuilt_governor.research_spend_ledger.read_all()],
            [r.request_id for r in governor.research_spend_ledger.read_all()],
        )


if __name__ == "__main__":
    unittest.main()
