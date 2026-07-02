import dataclasses
import unittest
from datetime import datetime, timezone

from src.events import (
    ApprovalDeniedEvent,
    ApprovalGrantedEvent,
    ApprovalRequiredEvent,
    BudgetCheckedEvent,
    Event,
    EventType,
    PlanProposedEvent,
    PolicyEvaluatedEvent,
)
from src.governor import (
    ApprovalLog,
    ApprovalRecord,
    BudgetState,
    BudgetStore,
    Constitution,
    ConstitutionStore,
    Governor,
)
from src.kernel import Kernel


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


if __name__ == "__main__":
    unittest.main()
