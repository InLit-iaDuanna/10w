import unittest

from fastapi import FastAPI

import render_ops
from render_ops.fixtures import FIXTURE_TIME, mock_dependency_snapshot, mock_manifest
from render_ops.router import plan_render_job, validate_render_manifest
from render_ops.schemas import ExecutionMode, RenderJobPlanRequest


class PublicApiTests(unittest.TestCase):
    def test_public_entrypoint_exports_router_and_contracts(self):
        self.assertIn("router", render_ops.__all__)
        self.assertIn("RenderManifest", render_ops.__all__)
        self.assertIn("WritebackExecutor", render_ops.__all__)

    def test_openapi_uses_pydantic_contracts(self):
        app = FastAPI()
        app.include_router(render_ops.router)
        schema = app.openapi()
        self.assertIn("/api/v1/render/jobs/plan", schema["paths"])
        self.assertIn("/api/v1/render/manifests/validate", schema["paths"])
        self.assertIn("RenderManifest", schema["components"]["schemas"])
        self.assertIn("RenderJob", schema["components"]["schemas"])

    def test_route_functions_delegate_to_domain_service(self):
        manifest = mock_manifest()
        summary = validate_render_manifest(manifest)
        self.assertEqual(summary.manifest_id, manifest.manifest_id)
        request = RenderJobPlanRequest(
            job_id="rjob_api_plan",
            brief=manifest.brief,
            recipe=manifest.recipe,
            dependency_snapshot=mock_dependency_snapshot(),
            existing_aovs=manifest.aovs,
            previous_snapshot=mock_dependency_snapshot(),
            execution_mode=ExecutionMode.CACHED,
            requested_at=FIXTURE_TIME,
        )
        job = plan_render_job(request)
        self.assertEqual(job.execution_mode, ExecutionMode.CACHED)
        self.assertEqual(job.cache_plan.reused_passes, [])
        self.assertEqual(
            set(job.cache_plan.capture_passes), set(manifest.recipe.required_passes)
        )


if __name__ == "__main__":
    unittest.main()
