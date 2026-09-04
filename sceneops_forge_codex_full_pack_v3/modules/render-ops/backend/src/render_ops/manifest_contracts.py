"""RenderManifest identity/provenance chain and API summary contracts."""

from datetime import datetime
from typing import List, Literal, Optional, Set

from pydantic import Field, field_validator, model_validator

from .base_contracts import (
    AovArtifact,
    AovDependencySnapshot,
    ApprovalState,
    ArtifactApprovalState,
    ArtifactRef,
    ExecutionMode,
    RenderBrief,
    RenderJob,
    RenderRecipe,
    StrictModel,
    require_utc,
)
from .review_contracts import RenderComparison, RenderVariant
from .writeback_contracts import WritebackProposal


class ValidationResult(StrictModel):
    validation_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    comparison_id: str = Field(min_length=1)
    deterministic_recipe_id: str = Field(min_length=1)
    changed_object_ids: List[str] = Field(default_factory=list)
    allowed_object_ids: List[str] = Field(default_factory=list)
    geometry_unchanged: bool
    camera_unchanged: bool
    protected_regions_passed: bool
    scope_passed: bool
    passed: bool
    failures: List[str] = Field(default_factory=list)
    execution_mode: ExecutionMode
    completed_at: datetime

    _completed_at_utc = field_validator("completed_at")(require_utc)

    @model_validator(mode="after")
    def aggregate_result(self) -> "ValidationResult":
        if self.execution_mode not in {
            ExecutionMode.LIVE,
            ExecutionMode.CACHED,
            ExecutionMode.MOCK,
        }:
            raise ValueError("validation evidence cannot be planned or blocked")
        if len(self.changed_object_ids) != len(set(self.changed_object_ids)):
            raise ValueError("validation changed_object_ids must be unique")
        if len(self.allowed_object_ids) != len(set(self.allowed_object_ids)):
            raise ValueError("validation allowed_object_ids must be unique")
        if self.scope_passed != set(self.changed_object_ids).issubset(
            set(self.allowed_object_ids)
        ):
            raise ValueError("scope_passed must be derived from changed and allowed IDs")
        expected = (
            self.geometry_unchanged
            and self.camera_unchanged
            and self.protected_regions_passed
            and self.scope_passed
            and not self.failures
        )
        if self.passed != expected:
            raise ValueError("passed must equal the aggregate validation gates")
        return self


