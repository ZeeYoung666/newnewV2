import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import (
    ApprovalDeniedEvent,
    ApprovalGrantedEvent,
    ApprovalRequiredEvent,
    BudgetCheckedEvent,
    ConstitutionAmendedEvent,
    ConstitutionAmendmentProposedEvent,
    ConstitutionAmendmentRejectedEvent,
    Event,
    EventType,
    PlanProposedEvent,
    PolicyEvaluatedEvent,
)
from src.governor import (
    Amendment,
    AmendmentLog,
    ApprovalLog,
    ApprovalRecord,
    BudgetState,
    BudgetStore,
    Constitution,
    ConstitutionStore,
    Governor,
    RuleRegistry,
)
from src.kernel import EventLog, Kernel


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


if __name__ == "__main__":
    unittest.main()
