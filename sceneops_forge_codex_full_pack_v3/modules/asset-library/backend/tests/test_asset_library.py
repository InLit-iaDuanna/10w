import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

from asset_library import (
    ArtifactOutput,
    ArtifactProvenance,
    AssetLibraryService,
    AssetObjectIdentity,
    AssetRecord,
    AssetSearchFilter,
    AssetSpec,
    AssetVersion,
    ExecutionMode,
    GateStatus,
    GeometryMetrics,
    InMemoryAssetRepository,
    PublicationBlockedError,
    PublicationRequest,
    PublicationStatus,
    QualityGate,
    SourceAsset,
    UnityStatus,
    UsageReference,
    Vector3Meters,
    create_router,
)


NOW = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
CHECKSUM = "a" * 64


def build_record(candidate_gate_status=GateStatus.PASSED):
    dimensions = Vector3Meters(x=0.04, y=0.01, z=0.1)
    spec = AssetSpec(
        asset_spec_id="aspec_hero_key",
        project_id="prj_remember_home",
        asset_id="ast_hero_key",
        display_name="归家钥匙",
        category="prop",
        intended_use="unlock home entrance",
        target_dimensions_m=dimensions,
        triangle_budget=1000,
        created_at=NOW,
    )
    source = SourceAsset(
        source_asset_id="src_hero_key",
        asset_id=spec.asset_id,
        project_id=spec.project_id,
        project_relative_path="Assets/Props/hero-key.blend",
        format="blend",
        source_version="1",
        source_kind="imported",
        license_name="CC0-1.0",
        imported_at=NOW,
    )
    identity = AssetObjectIdentity(
        sceneops_id="sop_key_mesh",
        source_asset_id=source.source_asset_id,
        display_name="HeroKey",
        source_object_locator="Collection/HeroKey",
    )
    outputs = [
        ArtifactOutput(
            artifact_id="art_key_" + format_name,
            artifact_type="engine_asset",
            format=format_name,
            project_relative_path="Published/hero-key/v1/hero-key." + format_name,
            media_type=(
                "model/gltf-binary"
                if format_name == "glb"
                else "application/octet-stream"
            ),
            byte_size=128,
            sha256=CHECKSUM,
        )
        for format_name in ("glb", "fbx")
    ]
    provenance = [
        ArtifactProvenance(
            artifact_id=output.artifact_id,
            source_project=spec.project_id,
            source_version=source.source_version,
            related_sceneops_ids=[identity.sceneops_id],
            producing_module="asset-factory",
            tool_name="Blender",
            tool_version="4.3.0",
            adapter_version="0.1.0",
            recipe_version="asset-pipeline@1",
            creator="usr_artist",
            execution_mode=ExecutionMode.MOCK,
            timestamp=NOW,
            sha256=CHECKSUM,
            approval_state="approved",
        )
        for output in outputs
    ]
    candidate = AssetVersion(
        asset_version_id="aver_hero_key_1",
        asset_id=spec.asset_id,
        source_asset_id=source.source_asset_id,
        version=1,
        status=PublicationStatus.APPROVED,
        execution_mode=ExecutionMode.MOCK,
        metrics=GeometryMetrics(
            dimensions_m=dimensions,
            triangle_count=840,
            vertex_count=460,
            material_count=1,
            texture_count=2,
            has_uv=True,
            is_rigged=False,
            animation_names=[],
            lod_count=2,
            collider_kind="convex_hull",
        ),
        object_identities=[identity],
        outputs=outputs,
        quality_gates=[
            QualityGate(
                gate_id=gate_id,
                label=gate_id,
                status=candidate_gate_status,
                blocking=True,
                message="fixture result",
            )
            for gate_id in spec.required_gate_ids
        ],
        provenance=provenance,
        approval_id="apr_key",
        created_at=NOW,
    )
    return AssetRecord(spec=spec, source=source, source_objects=[identity]), candidate


class FixtureApprovalVerifier:
    def verify(self, request, candidate):
        if (
            request.change_set_id == "chg_key"
            and request.approval_id == "apr_key"
            and candidate.asset_version_id == "aver_hero_key_1"
        ):
            return []
        return ["fixture approval scope mismatch"]


