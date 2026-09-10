import json
import tempfile
import unittest
from pathlib import Path

import yaml

from asset_factory import JOBS, PipelineState, StepState, create_router
from sceneops_blender import (
    BlenderOperation,
    DeterministicMockBlenderAdapter,
    extract_sceneops_ids,
    read_glb_json,
)

from factories import make_pipeline_service, make_record_and_request


class PipelineHappyPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_manifest_public_router_and_jobs_register(self):
        module_root = Path(__file__).resolve().parents[2]
        manifest = yaml.safe_load((module_root / "module.yaml").read_text())
        self.assertEqual(manifest["id"], "asset-factory")
        self.assertEqual(set(manifest["requires"]["modules"]),
                         {"core-kernel", "module-runtime", "asset-library", "concept-lab"})
        self.assertEqual([job.id for job in JOBS], [
            "asset.preflight",
            "asset.blender.process",
            "asset.validate",
            "asset.publish",
        ])
        record, request = make_record_and_request(self.root)
        service, _ = make_pipeline_service(self.root, record, request)
        router = create_router(service, lambda _: DeterministicMockBlenderAdapter(self.root))
        self.assertEqual(router.prefix, "/v1/asset-pipeline")
        self.assertTrue(
            {
                "/v1/asset-pipeline/runs",
                "/v1/asset-pipeline/runs/{pipeline_run_id}:cancel",
                "/v1/asset-pipeline/runs/{pipeline_run_id}:retry",
                "/v1/asset-pipeline/runs/{pipeline_run_id}:rollback",
            }.issubset({route.path for route in router.routes})
        )

    def test_dry_run_is_planned_and_never_executes_adapter(self):
        record, request = make_record_and_request(self.root, dry_run=True)
        adapter = DeterministicMockBlenderAdapter(self.root)
        service, _ = make_pipeline_service(self.root, record, request)
        run = service.run(request, adapter)
        self.assertEqual(run.state, PipelineState.PLANNED)
        self.assertEqual(run.execution_mode.value, "planned")
        self.assertEqual(adapter.call_counts, {})
        self.assertTrue(all(step.state in {StepState.PLANNED, StepState.SKIPPED} for step in run.steps))

    def test_unapproved_changeset_pauses_without_execution(self):
        record, request = make_record_and_request(self.root, approved=False)
        adapter = DeterministicMockBlenderAdapter(self.root)
        service, _ = make_pipeline_service(self.root, record, request)
        run = service.run(request, adapter)
        self.assertEqual(run.state, PipelineState.WAITING_APPROVAL)
        self.assertEqual(run.execution_mode.value, "planned")
        self.assertEqual(adapter.call_counts, {})

    def test_hero_key_reaches_published_asset_version_with_manifest_and_identity(self):
        record, request = make_record_and_request(self.root)
        service, catalog = make_pipeline_service(self.root, record, request)
        adapter = DeterministicMockBlenderAdapter(self.root)
        events = []
        source_path = self.root / record.source.project_relative_path
        original_source = source_path.read_bytes()
        run = service.run(request, adapter, events.append)

        self.assertEqual(run.state, PipelineState.SUCCEEDED)
        self.assertEqual(run.execution_mode.value, "mock")
        self.assertIsNotNone(run.published_version)
        self.assertEqual(run.published_version.status.value, "published")
        self.assertEqual({item.format for item in run.published_version.outputs}, {"glb", "fbx", "json"})
        self.assertTrue(all(len(item.sha256) == 64 for item in run.published_version.outputs))
        self.assertEqual({item.approval_state for item in run.published_version.provenance}, {"approved"})
        self.assertEqual({item.execution_mode.value for item in run.published_version.provenance}, {"mock"})

        manifest_path = self.root / request.output_directory / "v1" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["execution_mode"], "mock")
        self.assertEqual(manifest["source_asset_id"], record.source.source_asset_id)
        self.assertEqual(manifest["object_identities"][0]["sceneops_id"], record.source_objects[0].sceneops_id)
        glb = self.root / request.output_directory / "v1" / "asset.glb"
        glb_ids = set(extract_sceneops_ids(read_glb_json(glb)))
        version_ids = {item.sceneops_id for item in run.published_version.object_identities}
        self.assertEqual(glb_ids, version_ids)
        self.assertIn(record.source_objects[0].sceneops_id, glb_ids)
        self.assertEqual(catalog.get(record.spec.asset_id).latest_version.asset_version_id, request.asset_version_id)
        self.assertIn("asset.pipeline.completed", [event["event_type"] for event in events])
        self.assertEqual(len({event["event_id"] for event in events}), len(events))
        completed_event = next(
            event for event in events if event["event_type"] == "asset.pipeline.completed"
        )
        self.assertEqual(completed_event["correlation_id"], request.pipeline_run_id)
        self.assertEqual(completed_event["causation_id"], request.change_set.change_set_id)
        self.assertEqual(completed_event["actor"]["id"], request.creator)
        self.assertEqual(
            set(completed_event["payload"]["artifact_ids"]),
            {item.artifact_id for item in run.published_version.outputs},
        )
        self.assertEqual(source_path.read_bytes(), original_source)
        self.assertTrue((self.root / run.working_copy_path).is_file())

    def test_same_pipeline_accepts_warehouse_escape_obstacle_without_platform_changes(self):
        record, request = make_record_and_request(
            self.root,
            slug="warehouse_obstacle",
            display_name="仓库路障",
            project_id="prj_warehouse_escape",
            run_id="run_warehouse_obstacle_1",
            idempotency_key="idem_warehouse_obstacle_1",
            triangle_budget=3000,
            requires_lods=False,
        )
        service, catalog = make_pipeline_service(self.root, record, request)
        run = service.run(
            request, DeterministicMockBlenderAdapter(self.root, triangle_count=2200)
        )
        self.assertEqual(run.state, PipelineState.SUCCEEDED)
        lod_step = next(step for step in run.steps if step.kind.value == "lod")
        self.assertEqual(lod_step.state, StepState.SKIPPED)
        self.assertIn("does not require", lod_step.skip_reason)
        self.assertEqual(catalog.get(record.spec.asset_id).latest_version.asset_id, "ast_warehouse_obstacle")

    def test_event_sink_failure_cannot_abort_or_duplicate_a_published_run(self):
        record, request = make_record_and_request(self.root)
        service, catalog = make_pipeline_service(self.root, record, request)
        adapter = DeterministicMockBlenderAdapter(self.root)

        def failing_sink(_event):
            raise RuntimeError("fixture event transport is offline")

        run = service.run(request, adapter, failing_sink)
        counts = dict(adapter.call_counts)
        self.assertEqual(run.state, PipelineState.SUCCEEDED)
        self.assertEqual(
            catalog.get(record.spec.asset_id).latest_version.asset_version_id,
            request.asset_version_id,
        )
        self.assertIn(
            "EVENT_DELIVERY_FAILED",
            [log.code for step in run.steps for log in step.logs],
        )
        replay = service.run(request, adapter, failing_sink)
        self.assertEqual(replay.model_dump(), run.model_dump())
        self.assertEqual(adapter.call_counts, counts)


if __name__ == "__main__":
    unittest.main()
