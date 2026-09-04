import json
import unittest
from pathlib import Path

from asset_factory import PipelineRun, PipelineState
from asset_library import AssetRecord, ExecutionMode, GateStatus, PublicationStatus
from sceneops_blender import BlenderResult, IntegrationHealth

ROOT = Path(__file__).parents[4]


def load(relative):
    with (ROOT / relative).open(encoding="utf-8") as stream:
        return json.load(stream)


class FixtureContractTest(unittest.TestCase):
    def test_asset_records_validate_the_public_model_and_identity_rules(self):
        paths = [
            "modules/asset-library/fixtures/hero-key.asset-record.json",
            "modules/asset-library/fixtures/warehouse-obstacle.asset-record.json",
        ]
        records = [AssetRecord.model_validate(load(path)) for path in paths]
        self.assertNotEqual(records[0].spec.asset_id, records[1].spec.asset_id)
        for path, record in zip(paths, records):
            version = record.versions[0]
            self.assertEqual(version.status, PublicationStatus.PUBLISHED)
            self.assertEqual(version.execution_mode, ExecutionMode.MOCK)
            self.assertNotEqual(record.spec.asset_id, record.source.source_asset_id)
            self.assertNotEqual(
                record.spec.asset_id, record.usage_references[0].scene_instance_id
            )
            self.assertTrue(
                all(gate.status == GateStatus.PASSED for gate in version.quality_gates)
            )
            self.assertTrue(all(len(output.sha256) == 64 for output in version.outputs))
            self.assertEqual(
                record.model_dump(mode="json"),
                AssetRecord.model_validate(load(path)).model_dump(mode="json"),
            )

    def test_runs_and_adapter_responses_validate_typed_mock_contracts(self):
        files = ["hero-key.pipeline-run.json", "warehouse-obstacle.pipeline-run.json"]
        for name in files:
            run = PipelineRun.model_validate(
                load("modules/asset-factory/fixtures/" + name)
            )
            self.assertEqual(run.execution_mode, ExecutionMode.MOCK)
            self.assertEqual(run.state, PipelineState.SUCCEEDED)
            self.assertTrue(
                all(step.execution_mode == ExecutionMode.MOCK for step in run.steps)
            )

        health = IntegrationHealth.model_validate(
            load("integrations/blender-addon/tests/fixtures/health-online.json")
        )
        self.assertTrue(health.healthy)
        self.assertEqual(health.mode.value, "mock")
        for name in ["scene-scan.json", "export-manifest.json"]:
            response = BlenderResult.model_validate(
                load("integrations/blender-addon/tests/fixtures/" + name)
            )
            self.assertTrue(response.succeeded)
            self.assertEqual(response.mode.value, "mock")


if __name__ == "__main__":
    unittest.main()