class FixtureArtifactVerifier:
    def verify(self, project_id, artifact):
        if project_id == "prj_remember_home" and artifact.sha256 == CHECKSUM:
            return []
        return ["fixture artifact scope mismatch"]


class FixtureCandidateResolver:
    def __init__(self, candidate):
        self.candidate = candidate

    def resolve(self, request):
        if request.asset_version_id != self.candidate.asset_version_id:
            raise LookupError(request.asset_version_id)
        return self.candidate.model_copy(deep=True)


def build_service(record, candidate):
    return AssetLibraryService(
        InMemoryAssetRepository([record]),
        approval_verifier=FixtureApprovalVerifier(),
        artifact_verifier=FixtureArtifactVerifier(),
        candidate_resolver=FixtureCandidateResolver(candidate),
        clock=lambda: NOW,
    )


class AssetLibraryTests(unittest.TestCase):
    def test_manifest_and_public_router_register(self):
        module_root = Path(__file__).resolve().parents[2]
        manifest = yaml.safe_load((module_root / "module.yaml").read_text())
        self.assertEqual(manifest["id"], "asset-library")
        self.assertIn("asset.browser", manifest["contributes"]["editors"])
        record, _ = build_record()
        router = create_router(AssetLibraryService(InMemoryAssetRepository([record])))
        self.assertEqual(router.prefix, "/v1/assets")
        search_route = next(route for route in router.routes if route.path == "/v1/assets")
        query_names = {parameter.name for parameter in search_route.dependant.query_params}
        self.assertTrue(
            {"formats", "gate_status", "unity_status", "has_lod", "execution_modes"}
            .issubset(query_names)
        )

    def test_publish_success_preserves_origin_and_answers_usage_and_build(self):
        record, candidate = build_record()
        service = build_service(record, candidate)
        published = service.publish(
            PublicationRequest(
                asset_id=record.spec.asset_id,
                asset_version_id=candidate.asset_version_id,
                change_set_id="chg_key",
                approval_id="apr_key",
                approved_by="usr_release_owner",
            )
        )
        self.assertEqual(published.status, PublicationStatus.PUBLISHED)
        stored = service.get(record.spec.asset_id)
        usage = UsageReference(
            usage_id="use_key_hallway",
            asset_version_id=published.asset_version_id,
            project_id=record.spec.project_id,
            scene_id="scn_home_hallway",
            scene_instance_id="sinst_key_hallway",
            unity_prefab_id="prefab_hero_key",
            unity_status=UnityStatus.IMPORTED,
            build_ids=["bld_home_7"],
            first_seen_at=NOW,
        )
        service.register(stored.model_copy(update={"usage_references": [usage]}, deep=True))
        result = service.get(record.spec.asset_id)
        self.assertEqual(result.source.origin_uri, None)
        self.assertEqual(result.usage_references[0].scene_id, "scn_home_hallway")
        self.assertEqual(result.included_build_ids, ["bld_home_7"])

    def test_failed_blocking_gate_prevents_publication(self):
        record, candidate = build_record(GateStatus.FAILED)
        service = build_service(record, candidate)
        with self.assertRaises(PublicationBlockedError) as raised:
            service.publish(
                PublicationRequest(
                    asset_id=record.spec.asset_id,
                    asset_version_id=candidate.asset_version_id,
                    change_set_id="chg_key",
                    approval_id="apr_key",
                    approved_by="usr_release_owner",
                )
            )
        self.assertIn("blocking gates did not pass", str(raised.exception))
        self.assertEqual(service.get(record.spec.asset_id).versions, [])

    def test_catalog_asset_requirements_are_enforced_at_publication(self):
        record, candidate = build_record()
        record = record.model_copy(
            update={
                "spec": record.spec.model_copy(
                    update={"requires_rig": True}, deep=True
                )
            },
            deep=True,
        )
        service = build_service(record, candidate)
        with self.assertRaisesRegex(PublicationBlockedError, "requires a rig"):
            service.publish(
                PublicationRequest(
                    asset_id=record.spec.asset_id,
                    asset_version_id=candidate.asset_version_id,
                    change_set_id="chg_key",
                    approval_id="apr_key",
                    approved_by="usr_release_owner",
                )
            )

    def test_search_filters_full_asset_inspector_surface(self):
        record, candidate = build_record()
        usage = UsageReference(
            usage_id="use_key_hallway",
            asset_version_id=candidate.asset_version_id,
            project_id=record.spec.project_id,
            scene_id="scn_home_hallway",
            scene_instance_id="sinst_key_hallway",
            unity_status=UnityStatus.IMPORTED,
            build_ids=["bld_home_7"],
            first_seen_at=NOW,
        )
        record = record.model_copy(update={"versions": [candidate], "usage_references": [usage]}, deep=True)
        service = AssetLibraryService(InMemoryAssetRepository([record]))
        results = service.search(
            AssetSearchFilter(
                query="钥匙",
                formats=["glb"],
                gate_status=GateStatus.PASSED,
                unity_status=UnityStatus.IMPORTED,
                has_uv=True,
                rigged=False,
                has_animations=False,
                has_lod=True,
                has_collider=True,
                license_name="CC0-1.0",
                max_triangles=1000,
                execution_modes=[ExecutionMode.MOCK],
            )
        )
        self.assertEqual([item.spec.asset_id for item in results], ["ast_hero_key"])
        by_build = service.search(
            AssetSearchFilter(query="bld_home_7", has_ai_provenance=False)
        )
        self.assertEqual([item.spec.asset_id for item in by_build], ["ast_hero_key"])

    def test_identity_kinds_cannot_be_conflated(self):
        record, candidate = build_record()
        with self.assertRaisesRegex(ValueError, "identities must be distinct"):
            AssetRecord(
                spec=record.spec,
                source=record.source,
                source_objects=[
                    record.source_objects[0].model_copy(update={"sceneops_id": record.spec.asset_id})
                ],
                versions=[candidate],
            )
        with self.assertRaisesRegex(ValueError, "source-asset identities must be distinct"):
            AssetRecord(
                spec=record.spec,
                source=record.source.model_copy(
                    update={"source_asset_id": record.spec.asset_id}, deep=True
                ),
                source_objects=[
                    item.model_copy(
                        update={"source_asset_id": record.spec.asset_id}, deep=True
                    )
                    for item in record.source_objects
                ],
            )

        usage = UsageReference(
            usage_id="use_key_hallway",
            asset_version_id=candidate.asset_version_id,
            project_id=record.spec.project_id,
            scene_id="scn_home_hallway",
            scene_instance_id=record.spec.asset_id,
            unity_status=UnityStatus.NOT_IMPORTED,
            first_seen_at=NOW,
        )
        with self.assertRaisesRegex(ValueError, "scene-instance IDs must be distinct"):
            AssetRecord(
                spec=record.spec,
                source=record.source,
                source_objects=record.source_objects,
                versions=[candidate],
                usage_references=[usage],
            )

    def test_publication_defaults_fail_closed_without_trusted_verifiers(self):
        record, candidate = build_record()
        service = AssetLibraryService(InMemoryAssetRepository([record]))
        with self.assertRaisesRegex(
            PublicationBlockedError, "trusted finalized-run storage"
        ):
            service.publish(
                PublicationRequest(
                    asset_id=record.spec.asset_id,
                    asset_version_id=candidate.asset_version_id,
                    change_set_id="chg_key",
                    approval_id="apr_key",
                    approved_by="usr_release_owner",
                )
            )

    def test_publication_request_cannot_supply_its_own_candidate(self):
        record, candidate = build_record()
        with self.assertRaisesRegex(ValueError, "candidate"):
            PublicationRequest(
                asset_id=record.spec.asset_id,
                asset_version_id=candidate.asset_version_id,
                change_set_id="chg_key",
                approval_id="apr_key",
                approved_by="usr_release_owner",
                candidate=candidate,
            )


if __name__ == "__main__":
    unittest.main()