class RenderManifest(StrictModel):
    schema_version: Literal[1]
    manifest_id: str = Field(min_length=1)
    brief: RenderBrief
    recipe: RenderRecipe
    job: RenderJob
    aovs: List[AovArtifact] = Field(min_length=1)
    variants: List[RenderVariant] = Field(default_factory=list)
    comparisons: List[RenderComparison] = Field(default_factory=list)
    writeback_proposals: List[WritebackProposal] = Field(default_factory=list)
    validations: List[ValidationResult] = Field(default_factory=list)
    created_at: datetime

    _created_at_utc = field_validator("created_at")(require_utc)

    @model_validator(mode="after")
    def identity_and_provenance_chain(self) -> "RenderManifest":
        self._validate_job_links()
        self._validate_aovs()
        variant_ids = self._validate_variants()
        proposal_ids = self._validate_proposals(variant_ids)
        comparison_ids = self._validate_comparisons()
        self._validate_results(proposal_ids, comparison_ids)
        return self

    def _validate_job_links(self) -> None:
        if self.job.brief_id != self.brief.brief_id:
            raise ValueError("job must reference manifest brief")
        if (self.job.recipe_id, self.job.recipe_version) != (
            self.recipe.recipe_id,
            self.recipe.version,
        ):
            raise ValueError("job must reference manifest recipe and version")
        if self.job.scene != self.brief.scene:
            raise ValueError("job and brief must reference the same scene/camera")
        if (
            self.job.dependency_snapshot.recipe_id,
            self.job.dependency_snapshot.recipe_version,
        ) != (self.recipe.recipe_id, self.recipe.version):
            raise ValueError("job dependency snapshot must match the manifest recipe")

    def _validate_aovs(self) -> None:
        if self.job.execution_mode not in {
            ExecutionMode.LIVE,
            ExecutionMode.CACHED,
            ExecutionMode.MOCK,
        }:
            raise ValueError("a manifest with artifacts cannot be planned or blocked")
        pass_types = [item.pass_type for item in self.aovs]
        if len(pass_types) != len(set(pass_types)):
            raise ValueError("manifest AOV passes must be unique")
        artifact_ids = [item.artifact.artifact_id for item in self.aovs]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("manifest AOV artifact IDs must be unique")
        missing = set(self.recipe.required_passes) - set(pass_types)
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise ValueError("manifest is missing required AOVs: " + names)
        for aov in self.aovs:
            if aov.scene != self.brief.scene:
                raise ValueError("all AOVs must match the exact scene/camera version")
            if aov.artifact.execution_mode not in self._compatible_artifact_modes():
                raise ValueError("AOV mode is incompatible with manifest job mode")
            if not self._artifact_matches_scene(aov.artifact):
                raise ValueError("AOV provenance must match manifest project/scene version")

    def _validate_variants(self) -> Set[str]:
        variant_ids = {variant.variant_id for variant in self.variants}
        if len(variant_ids) != len(self.variants):
            raise ValueError("manifest variant IDs must be unique")
        for variant in self.variants:
            variant = RenderVariant.model_validate(variant.model_dump(mode="python"))
            if variant.job_id != self.job.job_id or variant.scene != self.brief.scene:
                raise ValueError("variant must match manifest job and scene/camera")
            if variant.output.execution_mode != self.job.execution_mode:
                raise ValueError("variant output mode must match manifest job mode")
            expected_approval = ArtifactApprovalState(variant.approval_state.value)
            if variant.output.approval_state != expected_approval:
                raise ValueError("variant artifact approval must match variant approval")
            if not self._artifact_matches_scene(variant.output):
                raise ValueError("variant provenance must match manifest project/scene version")
            if (
                variant.provenance.workflow_reference != self.recipe.workflow_reference
                or variant.provenance.workflow_checksum_sha256
                != self.recipe.workflow_checksum_sha256
            ):
                raise ValueError("variant workflow provenance must match manifest recipe")
        return variant_ids

    def _validate_proposals(self, variant_ids: Set[str]) -> Set[str]:
        proposal_ids = {item.proposal_id for item in self.writeback_proposals}
        if len(proposal_ids) != len(self.writeback_proposals):
            raise ValueError("manifest writeback proposal IDs must be unique")
        for proposal in self.writeback_proposals:
            proposal = WritebackProposal.model_validate(
                proposal.model_dump(mode="python")
            )
            if proposal.variant_id not in variant_ids:
                raise ValueError("writeback proposal must reference a manifest variant")
            if proposal.brief_id != self.brief.brief_id:
                raise ValueError("writeback proposal must reference the manifest brief")
            if proposal.base_scene_version != self.brief.scene.scene_version:
                raise ValueError("writeback base version must match manifest scene version")
            if proposal.scene != self.brief.scene:
                raise ValueError("writeback proposal must use the manifest scene/camera")
            operation_ids = {item.target_object_id for item in proposal.operations}
            if set(proposal.allowed_object_ids) != set(self.brief.target_object_ids):
                raise ValueError("writeback object allowlist must equal the render brief targets")
            if not operation_ids.issubset(set(self.brief.target_object_ids)):
                raise ValueError("writeback targets must belong to the render brief")
        return proposal_ids

    def _validate_comparisons(self) -> Set[str]:
        comparison_ids = {item.comparison_id for item in self.comparisons}
        if len(comparison_ids) != len(self.comparisons):
            raise ValueError("manifest comparison IDs must be unique")
        for comparison in self.comparisons:
            comparison = RenderComparison.model_validate(
                comparison.model_dump(mode="python")
            )
            if comparison.scene != self.brief.scene:
                raise ValueError("comparison must use the manifest fixed camera")
            if comparison.execution_mode != self.job.execution_mode:
                raise ValueError("comparison mode must match manifest job mode")
            expected_regions = {
                item.region_id: item.max_changed_ratio
                for item in self.brief.protected_regions
            }
            actual_regions = {
                item.region_id: item.threshold for item in comparison.protected_regions
            }
            if actual_regions != expected_regions:
                raise ValueError(
                    "comparison must contain the exact protected-region threshold set"
                )
        return comparison_ids

    def _validate_results(
        self, proposal_ids: Set[str], comparison_ids: Set[str]
    ) -> None:
        validation_ids = {item.validation_id for item in self.validations}
        if len(validation_ids) != len(self.validations):
            raise ValueError("manifest validation IDs must be unique")
        for validation in self.validations:
            if validation.proposal_id not in proposal_ids:
                raise ValueError("validation must reference a manifest writeback")
            if validation.comparison_id not in comparison_ids:
                raise ValueError("validation must reference a manifest comparison")
            if validation.execution_mode != self.job.execution_mode:
                raise ValueError("validation mode must match manifest job mode")
            proposal = next(
                item for item in self.writeback_proposals
                if item.proposal_id == validation.proposal_id
            )
            comparison = next(
                item for item in self.comparisons
                if item.comparison_id == validation.comparison_id
            )
            allowed_ids = {item.target_object_id for item in proposal.operations}
            if set(validation.allowed_object_ids) != allowed_ids:
                raise ValueError("validation scope must equal the approved writeback scope")
            if set(validation.changed_object_ids) != set(comparison.changed_object_ids):
                raise ValueError("validation changed-object evidence must match comparison")
            if validation.protected_regions_passed != all(
                item.passed for item in comparison.protected_regions
            ):
                raise ValueError("validation protected-region result is inconsistent")

    def _compatible_artifact_modes(self) -> Set[ExecutionMode]:
        if self.job.execution_mode == ExecutionMode.MOCK:
            return {ExecutionMode.MOCK}
        return {ExecutionMode.LIVE, ExecutionMode.CACHED}

    def _artifact_matches_scene(self, artifact: ArtifactRef) -> bool:
        return (
            artifact.source_project_id == self.brief.scene.project_id
            and artifact.source_version == self.brief.scene.scene_version
        )


