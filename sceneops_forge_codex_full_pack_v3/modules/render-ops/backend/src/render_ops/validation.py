"""Deterministic fixed-camera and protected-region validation."""

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence, Set

from .schemas import (
    DifferenceMetrics,
    ExecutionMode,
    ApprovalState,
    ProtectedRegionResult,
    RenderBrief,
    RenderComparison,
    SceneCameraRef,
    ValidationResult,
    WritebackProposal,
)


def compare_pixel_bytes(
    before: bytes,
    after: bytes,
    *,
    changed_threshold: float = 1.0 / 255.0,
) -> DifferenceMetrics:
    if not before or len(before) != len(after):
        raise ValueError("fixed-camera buffers must be non-empty and equal length")
    differences = [abs(left - right) / 255.0 for left, right in zip(before, after)]
    return DifferenceMetrics(
        mean_absolute_difference=sum(differences) / len(differences),
        changed_pixel_ratio=sum(item > changed_threshold for item in differences)
        / len(differences),
        maximum_channel_difference=max(differences),
        artistic_quality_measured=False,
    )


def compare_protected_region(
    region_id: str,
    before: bytes,
    after: bytes,
    mask: Sequence[bool],
    threshold: float,
    *,
    changed_threshold: float = 1.0 / 255.0,
) -> ProtectedRegionResult:
    if len(before) != len(after) or len(before) != len(mask):
        raise ValueError("protected-region mask must match fixed-camera buffers")
    protected_indices = [index for index, included in enumerate(mask) if included]
    if not protected_indices:
        raise ValueError("protected-region mask must contain at least one sample")
    changed = sum(
        abs(before[index] - after[index]) / 255.0 > changed_threshold
        for index in protected_indices
    )
    ratio = changed / len(protected_indices)
    return ProtectedRegionResult(
        region_id=region_id,
        changed_pixel_ratio=ratio,
        threshold=threshold,
        passed=ratio <= threshold,
    )


def make_comparison(
    *,
    comparison_id: str,
    before_artifact_id: str,
    after_artifact_id: str,
    scene: SceneCameraRef,
    before: bytes,
    after: bytes,
    protected_regions: Iterable[ProtectedRegionResult],
    changed_object_ids: Iterable[str],
    execution_mode: ExecutionMode,
) -> RenderComparison:
    return RenderComparison(
        comparison_id=comparison_id,
        before_artifact_id=before_artifact_id,
        after_artifact_id=after_artifact_id,
        scene=scene,
        metrics=compare_pixel_bytes(before, after),
        protected_regions=list(protected_regions),
        changed_object_ids=list(changed_object_ids),
        execution_mode=execution_mode,
    )


def validate_writeback_result(
    *,
    validation_id: str,
    proposal: WritebackProposal,
    brief: RenderBrief,
    comparison: RenderComparison,
    deterministic_recipe_id: str,
    geometry_revision_before: str,
    geometry_revision_after: str,
    camera_revision_before: str,
    camera_revision_after: str,
    execution_mode: ExecutionMode,
    completed_at: Optional[datetime] = None,
) -> ValidationResult:
    proposal = WritebackProposal.model_validate(proposal.model_dump(mode="python"))
    brief = RenderBrief.model_validate(brief.model_dump(mode="python"))
    comparison = RenderComparison.model_validate(comparison.model_dump(mode="python"))
    if proposal.approval_state != ApprovalState.APPROVED:
        raise PermissionError("validation requires an approved writeback proposal")
    if proposal.brief_id != brief.brief_id or proposal.scene != brief.scene:
        raise ValueError("validation proposal and brief identity differ")
    if set(proposal.allowed_object_ids) != set(brief.target_object_ids):
        raise ValueError("validation proposal allowlist differs from the render brief")
    if comparison.execution_mode != execution_mode:
        raise ValueError("validation mode must match comparison evidence mode")
    allowed: Set[str] = {item.target_object_id for item in proposal.operations}
    changed: Set[str] = set(comparison.changed_object_ids)
    geometry_unchanged = geometry_revision_before == geometry_revision_after
    camera_unchanged = camera_revision_before == camera_revision_after
    expected_regions = {item.region_id: item for item in brief.protected_regions}
    actual_regions = {item.region_id: item for item in comparison.protected_regions}
    protected_passed = set(expected_regions) == set(actual_regions) and all(
        actual_regions[region_id].threshold == region.max_changed_ratio
        and actual_regions[region_id].changed_pixel_ratio <= region.max_changed_ratio
        for region_id, region in expected_regions.items()
    )
    scope_passed = changed.issubset(allowed)
    failures: List[str] = []
    if not geometry_unchanged:
        failures.append("geometry changed outside the approved render writeback")
    if not camera_unchanged:
        failures.append("fixed camera changed")
    if not protected_passed:
        failures.append("protected-region evidence is incomplete or exceeds its threshold")
    if not scope_passed:
        failures.append("changed object scope exceeds the approved operations")
    return ValidationResult(
        validation_id=validation_id,
        proposal_id=proposal.proposal_id,
        comparison_id=comparison.comparison_id,
        deterministic_recipe_id=deterministic_recipe_id,
        changed_object_ids=sorted(changed),
        allowed_object_ids=sorted(allowed),
        geometry_unchanged=geometry_unchanged,
        camera_unchanged=camera_unchanged,
        protected_regions_passed=protected_passed,
        scope_passed=scope_passed,
        passed=not failures,
        failures=failures,
        execution_mode=execution_mode,
        completed_at=completed_at or datetime.now(timezone.utc),
    )
