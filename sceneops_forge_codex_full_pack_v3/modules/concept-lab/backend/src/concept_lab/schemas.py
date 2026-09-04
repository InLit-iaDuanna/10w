from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ConceptStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class VariantStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class PermissionStatus(str, Enum):
    CLEARED = "cleared"
    WARNING = "warning"
    BLOCKED = "blocked"


class ReferenceKind(str, Enum):
    IMPORTED = "imported"
    GENERATED = "generated"


class RequiredView(str, Enum):
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    THREE_QUARTER = "three_quarter"
    TURNAROUND = "turnaround"


class ChangeSetStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


class GenerationState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ReviewVerdict(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    UNCERTAIN = "uncertain"


class StyleAssessment(str, Enum):
    CONSISTENT = "consistent"
    NEEDS_REVIEW = "needs_review"
    INCONSISTENT = "inconsistent"


class ReviewAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class DimensionsMeters(StrictModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    depth: float = Field(gt=0)
    unit: Literal["m"] = "m"


class PlatformBudget(StrictModel):
    target_platform: str = Field(min_length=1)
    max_triangles: int = Field(gt=0)
    max_texture_size_px: int = Field(gt=0)
    max_material_slots: int = Field(gt=0)


class ConceptCreateInput(StrictModel):
    project_id: str = Field(min_length=1)
    project_bible_version_id: str = Field(min_length=1)
    feature_id: Optional[str] = None
    task_id: Optional[str] = None
    subject: str = Field(min_length=1)
    gameplay_function: str = Field(min_length=1)
    proportions: str = Field(min_length=1)
    dimensions: DimensionsMeters
    materials: List[str] = Field(min_length=1)
    required_views: List[RequiredView] = Field(min_length=1)
    platform_budget: PlatformBudget
    style_constraints: List[str] = Field(min_length=1)
    forbidden_elements: List[str] = Field(default_factory=list)

    @field_validator("materials", "style_constraints", "forbidden_elements")
    @classmethod
    def unique_nonempty_strings(cls, values: List[str]) -> List[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("entries must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("entries must be unique")
        return normalized

    @field_validator("required_views")
    @classmethod
    def unique_views(cls, values: List[RequiredView]) -> List[RequiredView]:
        if len(set(values)) != len(values):
            raise ValueError("required views must be unique")
        return values


class ConceptSpec(ConceptCreateInput):
    concept_id: str
    version: int = Field(ge=1)
    status: ConceptStatus = ConceptStatus.DRAFT
    reference_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    authored_by: str


class ConceptPatch(StrictModel):
    subject: Optional[str] = Field(default=None, min_length=1)
    gameplay_function: Optional[str] = Field(default=None, min_length=1)
    proportions: Optional[str] = Field(default=None, min_length=1)
    dimensions: Optional[DimensionsMeters] = None
    materials: Optional[List[str]] = None
    required_views: Optional[List[RequiredView]] = None
    platform_budget: Optional[PlatformBudget] = None
    style_constraints: Optional[List[str]] = None
    forbidden_elements: Optional[List[str]] = None


class ConceptChangeSet(StrictModel):
    change_set_id: str
    concept_id: str
    base_version: int
    target_integration: Literal["concept-lab"] = "concept-lab"
    target_object_ids: List[str]
    previous_values: Dict[str, Any]
    proposed_values: Dict[str, Any]
    rationale: str
    expected_result: str
    impact_scope: List[str]
    risk: Literal["low", "medium", "high"]
    validation_plan: List[str]
    rollback_plan: str
    approval_requirements: List[str]
    proposed_by: str
    proposed_by_type: Literal["user", "agent"]
    status: ChangeSetStatus
    approved_by: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None


class ReferenceSource(StrictModel):
    kind: ReferenceKind
    source_uri: str = Field(min_length=1)
    creator: str = Field(min_length=1)
    license_name: str = Field(min_length=1)
    license_uri: Optional[str] = None
    permission_status: PermissionStatus
    permission_notes: Optional[str] = None


class AiGenerationMetadata(StrictModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    workflow_version: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    negative_prompt: Optional[str] = None
    seed: int = Field(ge=0)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ArtifactProvenance(StrictModel):
    artifact_id: str
    artifact_type: Literal["concept-image"] = "concept-image"
    source_project_id: str
    source_version: str
    related_sceneops_ids: List[str] = Field(default_factory=list)
    producing_module: str
    tool: str
    adapter_version: str
    workflow_version: str
    creator_or_agent: str
    execution_mode: ExecutionMode
    created_at: datetime
    checksum_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    approval_state: Literal["unreviewed", "approved", "rejected"] = "unreviewed"
    ai: Optional[AiGenerationMetadata] = None

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("created_at must be timezone-aware UTC")
        return value


class ConceptReference(StrictModel):
    reference_id: str
    concept_id: str
    concept_version: int
    title: str = Field(min_length=1)
    view: RequiredView
    artifact_uri: str = Field(min_length=1)
    source: ReferenceSource
    provenance: ArtifactProvenance
    imported_at: datetime


class ImportedReferenceInput(StrictModel):
    title: str = Field(min_length=1)
    view: RequiredView
    artifact_uri: str = Field(min_length=1)
    source: ReferenceSource
    provenance: ArtifactProvenance


class ConceptVariant(StrictModel):
    variant_id: str
    concept_id: str
    concept_version: int
    title: str = Field(min_length=1)
    reference_ids: List[str] = Field(min_length=1)
    covered_views: List[RequiredView] = Field(min_length=1)
    status: VariantStatus = VariantStatus.PROPOSED
    execution_mode: ExecutionMode
    generation: Optional[AiGenerationMetadata] = None
    created_at: datetime


class StyleEvidenceInput(StrictModel):
    criterion: str = Field(min_length=1)
    criterion_kind: Literal["style_constraint", "forbidden_element"]
    observed: str = Field(min_length=1)
    verdict: ReviewVerdict
    evidence_reference_id: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1)


class StyleCheck(StrictModel):
    style_check_id: str
    concept_id: str
    concept_version: int
    variant_id: str
    evidence: List[StyleEvidenceInput] = Field(min_length=1)
    assessment: StyleAssessment
    confidence: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    unevaluated_criteria: List[str]
    method: Literal["declared-evidence-review"] = "declared-evidence-review"
    is_subjective: Literal[True] = True
    created_by: str
    created_at: datetime


class VariantComment(StrictModel):
    comment_id: str
    variant_id: str
    body: str = Field(min_length=1)
    author_id: str
    created_at: datetime


class ConceptDecision(StrictModel):
    decision_id: str
    concept_id: str
    concept_version: int
    variant_id: str
    action: ReviewAction
    rationale: str = Field(min_length=1)
    reviewer_id: str
    acknowledged_license_warning: bool = False
    created_at: datetime


class VariantComparisonEntry(StrictModel):
    variant_id: str
    status: VariantStatus
    execution_mode: ExecutionMode
    covered_views: List[RequiredView]
    missing_required_views: List[RequiredView]
    permission_statuses: List[PermissionStatus]
    latest_style_assessment: Optional[StyleAssessment] = None
    latest_style_confidence: Optional[float] = None


class VariantComparison(StrictModel):
    comparison_id: str
    concept_id: str
    concept_version: int
    entries: List[VariantComparisonEntry]
    created_at: datetime


class AssetSpecDraft(StrictModel):
    asset_spec_draft_id: str
    schema_version: Literal[1] = 1
    status: Literal["draft"] = "draft"
    source_concept_id: str
    source_concept_version: int
    approved_variant_id: str
    approval_decision_id: str
    project_id: str
    feature_id: Optional[str] = None
    task_id: Optional[str] = None
    subject: str
    gameplay_function: str
    proportions: str
    dimensions: DimensionsMeters
    materials: List[str]
    required_views: List[RequiredView]
    platform_budget: PlatformBudget
    style_constraints: List[str]
    forbidden_elements: List[str]
    concept_reference_ids: List[str]
    execution_mode: ExecutionMode
    producing_module: Literal["concept-lab"] = "concept-lab"
    created_by: str
    created_at: datetime
