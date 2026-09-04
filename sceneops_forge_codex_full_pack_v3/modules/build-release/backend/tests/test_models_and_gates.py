from __future__ import annotations

import unittest

from pydantic import ValidationError

from build_release.adapters import StaticArtifactCatalog
from build_release.checksum import canonical_sha256
from build_release.enums import (
    BuildProfile,
    CandidateStatus,
    ExecutionMode,
    GateCategory,
    GateStatus,
)
from build_release.errors import PolicyError
from build_release.models_build import BuildManifest
from build_release.models_common import ArtifactRef
from build_release.ports import ArtifactInspection
from build_release.requests import CreateCandidateRequest, RecordBuildRequest

from support import (
    BASE_TIME,
    create_ready_candidate,
    make_build_pair,
    make_service,
    record_pair,
)


class BuildManifestTests(unittest.TestCase):
    def test_default_matrix_supports_all_profiles(self) -> None:
        pair = make_build_pair("profiles")
        self.assertEqual(pair.matrix.supported_profiles, set(BuildProfile))

    def test_manifest_is_complete_and_checksum_is_verified(self) -> None:
        manifest = make_build_pair("complete").manifests[0]
        self.assertEqual(len(manifest.manifest_checksum), 64)
        self.assertTrue(manifest.module_catalog)
        self.assertTrue(manifest.asset_versions)
        self.assertTrue(manifest.scene_snapshots)
        self.assertTrue(manifest.unity_packages)
        self.assertTrue(manifest.test_evidence)
        self.assertTrue(manifest.artifacts)

        payload = manifest.model_dump(mode="json")
        payload["unity_version"] = "tampered"
        with self.assertRaisesRegex(ValidationError, "manifest_checksum"):
            BuildManifest.model_validate(payload)

        with self.assertRaises(ValidationError):
            manifest.source_dirty = True

    def test_source_identity_names_the_exact_git_object_and_algorithm(self) -> None:
        manifest = make_build_pair("source-identity").manifests[0]
        payload = manifest.model_dump(mode="json")
        payload["source_identity"] = f"git:sha1:{'b' * 40}"
        payload["manifest_checksum"] = "0" * 64
        with self.assertRaisesRegex(ValidationError, "exact Git object ID"):
            BuildManifest.model_validate(
                payload, context={"allow_checksum_placeholder": True}
            )

    def test_cached_artifact_requires_prior_live_provenance(self) -> None:
        original = make_build_pair("cached-origin").manifests[0].artifacts[0]
        payload = original.model_dump()
        payload["mode"] = ExecutionMode.CACHED
        with self.assertRaisesRegex(ValidationError, "prior live-run provenance"):
            ArtifactRef.model_validate(payload)

        payload["origin_live_run_id"] = "run.original.live"
        payload["origin_live_artifact_id"] = "artifact.original.live"
        cached = ArtifactRef.model_validate(payload)
        self.assertEqual(cached.mode, ExecutionMode.CACHED)

    def test_missing_artifact_prevents_build_recording(self) -> None:
        service, catalog, _, _ = make_service()
        pair = make_build_pair("missing-record")
        for artifact in pair.artifacts:
            catalog.register_matching(artifact)
        missing = pair.manifests[0].artifacts[0]
        catalog.register_inspection(
            ArtifactInspection(
                artifact_id=missing.artifact_id,
                available=False,
                checksum_matches=False,
                size_matches=False,
                reason="Fixture artifact is missing.",
            )
        )
        with self.assertRaisesRegex(PolicyError, "missing or corrupt"):
            service.record_build(
                RecordBuildRequest(
                    matrix=pair.matrix,
                    run=pair.runs[0],
                    manifest=pair.manifests[0],
                )
            )

    def test_manifest_must_be_bound_to_the_recorded_build_run(self) -> None:
        service, catalog, _, _ = make_service()
        pair = make_build_pair("run-binding")
        for artifact in pair.artifacts:
            catalog.register_matching(artifact)
        mismatched_run = pair.runs[0].model_copy(
            update={"build_run_id": "run.run-binding.other"}
        )

        with self.assertRaisesRegex(PolicyError, "does not match its run"):
            service.record_build(
                RecordBuildRequest(
                    matrix=pair.matrix,
                    run=mismatched_run,
                    manifest=pair.manifests[0],
                )
            )

    def test_cached_artifact_requires_a_matching_catalogued_live_record(self) -> None:
        live = make_build_pair(
            "cached-catalog", mode=ExecutionMode.LIVE
        ).manifests[0].artifacts[0]
        cached = ArtifactRef.model_validate(
            {
                **live.model_dump(),
                "artifact_id": "artifact.cached-catalog.replay",
                "mode": ExecutionMode.CACHED,
                "origin_live_run_id": live.build_run_id,
                "origin_live_artifact_id": live.artifact_id,
            }
        )
        catalog = StaticArtifactCatalog({})
        catalog.register_matching(cached)
        self.assertFalse(catalog.inspect(cached).available)

        catalog.register_matching(live)
        self.assertTrue(catalog.inspect(cached).available)

    def test_live_build_recording_is_blocked_without_trusted_source_authority(self) -> None:
        service, catalog, _, _ = make_service()
        pair = make_build_pair("live-authority", mode=ExecutionMode.LIVE)
        for artifact in pair.artifacts:
            catalog.register_matching(artifact)

        with self.assertRaisesRegex(PolicyError, "provenance are not configured"):
            service.record_build(
                RecordBuildRequest(
                    matrix=pair.matrix,
                    run=pair.runs[0],
                    manifest=pair.manifests[0],
                )
            )

    def test_manifest_binds_full_matrix_target_definition(self) -> None:
        service, catalog, _, _ = make_service()
        pair = make_build_pair("target-definition")
        for artifact in pair.artifacts:
            catalog.register_matching(artifact)
        changed_target = pair.manifests[0].target_definition.model_copy(
            update={"architecture": "x86_64"}
        )
        payload = pair.manifests[0].model_dump(exclude={"manifest_checksum"})
        payload["target_definition"] = changed_target
        changed_manifest = BuildManifest.create(**payload)

        with self.assertRaisesRegex(PolicyError, "matrix target"):
            service.record_build(
                RecordBuildRequest(
                    matrix=pair.matrix,
                    run=pair.runs[0],
                    manifest=changed_manifest,
                )
            )


class ReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service, self.catalog, _, _ = make_service()
        self.pair = make_build_pair("gates")
        record_pair(self.service, self.catalog, self.pair)

    def test_passing_gates_and_exact_approval_create_ready_candidate(self) -> None:
        candidate = create_ready_candidate(
            self.service, self.pair, "candidate.gates.ready"
        )
        self.assertEqual(candidate.status, CandidateStatus.READY)
        self.assertTrue(candidate.gate_report.can_release)
        self.assertEqual(
            set(candidate.gate_report.passed_categories), set(GateCategory)
        )
        self.assertEqual(candidate.mode, ExecutionMode.MOCK)

    def test_failed_blocking_gate_prevents_release(self) -> None:
        failed_gate = self.pair.gates[0].model_copy(
            update={"status": GateStatus.FAILED, "summary": "Asset gate failed"}
        )
        request = CreateCandidateRequest(
            candidate_id="candidate.gates.failed",
            manifest_ids=[item.manifest_id for item in self.pair.manifests],
            gates=[failed_gate, *self.pair.gates[1:]],
            approved_change_set_ids=[item.change_set_id for item in self.pair.change_sets],
        )
        candidate = self.service.create_candidate(request)
        self.assertEqual(candidate.status, CandidateStatus.BLOCKED)
        self.assertFalse(candidate.gate_report.can_release)
        self.assertIn("GATE:GATE_NOT_PASSED", candidate.blockers)

    def test_required_gate_cannot_be_downgraded_to_non_blocking(self) -> None:
        downgraded_gate = self.pair.gates[0].model_copy(update={"blocking": False})
        request = CreateCandidateRequest(
            candidate_id="candidate.gates.downgraded",
            manifest_ids=[item.manifest_id for item in self.pair.manifests],
            gates=[downgraded_gate, *self.pair.gates[1:]],
            approved_change_set_ids=[item.change_set_id for item in self.pair.change_sets],
        )

        candidate = self.service.create_candidate(request)

        self.assertEqual(candidate.status, CandidateStatus.BLOCKED)
        self.assertIn("GATE:REQUIRED_GATE_NON_BLOCKING", candidate.blockers)

    def test_missing_gate_and_stale_gate_both_fail_closed(self) -> None:
        missing_request = CreateCandidateRequest(
            candidate_id="candidate.gates.missing",
            manifest_ids=[item.manifest_id for item in self.pair.manifests],
            gates=self.pair.gates[:-1],
            approved_change_set_ids=[item.change_set_id for item in self.pair.change_sets],
        )
        missing = self.service.create_candidate(missing_request)
        self.assertIn("GATE:MISSING_GATE", missing.blockers)

        other_pair = make_build_pair("stale-source", commit="b" * 40)
        stale_payload = self.pair.gates[0].model_dump()
        stale_payload["source_commit"] = other_pair.manifests[0].source_commit
        stale_payload["evidence"][0]["source_commit"] = other_pair.manifests[0].source_commit
        from build_release.models_release import ReleaseGate

        stale_gate = ReleaseGate.model_validate(stale_payload)
        stale_request = CreateCandidateRequest(
            candidate_id="candidate.gates.stale",
            manifest_ids=[item.manifest_id for item in self.pair.manifests],
            gates=[stale_gate, *self.pair.gates[1:]],
            approved_change_set_ids=[item.change_set_id for item in self.pair.change_sets],
        )
        stale = self.service.create_candidate(stale_request)
        self.assertIn("GATE:STALE_GATE", stale.blockers)

    def test_candidate_cannot_inject_gate_evidence_after_build_recording(self) -> None:
        injected_evidence = self.pair.gates[0].evidence[0].model_copy(
            update={"artifact_id": "evidence.gates.injected"}
        )
        injected_gate = self.pair.gates[0].model_copy(
            update={"evidence": [injected_evidence]}
        )
        request = CreateCandidateRequest(
            candidate_id="candidate.gates.injected",
            manifest_ids=[item.manifest_id for item in self.pair.manifests],
            gates=[injected_gate, *self.pair.gates[1:]],
            approved_change_set_ids=[item.change_set_id for item in self.pair.change_sets],
        )

        candidate = self.service.create_candidate(request)

        self.assertEqual(candidate.status, CandidateStatus.BLOCKED)
        self.assertIn("GATE:UNBOUND_GATE_EVIDENCE", candidate.blockers)

    def test_dirty_source_and_mock_release_candidate_are_blocked(self) -> None:
        service, catalog, _, _ = make_service()
        dirty = make_build_pair("dirty", dirty=True)
        record_pair(service, catalog, dirty)
        candidate = service.create_candidate(
            CreateCandidateRequest(
                candidate_id="candidate.dirty.blocked",
                manifest_ids=[item.manifest_id for item in dirty.manifests],
                gates=dirty.gates,
                approved_change_set_ids=[item.change_set_id for item in dirty.change_sets],
            )
        )
        self.assertEqual(candidate.status, CandidateStatus.BLOCKED)
        self.assertTrue(any(item.startswith("DIRTY_SOURCE") for item in candidate.blockers))

        service, catalog, _, _ = make_service()
        release = make_build_pair(
            "release-mock", profile=BuildProfile.RELEASE_CANDIDATE
        )
        record_pair(service, catalog, release)
        candidate = service.create_candidate(
            CreateCandidateRequest(
                candidate_id="candidate.release.mock",
                manifest_ids=[item.manifest_id for item in release.manifests],
                gates=release.gates,
                approved_change_set_ids=[item.change_set_id for item in release.change_sets],
            )
        )
        self.assertEqual(candidate.status, CandidateStatus.BLOCKED)
        self.assertIn("GATE:EXECUTION_MODE_NOT_ALLOWED", candidate.blockers)

    def test_cross_game_reproducibility_pair_is_rejected(self) -> None:
        warehouse = make_build_pair(
            "warehouse",
            project_id="project.warehouse-escape",
            game_id="game.warehouse-escape",
        )
        record_pair(self.service, self.catalog, warehouse)
        with self.assertRaisesRegex(PolicyError, "share project, game"):
            self.service.create_candidate(
                CreateCandidateRequest(
                    candidate_id="candidate.cross-game",
                    manifest_ids=[
                        self.pair.manifests[0].manifest_id,
                        warehouse.manifests[1].manifest_id,
                    ],
                    gates=self.pair.gates,
                    approved_change_set_ids=[],
                )
            )

    def test_build_a_b_output_mismatch_blocks_candidate(self) -> None:
        service, catalog, _, _ = make_service()
        pair = make_build_pair("non-reproducible")
        changed_artifact = pair.manifests[1].artifacts[0].model_copy(
            update={"checksum": canonical_sha256({"different": "player-bytes"})}
        )
        payload = pair.manifests[1].model_dump(exclude={"manifest_checksum"})
        payload["artifacts"] = [changed_artifact]
        pair.manifests[1] = BuildManifest.create(**payload)
        record_pair(service, catalog, pair)
        candidate = service.create_candidate(
            CreateCandidateRequest(
                candidate_id="candidate.non-reproducible",
                manifest_ids=[item.manifest_id for item in pair.manifests],
                gates=pair.gates,
                approved_change_set_ids=[item.change_set_id for item in pair.change_sets],
            )
        )
        self.assertEqual(candidate.status, CandidateStatus.BLOCKED)
        self.assertIn("BUILD_OUTPUTS_NOT_REPRODUCIBLE", candidate.blockers)


if __name__ == "__main__":
    unittest.main()
