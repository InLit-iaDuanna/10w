import unittest
from datetime import datetime, timezone

from sceneops_core_contracts import ExecutionMode, RunRecord, RunState
from core_kernel import InvalidRunTransition, transition_run


class RunTransitionTests(unittest.TestCase):
    def setUp(self):
        self.created_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
        self.run = RunRecord(
            run_id="run_fixture0001",
            job_id="core.run.transition",
            state=RunState.QUEUED,
            mode=ExecutionMode.MOCK,
            created_at=self.created_at,
        )

    def test_successful_run_transition_path(self):
        running = transition_run(self.run, RunState.RUNNING, self.created_at)
        succeeded = transition_run(running, RunState.SUCCEEDED, self.created_at)
        self.assertEqual(succeeded.state, RunState.SUCCEEDED)
        self.assertEqual(succeeded.mode, ExecutionMode.MOCK)
        self.assertEqual(succeeded.finished_at, self.created_at)

    def test_invalid_transition_exposes_structured_failure(self):
        with self.assertRaises(InvalidRunTransition) as caught:
            transition_run(self.run, RunState.SUCCEEDED, self.created_at)
        self.assertEqual(caught.exception.error.code, "INVALID_RUN_TRANSITION")
        self.assertFalse(caught.exception.error.retryable)


if __name__ == "__main__":
    unittest.main()
