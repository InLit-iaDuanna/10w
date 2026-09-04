"""Build intake, gate aggregation, candidate, and patch-note behavior."""

from __future__ import annotations

from typing import List, Sequence

from .checksum import canonical_sha256
from .enums import (
    ApprovalAction,
    ApprovalDecision,
    CandidateStatus,
    ExecutionMode,
    RunStatus,
)
from .errors import PolicyError
from .models_build import BuildManifest
from .models_release import (
    FeedbackLink,
    ReleaseCandidate,
    ReproducibilityEvidence,
)
from .policies import (
    aggregate_execution_mode,
    evaluate_release_gates,
    required_approval_roles,
)
from .ports import ArtifactCatalog, Clock, ReleaseAuthority
from .repository import InMemoryReleaseRepository
from .requests import (
    CandidateApprovalRequest,
    CreateCandidateRequest,
    RecordBuildRequest,
)


class CandidateService:
    def __init__(
        self,
        repository: InMemoryReleaseRepository,
        artifact_catalog: ArtifactCatalog,
        clock: Clock,
        authority: ReleaseAuthority,
    ) -> None:
        self.repository = repository
        self.artifact_catalog = artifact_catalog
        self.clock = clock
        self.authority = authority

    def record_build(self, request: RecordBuildRequest) -> BuildManifest:
        matrix, run, manifest = request.matrix, request.run, request.manifest
        target = next(
            (item for item in matrix.targets if item.target_id == run.target_id), None
        )
        if target is None:
            raise PolicyError(
                "BUILD_TARGET_NOT_FOUND",
                "Build run target is not present in its matrix.",
                details={"target_id": run.target_id},
            )
        expected = (
            matrix.matrix_id,
            matrix.project_id,
            matrix.game_id,
            matrix.source_commit.lower(),
            target.profile,
        )
        run_values = (
            run.matrix_id,
            run.project_id,
            run.game_id,
            run.source_commit.lower(),
            run.profile,
        )
        if run_values != expected:
            raise PolicyError(
                "BUILD_RUN_SCOPE_MISMATCH",
                "Build run does not match its matrix target and source scope.",
                details={"build_run_id": run.build_run_id},
            )
        manifest_values = (
            manifest.matrix_id,
            manifest.project_id,
            manifest.game_id,
            manifest.source_commit.lower(),
            manifest.profile,
        )
        if (
            manifest_values != expected
            or manifest.target_id != target.target_id
            or manifest.target_definition != target
            or manifest.build_run_id != run.build_run_id
            or manifest.mode != run.mode
        ):
            raise PolicyError(
                "BUILD_MANIFEST_SCOPE_MISMATCH",
                "Build manifest does not match its run, matrix target, and source scope.",
                details={"manifest_id": manifest.manifest_id},
            )
        if run.status != RunStatus.SUCCEEDED or run.manifest_id != manifest.manifest_id:
            raise PolicyError(
                "BUILD_RUN_NOT_SUCCESSFUL",
                "Only a successful, linked build run can record a manifest.",
                details={"build_run_id": run.build_run_id, "status": run.status.value},
            )
        if manifest.mode in {ExecutionMode.LIVE, ExecutionMode.CACHED}:
            verification = self.authority.verify_source(matrix, run, manifest)
            if not verification.verified:
                raise PolicyError(
                    verification.code,
                    verification.message,
                    details={"build_run_id": run.build_run_id},
                )
        self._require_artifacts([*manifest.artifacts, *manifest.test_evidence])
        self.repository.add_build(matrix, run, manifest)
        return manifest

    def create_candidate(self, request: CreateCandidateRequest) -> ReleaseCandidate:
        manifests = [
            self.repository.get_manifest(manifest_id)
            for manifest_id in request.manifest_ids
        ]
        self._require_distinct_manifests(manifests)
        primary = manifests[0]
        blockers: List[str] = []

        for manifest in manifests:
            if manifest.source_dirty:
                blockers.append(f"DIRTY_SOURCE:{manifest.manifest_id}")
            try:
                self._require_artifacts([*manifest.artifacts, *manifest.test_evidence])
            except PolicyError as exc:
                blockers.append(f"{exc.code}:{manifest.manifest_id}")

        input_match = len({item.input_fingerprint for item in manifests}) == 1
        output_match = len({item.output_fingerprint for item in manifests}) == 1
        if not input_match:
            blockers.append("BUILD_INPUTS_NOT_REPRODUCIBLE")
        if not output_match:
            blockers.append("BUILD_OUTPUTS_NOT_REPRODUCIBLE")

        release_artifacts = [
            artifact
            for artifact in primary.artifacts
            if artifact.artifact_type == "unity_player"
        ]
        if len(release_artifacts) != 1:
            raise PolicyError(
                "RELEASE_ARTIFACT_AMBIGUOUS",
                "A candidate requires exactly one Unity player artifact.",
                details={"manifest_id": primary.manifest_id},
            )
        now = self.clock.now()
        gate_report = evaluate_release_gates(
            primary, request.gates, self.artifact_catalog, now
        )
        blockers.extend(f"GATE:{item.code}" for item in gate_report.blockers)
        change_set_ids = list(request.approved_change_set_ids)
        if len(change_set_ids) != len(set(change_set_ids)):
            raise PolicyError(
                "DUPLICATE_CHANGE_SET",
                "Candidate ChangeSet IDs must be unique.",
                details={"candidate_id": request.candidate_id},
            )

        reproduction = ReproducibilityEvidence(
            manifest_ids=[item.manifest_id for item in manifests],
            input_fingerprint=primary.input_fingerprint,
            output_fingerprint=primary.output_fingerprint,
            inputs_match=input_match,
            outputs_match=output_match,
            verified_at=now,
        )
        required_roles = required_approval_roles(
            primary.profile, ApprovalAction.CREATE_CANDIDATE
        )
        source_modes = self._candidate_source_modes(manifests, request.gates)
        scope_fingerprint = canonical_sha256(
            {
                "candidate_id": request.candidate_id,
                "manifest_checksums": sorted(
                    item.manifest_checksum for item in manifests
                ),
                "gate_report": gate_report.model_dump(mode="json"),
                "approved_change_set_ids": sorted(change_set_ids),
                "release_artifact_checksum": release_artifacts[0].checksum,
            }
        )
        if blockers:
            status = CandidateStatus.BLOCKED
            mode = ExecutionMode.BLOCKED
            readied_at = None
        elif required_roles:
            status = CandidateStatus.WAITING_APPROVAL
            mode = aggregate_execution_mode(source_modes)
            readied_at = None
        else:
            status = CandidateStatus.READY
            mode = aggregate_execution_mode(source_modes)
            readied_at = now
        candidate = ReleaseCandidate(
            candidate_id=request.candidate_id,
            project_id=primary.project_id,
            game_id=primary.game_id,
            profile=primary.profile,
            source_commit=primary.source_commit,
            build_manifest_ids=[item.manifest_id for item in manifests],
            release_artifact=release_artifacts[0],
            reproducibility=reproduction,
            gates=list(request.gates),
            gate_report=gate_report,
            approved_change_set_ids=change_set_ids,
            required_approval_roles=required_roles,
            approvals=[],
            scope_fingerprint=scope_fingerprint,
            source_modes=source_modes,
            mode=mode,
            status=status,
            blockers=blockers,
            created_at=now,
            readied_at=readied_at,
        )
        self.repository.add_candidate(candidate)
        return candidate

    def approve_candidate(
        self, request: CandidateApprovalRequest
    ) -> ReleaseCandidate:
        candidate = self.repository.get_candidate(request.candidate_id)
        if candidate.status != CandidateStatus.WAITING_APPROVAL:
            raise PolicyError(
                "CANDIDATE_NOT_WAITING_APPROVAL",
                "Candidate is not in an approvable state.",
                details={"status": candidate.status.value},
            )
        approval = request.approval
        if (
            approval.action != ApprovalAction.CREATE_CANDIDATE
            or approval.target_id != candidate.candidate_id
            or approval.scope_fingerprint != candidate.scope_fingerprint
        ):
            raise PolicyError(
                "APPROVAL_SCOPE_MISMATCH",
                "Candidate approval is bound to a different candidate state.",
                details={"approval_id": approval.approval_id},
            )
        if any(
            mode in {ExecutionMode.LIVE, ExecutionMode.CACHED}
            for mode in candidate.source_modes
        ):
            verification = self.authority.verify_approval(approval)
            if not verification.verified:
                raise PolicyError(
                    verification.code,
                    verification.message,
                    details={"approval_id": approval.approval_id},
                )
        if approval.approval_id in {item.approval_id for item in candidate.approvals}:
            return candidate
        approvals = [*candidate.approvals, approval]
        blockers = list(candidate.blockers)
        if approval.decision == ApprovalDecision.REJECTED:
            blockers.append(f"APPROVAL_REJECTED:{approval.role}")
            status = CandidateStatus.BLOCKED
            mode = ExecutionMode.BLOCKED
            readied_at = None
        else:
            approved_roles = {
                item.role
                for item in approvals
                if item.decision == ApprovalDecision.APPROVED
            }
            ready = set(candidate.required_approval_roles).issubset(approved_roles)
            status = CandidateStatus.READY if ready else CandidateStatus.WAITING_APPROVAL
            mode = candidate.mode
            readied_at = self.clock.now() if ready else None
        updated = candidate.model_copy(
            update={
                "approvals": approvals,
                "blockers": blockers,
                "status": status,
                "mode": mode,
                "readied_at": readied_at,
            }
        )
        updated = ReleaseCandidate.model_validate(updated.model_dump())
        self.repository.save_candidate(updated)
        return updated

    def add_feedback_link(self, link: FeedbackLink) -> FeedbackLink:
        candidate = self.repository.get_candidate(link.candidate_id)
        if candidate.project_id != link.project_id or candidate.game_id != link.game_id:
            raise PolicyError(
                "FEEDBACK_SCOPE_MISMATCH",
                "Feedback link belongs to another project or game.",
                details={"feedback_link_id": link.feedback_link_id},
            )
        if link.deployment_id:
            deployment = self.repository.get_deployment(link.deployment_id)
            if deployment.candidate_id != candidate.candidate_id:
                raise PolicyError(
                    "FEEDBACK_DEPLOYMENT_MISMATCH",
                    "Feedback deployment does not contain this candidate.",
                    details={"deployment_id": link.deployment_id},
                )
        self.repository.add_feedback_link(link)
        return link

    def _require_artifacts(self, artifacts: Sequence) -> None:
        failures = []
        for artifact in artifacts:
            inspection = self.artifact_catalog.inspect(artifact)
            if not inspection.available:
                failures.append({"artifact_id": artifact.artifact_id, "reason": inspection.reason})
            elif not inspection.checksum_matches or not inspection.size_matches:
                failures.append({"artifact_id": artifact.artifact_id, "reason": inspection.reason})
        if failures:
            raise PolicyError(
                "ARTIFACT_INTEGRITY_FAILED",
                "One or more release artifacts are missing or corrupt.",
                details={"artifacts": failures},
            )

    @staticmethod
    def _require_distinct_manifests(manifests: Sequence[BuildManifest]) -> None:
        ids = [item.manifest_id for item in manifests]
        if len(ids) < 2 or len(ids) != len(set(ids)):
            raise PolicyError(
                "REPRODUCIBILITY_PAIR_REQUIRED",
                "Candidate requires at least two distinct build manifests.",
                details={"manifest_ids": ids},
            )
        primary = manifests[0]
        scope = (
            primary.project_id,
            primary.game_id,
            primary.profile,
            primary.target_id,
            primary.source_commit.lower(),
        )
        if any(
            (
                item.project_id,
                item.game_id,
                item.profile,
                item.target_id,
                item.source_commit.lower(),
            )
            != scope
            for item in manifests[1:]
        ):
            raise PolicyError(
                "CROSS_SCOPE_BUILD",
                "Reproducibility builds must share project, game, target, profile, and commit.",
                details={"manifest_ids": ids},
            )

    @staticmethod
    def _candidate_source_modes(manifests, gates) -> List[ExecutionMode]:
        modes = {
            *[manifest.mode for manifest in manifests],
            *[artifact.mode for manifest in manifests for artifact in manifest.artifacts],
            *[
                evidence.mode
                for manifest in manifests
                for evidence in manifest.test_evidence
            ],
            *[gate.mode for gate in gates],
            *[evidence.mode for gate in gates for evidence in gate.evidence],
        }
        return sorted(modes, key=lambda mode: mode.value)
