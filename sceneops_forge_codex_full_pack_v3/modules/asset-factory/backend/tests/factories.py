from datetime import datetime, timezone
from pathlib import Path

from asset_factory import (
    AssetApprovalRecord,
    AssetChangeSet,
    AssetPipelineService,
    ChangeSetState,
    InMemoryAssetApprovalAuthority,
    InMemoryFinalizedCandidateStore,
    InMemoryProjectRootRegistry,
    InMemoryRequestLedger,
    PipelineRequest,
    ProjectArtifactVerifier,
    canonical_command_scope,
    RetryPolicy,
    RiskLevel,
)
from asset_factory.workflow import build_workflow_plan
from asset_library import (
    AssetLibraryService,
    AssetObjectIdentity,
    AssetRecord,
    AssetSpec,
    ExecutionMode,
    InMemoryAssetRepository,
    SourceAsset,
    Vector3Meters,
)


NOW = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)


def make_record_and_request(
    root: Path,
    *,
    slug: str = "hero_key",
    display_name: str = "归家钥匙",
    project_id: str = "prj_remember_home",
    approved: bool = True,
    dry_run: bool = False,
    run_id: str = "run_hero_key_1",
    idempotency_key: str = "idem_hero_key_1",
    requested_mode: ExecutionMode = ExecutionMode.MOCK,
    triangle_budget: int = 1000,
    requires_lods: bool = True,
    retry_of_run_id=None,
):
    source_path = Path("Assets") / (slug.replace("_", "-") + ".blend")
    absolute_source = root / source_path
    absolute_source.parent.mkdir(parents=True, exist_ok=True)
    absolute_source.write_bytes(("deterministic source " + slug).encode("utf-8"))
    asset_id = "ast_" + slug
    source_asset_id = "src_" + slug
    sceneops_id = "sop_" + slug + "_mesh"
    spec = AssetSpec(
        asset_spec_id="aspec_" + slug,
        project_id=project_id,
        asset_id=asset_id,
        display_name=display_name,
        category="prop",
        description="Deterministic task 07 fixture",
        intended_use="gameplay interaction",
        target_dimensions_m=Vector3Meters(x=0.04, y=0.01, z=0.1),
        triangle_budget=triangle_budget,
        requires_lods=requires_lods,
        requires_collider=True,
        created_at=NOW,
    )
    source = SourceAsset(
        source_asset_id=source_asset_id,
        asset_id=asset_id,
        project_id=project_id,
        project_relative_path=source_path.as_posix(),
        format="blend",
        source_version="1",
        source_commit="commit_fixture",
        source_kind="imported",
        license_name="CC0-1.0",
        origin_uri="fixture://" + slug,
        imported_at=NOW,
    )
    identity = AssetObjectIdentity(
        sceneops_id=sceneops_id,
        source_asset_id=source_asset_id,
        display_name="FixtureMesh",
        source_object_locator="Collection/FixtureMesh",
    )
    change_set = AssetChangeSet(
        change_set_id="chg_" + slug,
        base_version="source:1",
        project_id=project_id,
        target_object_ids=[sceneops_id],
        previous_values={"source": source_path.as_posix()},
        proposed_values={"outputs": ["glb", "fbx"], "collider": "convex_hull"},
        rationale="Create an engine-ready asset version.",
        expected_result="Validated GLB and FBX with stable identity.",
        impact_scope=[asset_id],
        risk=RiskLevel.MEDIUM,
        validation_plan=["geometry", "uv_material", "identity"],
        rollback_plan=["restore Blender snapshot"],
        approval_requirements=["asset owner"],
        state=ChangeSetState.APPROVED if approved else ChangeSetState.PROPOSED,
        approval_id="apr_" + slug if approved else None,
        approved_by="usr_asset_owner" if approved else None,
        approved_at=NOW if approved else None,
    )
    record = AssetRecord(spec=spec, source=source, source_objects=[identity])
    request = PipelineRequest(
        pipeline_run_id=run_id,
        idempotency_key=idempotency_key,
        retry_of_run_id=retry_of_run_id,
        spec=spec,
        source=source,
        source_object_identities=[identity],
        asset_version_id="aver_%s_1" % slug,
        asset_version_number=1,
        output_directory="Published/" + slug.replace("_", "-"),
        change_set=change_set,
        requested_mode=requested_mode,
        dry_run=dry_run,
        timeout_seconds=10,
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=0),
        creator="usr_asset_artist",
    )
    return record, request


def make_pipeline_service(root: Path, record, request):
    approval_records = []
    if request.change_set.approval_id:
        approval_records.append(
            AssetApprovalRecord(
                approval_id=request.change_set.approval_id,
                change_set_id=request.change_set.change_set_id,
                project_id=request.change_set.project_id,
                asset_id=request.spec.asset_id,
                asset_version_id=request.asset_version_id,
                approved_by=request.change_set.approved_by,
                approved_at=request.change_set.approved_at,
                change_set=request.change_set,
                command_scope=canonical_command_scope(
                    (
                        command
                        for plan in build_workflow_plan(request, preview=False)
                        for command in plan.commands
                    ),
                    request.pipeline_run_id,
                ),
            )
        )
    authority = InMemoryAssetApprovalAuthority(approval_records)
    roots = InMemoryProjectRootRegistry({request.spec.project_id: root})
    candidates = InMemoryFinalizedCandidateStore()
    catalog = AssetLibraryService(
        InMemoryAssetRepository([record]),
        approval_verifier=authority,
        artifact_verifier=ProjectArtifactVerifier(roots),
        candidate_resolver=candidates,
        clock=lambda: NOW,
    )
    service = AssetPipelineService(
        catalog,
        approval_authority=authority,
        project_roots=roots,
        candidate_store=candidates,
        request_ledger=InMemoryRequestLedger(),
        clock=lambda: NOW,
    )
    return service, catalog
