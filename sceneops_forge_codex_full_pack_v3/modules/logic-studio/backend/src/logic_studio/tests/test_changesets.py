import unittest

from logic_studio.changesets import (
    AdapterUnavailableError,
    ApprovalRequiredError,
    CodeChangeCoordinator,
    CodeChangeProposalError,
)
from logic_studio.models import ChangeSetStatus
from logic_studio.tests.support import code_change_proposal
from logic_studio.unity_adapter import (
    AdapterExecutionContext,
    DeterministicMockUnityCodeChangeAdapter,
    UnityAdapterCancelled,
)


def execution_context(cancelled=False):
    progress = []
    context = AdapterExecutionContext(
        request_id="req_logic_test",
        correlation_id="corr_logic_test",
        timeout_seconds=30,
        max_attempts=1,
        is_cancelled=lambda: cancelled,
        report_progress=progress.append,
    )
    return context, progress


def coordinator():
    return CodeChangeCoordinator(
        id_factory=lambda: "chg_key_door_001",
        clock=lambda: "2026-09-04T00:00:00Z",
    )


def approved_change_set():
    changes = coordinator()
    waiting = changes.propose(code_change_proposal())
    approved = changes.approve(
        waiting,
        approver_id="usr_reviewer",
        permissions={"logic:code:approve"},
    )
    return changes, approved


class ScopeMismatchedAdapter(DeterministicMockUnityCodeChangeAdapter):
    def dry_run(self, change_set, context):
        preview = super().dry_run(change_set, context)
        return preview.model_copy(update={"impacted_paths": ["Assets/Unexpected.cs"]})


class ChangeSetTests(unittest.TestCase):
    def test_csharp_change_requires_explicit_approval(self):
        changes = coordinator()
        waiting = changes.propose(code_change_proposal())
        self.assertEqual(waiting.status, ChangeSetStatus.WAITING_APPROVAL)
        self.assertTrue(waiting.dry_run)
        adapter = DeterministicMockUnityCodeChangeAdapter()
        context, _ = execution_context()
        with self.assertRaises(ApprovalRequiredError):
            changes.apply(waiting, adapter, context)
        self.assertEqual(adapter.calls, [])
        with self.assertRaises(ApprovalRequiredError):
            changes.approve(waiting, approver_id="usr_reader", permissions={"logic:read"})

    def test_approved_change_runs_dry_run_compile_and_tests(self):
        changes, approved = approved_change_set()
        adapter = DeterministicMockUnityCodeChangeAdapter()
        context, progress = execution_context()
        result = changes.apply(approved, adapter, context)
        self.assertEqual(result.status, ChangeSetStatus.SUCCEEDED)
        self.assertEqual(result.mode.value, "mock")
        self.assertTrue(result.validation_result.succeeded)
        self.assertEqual(
            result.validation_result.provenance.correlation_id,
            "corr_logic_test",
        )
        self.assertEqual(
            adapter.calls,
            ["health_check", "capabilities", "dry_run", "apply", "compile_and_test"],
        )
        self.assertEqual([item.stage for item in progress], ["dry_run", "apply", "compile_and_test"])

    def test_compile_failure_triggers_rollback(self):
        changes, approved = approved_change_set()
        adapter = DeterministicMockUnityCodeChangeAdapter(compile_succeeded=False)
        context, _ = execution_context()
        result = changes.apply(approved, adapter, context)
        self.assertEqual(result.status, ChangeSetStatus.ROLLED_BACK)
        self.assertEqual(result.last_error, "COMPILE_TEST_FAILED")
        self.assertTrue(result.rollback_result.succeeded)
        self.assertEqual(adapter.calls[-1], "rollback")

    def test_succeeded_change_can_be_explicitly_rolled_back(self):
        changes, approved = approved_change_set()
        adapter = DeterministicMockUnityCodeChangeAdapter()
        context, _ = execution_context()
        succeeded = changes.apply(approved, adapter, context)
        rolled_back = changes.rollback(succeeded, adapter, context)
        self.assertEqual(rolled_back.status, ChangeSetStatus.ROLLED_BACK)
        self.assertTrue(rolled_back.rollback_result.succeeded)

    def test_offline_adapter_fails_without_apply(self):
        changes, approved = approved_change_set()
        adapter = DeterministicMockUnityCodeChangeAdapter(online=False)
        context, _ = execution_context()
        with self.assertRaises(AdapterUnavailableError):
            changes.apply(approved, adapter, context)
        self.assertEqual(adapter.calls, ["health_check"])

    def test_path_boundary_and_diff_are_validated(self):
        changes = coordinator()
        with self.assertRaises(CodeChangeProposalError):
            changes.propose(
                code_change_proposal(target_paths=["../ProjectSettings/ProjectSettings.asset"])
            )
        with self.assertRaises(CodeChangeProposalError):
            changes.propose(code_change_proposal(unified_diff="not a unified diff"))

    def test_diff_cannot_hide_an_undeclared_target(self):
        hidden = (
            code_change_proposal().unified_diff
            + "--- a/Assets/Hidden.cs\n"
            + "+++ b/Assets/Hidden.cs\n"
            + "@@ -0,0 +1 @@\n+hidden\n"
        )
        with self.assertRaisesRegex(CodeChangeProposalError, "undeclared"):
            coordinator().propose(code_change_proposal(unified_diff=hidden))

    def test_dry_run_scope_mismatch_stops_before_apply(self):
        changes, approved = approved_change_set()
        adapter = ScopeMismatchedAdapter()
        context, _ = execution_context()
        result = changes.apply(approved, adapter, context)
        self.assertEqual(result.status, ChangeSetStatus.FAILED)
        self.assertEqual(result.last_error, "DRY_RUN_SCOPE_MISMATCH")
        self.assertNotIn("apply", adapter.calls)

    def test_adapter_cancellation_is_structured(self):
        changes, approved = approved_change_set()
        adapter = DeterministicMockUnityCodeChangeAdapter()
        context, _ = execution_context(cancelled=True)
        with self.assertRaises(UnityAdapterCancelled):
            changes.apply(approved, adapter, context)
        self.assertEqual(adapter.calls, ["health_check", "capabilities"])


if __name__ == "__main__":
    unittest.main()
