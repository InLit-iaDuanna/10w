"""Render Ops orchestration without vendor-specific imports."""

from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional

from .cache import plan_aov_cache, validate_aov_set
from .schemas import (
    AovArtifact,
    AovDependencySnapshot,
    AovPass,
    ApprovalState,
    ArtifactApprovalState,
    ArtifactRef,
    ExecutionMode,
    JobFailure,
    RenderBrief,
    RenderJob,
    RenderJobState,
    RenderRecipe,
    RenderVariant,
    WorkflowProvenance,
    WritebackOperation,
    WritebackProposal,
)


class RenderOpsService:
    def create_job(
        self,
        *,
        job_id: str,
        brief: RenderBrief,
        recipe: RenderRecipe,
        dependency_snapshot: AovDependencySnapshot,
        existing_aovs: Mapping[AovPass, AovArtifact],
        previous_snapshot: Optional[AovDependencySnapshot],
        execution_mode: ExecutionMode,
        created_at: Optional[datetime] = None,
    ) -> RenderJob:
        brief = RenderBrief.model_validate(brief.model_dump(mode="python"))
        recipe = RenderRecipe.model_validate(recipe.model_dump(mode="python"))
        dependency_snapshot = AovDependencySnapshot.model_validate(
            dependency_snapshot.model_dump(mode="python")
        )
        timestamp = created_at or datetime.now(timezone.utc)
        if (
            dependency_snapshot.recipe_id,
            dependency_snapshot.recipe_version,
        ) != (recipe.recipe_id, recipe.version):
            raise ValueError("dependency snapshot must match the selected recipe version")
        plan = plan_aov_cache(
            recipe,
            brief.scene,
            dependency_snapshot,
            existing_aovs,
            previous_snapshot,
            execution_mode,
        )
        return RenderJob(
            job_id=job_id,
            brief_id=brief.brief_id,
            recipe_id=recipe.recipe_id,
            recipe_version=recipe.version,
            scene=brief.scene,
            dependency_snapshot=dependency_snapshot,
            cache_plan=plan,
            state=RenderJobState.QUEUED,
            execution_mode=execution_mode,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def block_job(
        self,
        job: RenderJob,
        *,
        code: str,
        message: str,
        retryable: bool,
        updated_at: Optional[datetime] = None,
    ) -> RenderJob:
        if job.state != RenderJobState.QUEUED:
            raise ValueError("only a queued job can be blocked before execution")
        payload = job.model_dump(mode="python")
        payload.update(
            state=RenderJobState.FAILED,
            execution_mode=ExecutionMode.BLOCKED,
            failure=JobFailure(
                code=code,
                message=message,
                retryable=retryable,
                suggested_actions=["integration.open", "render.job.retry"],
            ),
            updated_at=updated_at or datetime.now(timezone.utc),
        )
        return RenderJob.model_validate(payload)

    def validate_capture(
        self,
        *,
        job: RenderJob,
        recipe: RenderRecipe,
        aovs: Iterable[AovArtifact],
    ) -> Mapping[AovPass, AovArtifact]:
        job = RenderJob.model_validate(job.model_dump(mode="python"))
        recipe = RenderRecipe.model_validate(recipe.model_dump(mode="python"))
        return validate_aov_set(
            recipe,
            job.scene,
            job.dependency_snapshot.width,
            job.dependency_snapshot.height,
            aovs,
            job.execution_mode,
        )

    def create_variant(
        self,
        *,
        variant_id: str,
        job: RenderJob,
        recipe: RenderRecipe,
        output: ArtifactRef,
        provenance: WorkflowProvenance,
        constraint_passes: Iterable[AovPass],
    ) -> RenderVariant:
        job = RenderJob.model_validate(job.model_dump(mode="python"))
        recipe = RenderRecipe.model_validate(recipe.model_dump(mode="python"))
        output = ArtifactRef.model_validate(output.model_dump(mode="python"))
        provenance = WorkflowProvenance.model_validate(
            provenance.model_dump(mode="python")
        )
        if job.state not in {
            RenderJobState.RUNNING,
            RenderJobState.WAITING_APPROVAL,
            RenderJobState.SUCCEEDED,
        }:
            raise ValueError("variant requires a started render job")
        if output.execution_mode != job.execution_mode:
            raise ValueError("variant output mode must match the render job mode")
        if (
            output.source_project_id != job.scene.project_id
            or output.source_version != job.scene.scene_version
        ):
            raise ValueError("variant output provenance must match the render job scene")
        if output.approval_state != ArtifactApprovalState.PENDING:
            raise ValueError("new AI variant artifacts must be pending approval")
        if recipe.workflow_reference != provenance.workflow_reference:
            raise ValueError("variant workflow reference does not match recipe")
        if recipe.workflow_checksum_sha256 != provenance.workflow_checksum_sha256:
            raise ValueError("variant workflow checksum does not match recipe")
        return RenderVariant(
            variant_id=variant_id,
            job_id=job.job_id,
            scene=job.scene,
            output=output,
            constraint_passes=list(constraint_passes),
            provenance=provenance,
            approval_state=ApprovalState.PENDING,
        )

    def approve_variant(
        self,
        variant: RenderVariant,
        *,
        approved_by: str,
        approved_at: Optional[datetime] = None,
    ) -> RenderVariant:
        variant = RenderVariant.model_validate(variant.model_dump(mode="python"))
        if variant.approval_state != ApprovalState.PENDING:
            raise ValueError("only pending variants can be approved")
        payload = variant.model_dump(mode="python")
        output = variant.output.model_dump(mode="python")
        output["approval_state"] = ArtifactApprovalState.APPROVED
        approved_output = ArtifactRef.model_validate(output)
        timestamp = approved_at or datetime.now(timezone.utc)
        payload.update(
            approval_state=ApprovalState.APPROVED,
            approved_by=approved_by,
            approved_at=timestamp,
            output=approved_output,
            approval_snapshot=variant.snapshot_payload(
                output=approved_output,
                approved_by=approved_by,
                approved_at=timestamp,
            ),
        )
        return RenderVariant.model_validate(payload)

    def propose_writeback(
        self,
        *,
        proposal_id: str,
        brief: RenderBrief,
        variant: RenderVariant,
        operations: Iterable[WritebackOperation],
        rationale: str,
        expected_result: str,
        risk: str,
        validation_plan: str,
        rollback_plan: str,
    ) -> WritebackProposal:
        brief = RenderBrief.model_validate(brief.model_dump(mode="python"))
        variant = RenderVariant.model_validate(variant.model_dump(mode="python"))
        if variant.approval_state != ApprovalState.APPROVED:
            raise PermissionError("writeback proposals require an approved variant")
        if variant.scene != brief.scene:
            raise ValueError("writeback brief and variant must reference the same scene")
        operation_list = [
            WritebackOperation.model_validate(item.model_dump(mode="python"))
            for item in operations
        ]
        target_ids = {item.target_object_id for item in operation_list}
        if not target_ids.issubset(set(brief.target_object_ids)):
            raise PermissionError("writeback operation targets must belong to the render brief")
        return WritebackProposal(
            proposal_id=proposal_id,
            variant_id=variant.variant_id,
            brief_id=brief.brief_id,
            scene=variant.scene,
            base_scene_version=variant.scene.scene_version,
            operations=operation_list,
            rationale=rationale,
            expected_result=expected_result,
            impact_scope=sorted({item.target_object_id for item in operation_list}),
            allowed_object_ids=tuple(brief.target_object_ids),
            risk=risk,
            validation_plan=validation_plan,
            rollback_plan=rollback_plan,
            approval_requirements=["render:approve", "render:writeback"],
            approval_state=ApprovalState.PENDING,
        )
