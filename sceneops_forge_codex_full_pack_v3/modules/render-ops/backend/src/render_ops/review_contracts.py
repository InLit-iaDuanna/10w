"""AI variant and deterministic comparison contracts."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base_contracts import (
    AovPass,
    ApprovalState,
    ArtifactApprovalState,
    ArtifactRef,
    ExecutionMode,
    SceneCameraRef,
    StrictModel,
    require_utc,
)


class WorkflowProvenance(StrictModel):
    provider: str = Field(min_length=1)
    workflow_reference: str = Field(min_length=1)
    workflow_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_reference: str = Field(min_length=1)
    model_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    seed: int = Field(ge=0)
    prompt: str = Field(min_length=1)
    negative_prompt: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    adapter_version: str = Field(min_length=1)


class RenderVariantApprovalSnapshot(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variant_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    scene: SceneCameraRef
    output: ArtifactRef
    constraint_passes: Tuple[AovPass, ...] = Field(min_length=1)
    provenance: WorkflowProvenance
    approved_by: str = Field(min_length=1)
    approved_at: datetime

    _approved_at_utc = field_validator("approved_at")(require_utc)


class RenderVariant(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variant_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    scene: SceneCameraRef
    output: ArtifactRef
    constraint_passes: Tuple[AovPass, ...] = Field(min_length=1)
    provenance: WorkflowProvenance
    approval_state: ApprovalState
    approved_by: Optional[str] = Field(default=None, min_length=1)
    approved_at: Optional[datetime] = None
    approval_snapshot: Optional[RenderVariantApprovalSnapshot] = None

    _approved_at_utc = field_validator("approved_at")(
        lambda value: require_utc(value) if value is not None else value
    )

    @model_validator(mode="after")
    def approval_identity(self) -> "RenderVariant":
        approved = self.approval_state == ApprovalState.APPROVED
        if approved and not (
            self.approved_by and self.approved_at and self.approval_snapshot
        ):
            raise ValueError("approved variants require approver and UTC timestamp")
        expected_output_approval = ArtifactApprovalState(self.approval_state.value)
        if self.output.approval_state != expected_output_approval:
            raise ValueError("variant output approval must match variant approval")
        if not approved and (
            self.approved_by or self.approved_at or self.approval_snapshot
        ):
            raise ValueError("unapproved variants cannot contain approval identity")
        if not {AovPass.DEPTH, AovPass.NORMAL, AovPass.OBJECT_ID}.issubset(
            set(self.constraint_passes)
        ):
            raise ValueError("variants require depth, normal, and object_id constraints")
        if approved and self.approval_snapshot != self.snapshot_payload():
            raise ValueError("approved variant differs from its approval snapshot")
        return self

    def snapshot_payload(
        self,
        *,
        output: Optional[ArtifactRef] = None,
        approved_by: Optional[str] = None,
        approved_at: Optional[datetime] = None,
    ) -> RenderVariantApprovalSnapshot:
        resolved_output = output or self.output
        resolved_by = approved_by or self.approved_by
        resolved_at = approved_at or self.approved_at
        if not (resolved_by and resolved_at):
            raise ValueError("variant approval snapshot requires approval identity")
        return RenderVariantApprovalSnapshot(
            variant_id=self.variant_id,
            job_id=self.job_id,
            scene=SceneCameraRef.model_validate(self.scene.model_dump(mode="python")),
            output=ArtifactRef.model_validate(resolved_output.model_dump(mode="python")),
            constraint_passes=self.constraint_passes,
            provenance=WorkflowProvenance.model_validate(
                self.provenance.model_dump(mode="python")
            ),
            approved_by=resolved_by,
            approved_at=resolved_at,
        )


class DifferenceMetrics(StrictModel):
    mean_absolute_difference: float = Field(ge=0.0, le=1.0)
    changed_pixel_ratio: float = Field(ge=0.0, le=1.0)
    maximum_channel_difference: float = Field(ge=0.0, le=1.0)
    artistic_quality_measured: Literal[False] = False


class ProtectedRegionResult(StrictModel):
    region_id: str = Field(min_length=1)
    changed_pixel_ratio: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    passed: bool

    @model_validator(mode="after")
    def threshold_result_is_derived(self) -> "ProtectedRegionResult":
        if self.passed != (self.changed_pixel_ratio <= self.threshold):
            raise ValueError("passed must be derived from the protected-region threshold")
        return self


class RenderComparison(StrictModel):
    comparison_id: str = Field(min_length=1)
    before_artifact_id: str = Field(min_length=1)
    after_artifact_id: str = Field(min_length=1)
    scene: SceneCameraRef
    metrics: DifferenceMetrics
    protected_regions: List[ProtectedRegionResult] = Field(default_factory=list)
    changed_object_ids: List[str] = Field(default_factory=list)
    execution_mode: ExecutionMode

    @model_validator(mode="after")
    def unique_evidence_ids(self) -> "RenderComparison":
        if self.execution_mode not in {
            ExecutionMode.LIVE,
            ExecutionMode.CACHED,
            ExecutionMode.MOCK,
        }:
            raise ValueError("comparison evidence cannot be planned or blocked")
        region_ids = [item.region_id for item in self.protected_regions]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("protected-region result IDs must be unique")
        if len(self.changed_object_ids) != len(set(self.changed_object_ids)):
            raise ValueError("changed_object_ids must be unique")
        return self