class ManifestSummary(StrictModel):
    manifest_id: str
    job_id: str
    execution_mode: ExecutionMode
    pass_count: int = Field(ge=0)
    variant_count: int = Field(ge=0)
    approved_writeback_count: int = Field(ge=0)
    passing_validation_count: int = Field(ge=0)


class RenderJobPlanRequest(StrictModel):
    job_id: str = Field(min_length=1)
    brief: RenderBrief
    recipe: RenderRecipe
    dependency_snapshot: AovDependencySnapshot
    existing_aovs: List[AovArtifact] = Field(default_factory=list)
    previous_snapshot: Optional[AovDependencySnapshot] = None
    execution_mode: ExecutionMode
    requested_at: datetime

    _requested_at_utc = field_validator("requested_at")(require_utc)

    @model_validator(mode="after")
    def existing_passes_are_unique(self) -> "RenderJobPlanRequest":
        passes = [item.pass_type for item in self.existing_aovs]
        if len(passes) != len(set(passes)):
            raise ValueError("existing_aovs must contain unique pass types")
        return self


def summarize_manifest(manifest: RenderManifest) -> ManifestSummary:
    approved = sum(
        proposal.approval_state == ApprovalState.APPROVED
        for proposal in manifest.writeback_proposals
    )
    passed = sum(validation.passed for validation in manifest.validations)
    return ManifestSummary(
        manifest_id=manifest.manifest_id,
        job_id=manifest.job.job_id,
        execution_mode=manifest.job.execution_mode,
        pass_count=len(manifest.aovs),
        variant_count=len(manifest.variants),
        approved_writeback_count=approved,
        passing_validation_count=passed,
    )
