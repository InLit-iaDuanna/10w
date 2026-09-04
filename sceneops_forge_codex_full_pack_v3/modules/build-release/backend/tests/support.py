from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from build_release.adapters import DeterministicMockDeploymentAdapter, StaticArtifactCatalog
from build_release.checksum import canonical_sha256
from build_release.enums import (
    ApprovalAction,
    ApprovalDecision,
    BuildProfile,
    DeploymentTarget,
    ExecutionMode,
    GateCategory,
    GateStatus,
    RunStatus,
)
from build_release.models_build import BuildManifest, BuildMatrix, BuildRun, BuildTarget
from build_release.models_common import (
    Approval,
    ApprovedChangeSet,
    ArtifactRef,
    GateEvidence,
    VersionBinding,
)
from build_release.models_release import PatchNote, ReleaseCandidate, ReleaseGate
from build_release.repository import InMemoryReleaseRepository
from build_release.requests import (
    CandidateApprovalRequest,
    CreateCandidateRequest,
    GeneratePatchNoteRequest,
    RecordBuildRequest,
)
from build_release.service import BuildReleaseService


UTC = timezone.utc
BASE_TIME = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)


class SteppingClock:
    def __init__(self, current: datetime = BASE_TIME) -> None:
        self.current = current

    def now(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        return value


@dataclass
class BuildPair:
    matrix: BuildMatrix
    runs: List[BuildRun]
    manifests: List[BuildManifest]
    gates: List[ReleaseGate]
    change_sets: List[ApprovedChangeSet]

    @property
    def artifacts(self):
        return [
            artifact
            for manifest in self.manifests
            for artifact in [*manifest.artifacts, *manifest.test_evidence]
        ]


def make_service(fail_attempts: int = 0):
    repository = InMemoryReleaseRepository()
    catalog = StaticArtifactCatalog({})
    adapter = DeterministicMockDeploymentAdapter(fail_attempts=fail_attempts)
    clock = SteppingClock()
    service = BuildReleaseService(
        repository,
        catalog,
        {
            DeploymentTarget.LOCAL: adapter,
            DeploymentTarget.JUDGE: adapter,
        },
        clock,
    )
    return service, catalog, adapter, clock


def make_build_pair(
    slug: str,
    *,
    project_id: str = "project.remember-home",
    game_id: str = "game.remember-home",
    commit: str = "a" * 40,
    profile: BuildProfile = BuildProfile.QA,
    mode: ExecutionMode = ExecutionMode.MOCK,
    dirty: bool = False,
    output_seed: str = "player-output",
) -> BuildPair:
    target_id = f"target.{game_id}.{profile.value}"
    matrix = BuildMatrix(
        matrix_id=f"matrix.{slug}",
        project_id=project_id,
        game_id=game_id,
        source_commit=commit,
        targets=[
            BuildTarget(
                target_id=f"target.{game_id}.{item.value}",
                profile=item,
                platform="macos",
                architecture="arm64",
                variant="default",
                settings={"development_build": item == BuildProfile.DEVELOPMENT},
            )
            for item in BuildProfile
        ],
        created_at=BASE_TIME,
    )
    manifests: List[BuildManifest] = []
    runs: List[BuildRun] = []
    gate_evidence: List[GateEvidence] = []
    output_checksum = canonical_sha256({"fixture": output_seed})
    for label in ("a", "b"):
        run_id = f"run.{slug}.{label}"
        evidence = [
            GateEvidence(
                artifact_id=f"evidence.{slug}.{label}.{category.value}",
                project_id=project_id,
                game_id=game_id,
                build_run_id=run_id,
                artifact_type="gate_evidence",
                version="1",
                uri=f"{slug}/{label}/{category.value}.json",
                checksum=canonical_sha256(
                    {"slug": slug, "category": category.value, "result": "passed"}
                ),
                size_bytes=128,
                source_commit=commit,
                mode=mode,
                created_at=BASE_TIME,
                category=category,
                result=GateStatus.PASSED,
                summary=f"{category.value} fixture passed",
            )
            for category in GateCategory
        ]
        artifact = ArtifactRef(
            artifact_id=f"artifact.{slug}.{label}",
            project_id=project_id,
            game_id=game_id,
            build_run_id=run_id,
            artifact_type="unity_player",
            version="1",
            uri=f"{slug}/{label}/player.bin",
            checksum=output_checksum,
            size_bytes=512,
            source_commit=commit,
            mode=mode,
            created_at=BASE_TIME,
        )
        manifest = BuildManifest.create(
            manifest_id=f"manifest.{slug}.{label}",
            build_run_id=run_id,
            matrix_id=matrix.matrix_id,
            target_id=target_id,
            target_definition=next(
                item for item in matrix.targets if item.target_id == target_id
            ),
            project_id=project_id,
            game_id=game_id,
            profile=profile,
            mode=mode,
            source_commit=commit,
            source_identity=f"git:sha1:{commit}",
            source_dirty=dirty,
            module_catalog={"build-release": "0.1.0", "engine-unity": "0.1.0"},
            project_bible_version="bible-v1",
            project_bible_checksum=canonical_sha256({"bible": slug, "version": 1}),
            asset_versions={
                "asset.door": VersionBinding(
                    version_id="v3",
                    checksum=canonical_sha256({"asset": "door", "version": 3}),
                ),
                "asset.key": VersionBinding(
                    version_id="v2",
                    checksum=canonical_sha256({"asset": "key", "version": 2}),
                ),
            },
            scene_snapshots={
                "scene.home": VersionBinding(
                    version_id="snapshot-v4",
                    checksum=canonical_sha256({"scene": "home", "version": 4}),
                )
            },
            unity_version="6000.0.15f1",
            unity_packages={"com.sceneops.runtime": "0.1.0"},
            build_recipe_version="recipe-v1",
            settings={"scripting_backend": "IL2CPP", "configuration": "QA"},
            test_evidence=evidence,
            artifacts=[artifact],
            created_at=BASE_TIME,
        )
        run = BuildRun(
            build_run_id=run_id,
            matrix_id=matrix.matrix_id,
            target_id=target_id,
            project_id=project_id,
            game_id=game_id,
            profile=profile,
            source_commit=commit,
            status=RunStatus.SUCCEEDED,
            mode=mode,
            attempt=1,
            started_at=BASE_TIME,
            finished_at=BASE_TIME + timedelta(minutes=1),
            manifest_id=manifest.manifest_id,
        )
        manifests.append(manifest)
        runs.append(run)
        if label == "a":
            gate_evidence = evidence
    gates = [
        ReleaseGate(
            gate_id=f"gate.{slug}.{evidence.category.value}",
            category=evidence.category,
            status=GateStatus.PASSED,
            blocking=True,
            source_commit=commit,
            evidence=[evidence],
            mode=mode,
            summary=f"{evidence.category.value} gate passed",
            evaluated_at=BASE_TIME + timedelta(minutes=2),
        )
        for evidence in gate_evidence
    ]
    changes = [
        ApprovedChangeSet(
            change_set_id=f"changeset.{slug}.door",
            project_id=project_id,
            game_id=game_id,
            included_source_commit=commit,
            title="修复门锁交互",
            summary="门锁现在只在持有钥匙时打开。",
            approved=True,
            approval_ids=[f"approval.{slug}.change"],
            approved_at=BASE_TIME - timedelta(minutes=5),
        )
    ]
    return BuildPair(matrix, runs, manifests, gates, changes)


def record_pair(service: BuildReleaseService, catalog: StaticArtifactCatalog, pair: BuildPair) -> None:
    for artifact in pair.artifacts:
        catalog.register_matching(artifact)
    for run, manifest in zip(pair.runs, pair.manifests):
        service.record_build(RecordBuildRequest(matrix=pair.matrix, run=run, manifest=manifest))


def create_ready_candidate(
    service: BuildReleaseService,
    pair: BuildPair,
    candidate_id: str,
) -> ReleaseCandidate:
    candidate = service.create_candidate(
        CreateCandidateRequest(
            candidate_id=candidate_id,
            manifest_ids=[item.manifest_id for item in pair.manifests],
            gates=pair.gates,
            approved_change_set_ids=[item.change_set_id for item in pair.change_sets],
        )
    )
    for index, role in enumerate(candidate.required_approval_roles):
        candidate = service.approve_candidate(
            CandidateApprovalRequest(
                candidate_id=candidate.candidate_id,
                approval=Approval(
                    approval_id=f"approval.{candidate_id}.{index}",
                    action=ApprovalAction.CREATE_CANDIDATE,
                    target_id=candidate.candidate_id,
                    scope_fingerprint=candidate.scope_fingerprint,
                    role=role,
                    actor_id=f"user.{role}",
                    decision=ApprovalDecision.APPROVED,
                    rationale="Fixture approval for deterministic module testing.",
                    decided_at=BASE_TIME,
                ),
            )
        )
    return candidate


def create_patch_note(
    service: BuildReleaseService,
    pair: BuildPair,
    candidate: ReleaseCandidate,
    patch_note_id: str,
) -> PatchNote:
    return service.generate_patch_note(
        GeneratePatchNoteRequest(
            patch_note_id=patch_note_id,
            candidate_id=candidate.candidate_id,
            title=f"{candidate.game_id} 发布说明",
            change_sets=pair.change_sets,
        )
    )
