import unittest
from datetime import datetime, timezone

from render_ops.fixtures import FIXTURE_TIME, mock_dependency_snapshot, mock_recipe, mock_scene
from render_ops.jobs import RenderJobRepository, RenderQueue
from render_ops.schemas import (
    CachePlan,
    ExecutionMode,
    JobFailure,
    RenderJob,
    RenderJobState,
)


def queued_job() -> RenderJob:
    recipe = mock_recipe()
    return RenderJob(
        job_id="rjob_queue_test",
        brief_id="rbrief_queue_test",
        recipe_id=recipe.recipe_id,
        recipe_version=recipe.version,
        scene=mock_scene(),
        dependency_snapshot=mock_dependency_snapshot(),
        cache_plan=CachePlan(capture_passes=recipe.required_passes),
        state=RenderJobState.QUEUED,
        execution_mode=ExecutionMode.MOCK,
        created_at=FIXTURE_TIME,
        updated_at=FIXTURE_TIME,
    )


class RenderQueueTests(unittest.TestCase):
    def setUp(self):
        self.clock_value = datetime(2026, 9, 4, 2, 0, tzinfo=timezone.utc)
        self.repository = RenderJobRepository()
        self.queue = RenderQueue(self.repository, clock=lambda: self.clock_value)
        self.queue.enqueue(queued_job())

    def test_success_state_machine_and_progress(self):
        running = self.queue.start("rjob_queue_test")
        self.assertEqual(running.state, RenderJobState.RUNNING)
        progressed = self.queue.progress(running.job_id, 0.4)
        self.assertEqual(progressed.progress, 0.4)
        waiting = self.queue.wait_for_approval(running.job_id)
        self.assertEqual(waiting.state, RenderJobState.WAITING_APPROVAL)
        self.queue.resume(running.job_id)
        succeeded = self.queue.succeed(running.job_id)
        self.assertEqual(succeeded.progress, 1.0)
        self.assertEqual(succeeded.state, RenderJobState.SUCCEEDED)

    def test_cancel_and_retry_increment_attempt(self):
        self.queue.start("rjob_queue_test")
        cancelled = self.queue.cancel("rjob_queue_test")
        self.assertEqual(cancelled.state, RenderJobState.CANCELLED)
        retried = self.queue.retry("rjob_queue_test")
        self.assertEqual(retried.state, RenderJobState.QUEUED)
        self.assertEqual(retried.attempt, 2)

    def test_failure_preserves_structured_error_and_retry_clears_it(self):
        self.queue.start("rjob_queue_test")
        failed = self.queue.fail(
            "rjob_queue_test",
            JobFailure(
                code="INTEGRATION_OFFLINE",
                message="ComfyUI is offline.",
                retryable=True,
                suggested_actions=["integration.open", "render.job.retry"],
            ),
        )
        self.assertEqual(failed.failure.code, "INTEGRATION_OFFLINE")
        retried = self.queue.retry("rjob_queue_test", ExecutionMode.LIVE)
        self.assertIsNone(retried.failure)
        self.assertEqual(retried.execution_mode, ExecutionMode.LIVE)

    def test_invalid_transition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid render job transition"):
            self.queue.succeed("rjob_queue_test")

    def test_non_retryable_failure_cannot_be_requeued(self):
        self.queue.start("rjob_queue_test")
        self.queue.fail(
            "rjob_queue_test",
            JobFailure(code="INVALID_INPUT", message="Invalid.", retryable=False),
        )
        with self.assertRaisesRegex(PermissionError, "not retryable"):
            self.queue.retry("rjob_queue_test")

    def test_enqueue_idempotency_rejects_same_id_with_different_inputs(self):
        different = queued_job().model_copy(update={"brief_id": "rbrief_different"})
        with self.assertRaisesRegex(ValueError, "reused for different inputs"):
            self.queue.enqueue(different)

    def test_queue_snapshot_survives_editor_visibility_lifecycle(self):
        self.queue.start("rjob_queue_test")
        snapshot = self.repository.dump_snapshot()
        restored = RenderJobRepository.restore_snapshot(snapshot)
        self.assertEqual(restored.get("rjob_queue_test").state, RenderJobState.RUNNING)
        self.assertEqual(restored.dump_snapshot(), snapshot)


if __name__ == "__main__":
    unittest.main()
