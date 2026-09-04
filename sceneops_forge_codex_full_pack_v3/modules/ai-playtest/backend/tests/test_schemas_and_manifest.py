from __future__ import annotations

import unittest
import json
from datetime import datetime

import yaml
from pydantic import ValidationError

from test_support import FIXED_NOW, MODULE_ROOT, load_json, load_test_case, run_fixture

from ai_playtest.events import (
    EVENT_MODELS,
    EventActor,
    PlaytestIssueBackpinResolvedEvent,
    PlaytestStepRecordedEvent,
)
from ai_playtest.schemas import (
    ActionKind,
    AvailableAction,
    Backpin,
    EvidenceBundle,
    ExecutionMode,
    Issue,
    Observation,
    PlaytestRun,
    PlaytestStep,
    RunRequest,
    SourceCatalog,
    TestCase,
)
from adapters.fixture_schema import DeterministicRuntimeFixture


class SchemaAndManifestTests(unittest.TestCase):
    def test_both_reusable_test_cases_validate(self):
        hero = load_test_case()
        warehouse = TestCase.model_validate(load_json("warehouse-escape.test-case.json"))
        self.assertEqual(hero.test_case_id, "test.find-home.key-door")
        self.assertEqual(warehouse.project_id, "project.warehouse-escape")
        self.assertNotEqual(hero.project_id, warehouse.project_id)

    def test_registered_action_requires_registered_id(self):
        with self.assertRaises(ValidationError):
            AvailableAction(
                action_id="action.bad",
                kind="registered",
                label="缺少注册 ID",
            )

    def test_bounded_action_contract_contains_all_standard_and_registered_actions(self):
        self.assertEqual(
            {item.value for item in ActionKind},
            {"move", "look", "interact", "use_item", "confirm", "cancel", "registered"},
        )

    def test_observation_rejects_non_utc_timestamp(self):
        fixture = load_json("find-my-way-home-before.runtime.json")
        frame = fixture["frames"][0]
        from adapters import DeterministicPlaytestRunnerAdapter

        adapter = DeterministicPlaytestRunnerAdapter(fixture)
        observation = adapter._observation().model_dump(mode="python")
        observation["observed_at"] = datetime(2026, 9, 4, 1, 0)
        with self.assertRaises(ValidationError):
            Observation.model_validate(observation)

    def test_manifest_matches_public_contributions(self):
        manifest = yaml.safe_load((MODULE_ROOT / "module.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "ai-playtest")
        self.assertEqual(len(manifest["contributes"]["editors"]), 6)
        self.assertIn("playtest.step.recorded@1", manifest["contributes"]["events"])
        self.assertEqual(manifest["entrypoints"]["backend"], "ai_playtest")
        self.assertEqual(manifest["feature_flag"], "ai_playtest")

    def test_event_models_publish_versioned_json_schemas(self):
        for name, model in EVENT_MODELS.items():
            schema = model.model_json_schema()
            self.assertEqual(schema["properties"]["event_version"]["const"], 1, name)
            self.assertIn("payload", schema["properties"], name)

    def test_event_envelope_cannot_mislabel_mock_payload_as_live(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.event-mode"
        )
        with self.assertRaises(ValidationError):
            PlaytestStepRecordedEvent(
                event_id="event.step.mode-mismatch",
                occurred_at=FIXED_NOW,
                project_id=run.test_case.project_id,
                correlation_id="correlation.event-mode",
                causation_id="causation.event-mode",
                actor=EventActor(type="system", id="system.playtest"),
                mode="live",
                payload=run.steps[0],
            )

    def test_generated_contract_schemas_match_pydantic_sources(self):
        manifest_directory = MODULE_ROOT / "contracts" / "manifests"
        self.assertEqual(
            json.loads((manifest_directory / "test-case.v1.schema.json").read_text()),
            TestCase.model_json_schema(),
        )
        self.assertEqual(
            json.loads(
                (manifest_directory / "deterministic-runtime-fixture.v1.schema.json").read_text()
            ),
            DeterministicRuntimeFixture.model_json_schema(),
        )
        self.assertEqual(
            json.loads(
                (manifest_directory / "source-catalog.v1.schema.json").read_text()
            ),
            SourceCatalog.model_json_schema(),
        )
        event_directory = MODULE_ROOT / "contracts" / "events"
        for event_name, model in EVENT_MODELS.items():
            filename = event_name.replace(".", "-") + ".v1.schema.json"
            self.assertEqual(
                json.loads((event_directory / filename).read_text()),
                model.model_json_schema(),
            )

    def test_runtime_fixture_rejects_missing_action_transition(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        del fixture["frames"][0]["next_frame"]["action.key.move"]
        with self.assertRaises(ValidationError):
            DeterministicRuntimeFixture.model_validate(fixture)

    def test_runtime_fixture_rejects_duplicate_goal_and_producer_sequence(self):
        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][0]["goals"].append(fixture["frames"][0]["goals"][0])
        with self.assertRaises(ValidationError):
            DeterministicRuntimeFixture.model_validate(fixture)

        fixture = load_json("find-my-way-home-after.runtime.json")
        fixture["frames"][0]["telemetry_sequence"] = 0
        with self.assertRaises(ValidationError):
            DeterministicRuntimeFixture.model_validate(fixture)

    def test_test_case_requires_at_least_one_unique_goal(self):
        payload = load_json("find-my-way-home-key-door.test-case.json")
        payload["goals"] = []
        with self.assertRaises(ValidationError):
            TestCase.model_validate(payload)

    def test_observation_rejects_duplicate_action_ids(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-observation"
        )
        payload = run.steps[0].observation.model_dump(mode="python")
        payload["available_actions"].append(payload["available_actions"][0])
        with self.assertRaises(ValidationError):
            Observation.model_validate(payload)

    def test_step_rejects_unadvertised_action_and_false_progress(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-step"
        )
        payload = run.steps[0].model_dump(mode="python")
        payload["selected_action"]["label"] = "tampered action"
        with self.assertRaises(ValidationError):
            PlaytestStep.model_validate(payload)

        payload = run.steps[0].model_dump(mode="python")
        payload["progress"][0]["value"] = 0.123
        with self.assertRaises(ValidationError):
            PlaytestStep.model_validate(payload)

    def test_evidence_rejects_artifact_mode_mismatch(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-evidence"
        )
        payload = run.steps[0].evidence.model_dump(mode="python")
        payload["artifacts"][0]["execution_mode"] = ExecutionMode.LIVE
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_evidence_rejects_empty_path_and_unowned_screenshot(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-evidence-relations"
        )
        payload = run.steps[0].evidence.model_dump(mode="python")
        payload["trajectory"] = []
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

        payload = run.steps[0].evidence.model_dump(mode="python")
        payload["camera"]["screenshot_artifact_id"] = "artifact.not-owned"
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_step_and_issue_reject_false_restoration_geometry(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.schema-restoration"
        )
        step_payload = run.steps[0].model_dump(mode="python")
        step_payload["evidence"]["camera"]["camera_id"] = "camera.unrelated"
        with self.assertRaises(ValidationError):
            PlaytestStep.model_validate(step_payload)

        issue_payload = run.issues[0].model_dump(mode="python")
        issue_payload["restoration"]["trajectory"][-1]["position"]["x"] += 1
        with self.assertRaises(ValidationError):
            Issue.model_validate(issue_payload)

    def test_run_request_rejects_non_executable_truth_modes(self):
        adapter_run, adapter, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-request-source"
        )
        with self.assertRaises(ValidationError):
            RunRequest(
                run_id="run.schema-planned",
                test_case=adapter_run.test_case,
                build=adapter.build,
                execution_mode=ExecutionMode.PLANNED,
            )

    def test_run_identifier_limit_reserves_space_for_derived_ids(self):
        run, adapter, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-id-source"
        )
        with self.assertRaises(ValidationError):
            RunRequest(
                run_id="r" * 97,
                test_case=run.test_case,
                build=adapter.build,
                execution_mode=ExecutionMode.MOCK,
            )

    def test_run_contract_rejects_cross_run_step_identity(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-identity"
        )
        payload = run.model_dump(mode="python")
        payload["run_id"] = "run.schema-other"
        with self.assertRaises(ValidationError):
            PlaytestRun.model_validate(payload)

    def test_run_contract_rejects_issue_evidence_not_owned_by_run(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.schema-issue-evidence"
        )
        payload = run.model_dump(mode="python")
        payload["issues"][0]["evidence"]["build_id"] = "build.unrelated"
        with self.assertRaises(ValidationError):
            PlaytestRun.model_validate(payload)

    def test_run_contract_binds_artifacts_and_logs_to_the_run(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-provenance"
        )
        payload = run.model_dump(mode="python")
        payload["steps"][0]["evidence"]["artifacts"][0][
            "source_project_id"
        ] = "project.unrelated"
        with self.assertRaises(ValidationError):
            PlaytestRun.model_validate(payload)

        payload = run.model_dump(mode="python")
        payload["adapter_logs"] = []
        with self.assertRaises(ValidationError):
            PlaytestRun.model_validate(payload)

    def test_fixture_source_candidates_resolve_to_versioned_catalog_records(self):
        catalog_path = MODULE_ROOT / "contracts" / "examples" / "source-catalog.v1.json"
        catalog = SourceCatalog.model_validate(
            json.loads(catalog_path.read_text(encoding="utf-8"))
        )
        for filename in (
            "find-my-way-home-before.runtime.json",
            "find-my-way-home-after.runtime.json",
            "warehouse-escape.runtime.json",
        ):
            fixture = DeterministicRuntimeFixture.model_validate(load_json(filename))
            for candidate in fixture.source_candidates:
                relative_path, fragment = candidate.source_record_uri.split("#", 1)
                self.assertEqual(MODULE_ROOT / relative_path, catalog_path)
                record = catalog.records[fragment]
                self.assertEqual(record.source_record_id, candidate.source_record_id)
                self.assertEqual(record.project_id, fixture.build.project_id)
                self.assertEqual(record.build_id, fixture.build.build_id)
                self.assertEqual(record.source_version, fixture.build.version)
                self.assertEqual(record.target_type, candidate.target_type)
                self.assertEqual(record.target_id, candidate.target_id)
                self.assertEqual(record.sceneops_id, candidate.sceneops_id)
                self.assertEqual(record.locator, candidate.locator)
                self.assertEqual(record.owning_module, candidate.owning_module)

    def test_run_contract_rejects_contradictory_lifecycle_state(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-after.runtime.json", "run.schema-lifecycle"
        )
        payload = run.model_dump(mode="python")
        payload["status"] = "running"
        with self.assertRaises(ValidationError):
            PlaytestRun.model_validate(payload)

        payload = run.model_dump(mode="python")
        payload["final_goal_progress"][0]["state"] = "pending"
        with self.assertRaises(ValidationError):
            PlaytestRun.model_validate(payload)

        failed, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.schema-failed-lifecycle"
        )
        payload = failed.model_dump(mode="python")
        payload["failure"] = None
        with self.assertRaises(ValidationError):
            PlaytestRun.model_validate(payload)

    def test_resolved_backpin_requires_target_and_resolved_event_status(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.schema-backpin-event"
        )
        issue = next(item for item in run.issues if item.backpin.status == "resolved")
        payload = issue.backpin.model_dump(mode="python")
        payload["target_id"] = None
        with self.assertRaises(ValidationError):
            Backpin.model_validate(payload)

        payload = issue.backpin.model_dump(mode="python")
        payload["source_record_uri"] = (
            "contracts/examples/source-catalog.v1.json#source-record.unrelated"
        )
        with self.assertRaises(ValidationError):
            Backpin.model_validate(payload)

        payload = issue.backpin.model_dump(mode="python")
        payload["status"] = "unresolved"
        event = {
            "event_id": "event.backpin.invalid-status",
            "occurred_at": FIXED_NOW,
            "project_id": run.test_case.project_id,
            "correlation_id": "correlation.backpin.invalid-status",
            "causation_id": "causation.backpin.invalid-status",
            "actor": {"type": "system", "id": "system.playtest"},
            "mode": run.execution_mode,
            "payload": {
                "issue_id": issue.issue_id,
                "backpin": payload,
                "execution_mode": run.execution_mode,
            },
        }
        with self.assertRaises(ValidationError):
            PlaytestIssueBackpinResolvedEvent.model_validate(event)

    def test_failure_signal_producer_matches_recorded_detector_version(self):
        run, _, _, _ = run_fixture(
            "find-my-way-home-before.runtime.json", "run.schema-producer"
        )
        detector_signals = [
            signal
            for step in run.steps
            for signal in step.failure_signals
            if signal.producer_id == "ai-playtest.failure-detector"
        ]
        self.assertTrue(detector_signals)
        self.assertTrue(
            all(
                signal.producer_version == run.behavior_provenance.detector_version
                for signal in detector_signals
            )
        )


if __name__ == "__main__":
    unittest.main()
