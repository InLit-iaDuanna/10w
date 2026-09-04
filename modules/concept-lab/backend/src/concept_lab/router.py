from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from .errors import ConceptLabError
from .generation_schemas import GenerationOutcome, GenerationRequest
from .schemas import (
    AssetSpecDraft,
    ConceptChangeSet,
    ConceptCreateInput,
    ConceptDecision,
    ConceptPatch,
    ConceptReference,
    ConceptSpec,
    ConceptVariant,
    ImportedReferenceInput,
    ReviewAction,
    StrictModel,
    StyleCheck,
    StyleEvidenceInput,
    VariantComment,
    VariantComparison,
)
from .service import ConceptLabService
from .workspace_schemas import ConceptReviewWorkspace


class CommandContext(StrictModel):
    actor_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)


class CreateConceptRequest(StrictModel):
    command: CommandContext
    concept: ConceptCreateInput


class ProposeChangeRequest(StrictModel):
    base_version: int = Field(ge=1)
    patch: ConceptPatch
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: List[str] = Field(min_length=1)
    risk: Literal["low", "medium", "high"]
    validation_plan: List[str] = Field(min_length=1)
    rollback_plan: str = Field(min_length=1)
    proposed_by: str = Field(min_length=1)
    proposed_by_type: Literal["user", "agent"]


class ApproveChangeRequest(StrictModel):
    reviewer_id: str = Field(min_length=1)


class ApplyChangeRequest(StrictModel):
    command: CommandContext


class ImportReferenceRequest(StrictModel):
    concept_version: int = Field(ge=1)
    reference: ImportedReferenceInput


class ImportVariantRequest(StrictModel):
    command: CommandContext
    concept_version: int = Field(ge=1)
    title: str = Field(min_length=1)
    reference_ids: List[str] = Field(min_length=1)


class GenerateVariantRequest(StrictModel):
    command: CommandContext
    generation: GenerationRequest


class StyleCheckRequest(StrictModel):
    concept_version: int = Field(ge=1)
    created_by: str = Field(min_length=1)
    evidence: List[StyleEvidenceInput] = Field(min_length=1)


class CommentRequest(StrictModel):
    body: str = Field(min_length=1)
    author_id: str = Field(min_length=1)


class CompareRequest(StrictModel):
    concept_version: int = Field(ge=1)
    variant_ids: List[str] = Field(min_length=2)


class ReviewRequest(StrictModel):
    command: CommandContext
    concept_version: int = Field(ge=1)
    action: ReviewAction
    rationale: str = Field(min_length=1)
    acknowledge_license_warning: bool = False


class CompileAssetSpecRequest(StrictModel):
    command: CommandContext
    concept_version: int = Field(ge=1)
    variant_id: str = Field(min_length=1)


def create_router(service: ConceptLabService) -> APIRouter:
    router = APIRouter(prefix="/v1/concepts", tags=["concept-lab"])

    @router.post("", response_model=ConceptSpec, status_code=201)
    def create_concept(request: CreateConceptRequest) -> ConceptSpec:
        return service.create_concept(
            request.concept,
            actor_id=request.command.actor_id,
            correlation_id=request.command.correlation_id,
            causation_id=request.command.causation_id,
        )

    @router.get("/{concept_id}", response_model=ConceptSpec)
    def get_concept(concept_id: str, version: Optional[int] = None) -> ConceptSpec:
        return service.get_concept(concept_id, version)

    @router.get("/{concept_id}/versions", response_model=List[ConceptSpec])
    def list_versions(concept_id: str) -> List[ConceptSpec]:
        return service.list_versions(concept_id)

    @router.get("/{concept_id}/review-workspace", response_model=ConceptReviewWorkspace)
    def review_workspace(
        concept_id: str, version: Optional[int] = None
    ) -> ConceptReviewWorkspace:
        return service.get_review_workspace(concept_id, version)

    @router.post(
        "/{concept_id}/changes", response_model=ConceptChangeSet, status_code=201
    )
    def propose_change(
        concept_id: str, request: ProposeChangeRequest
    ) -> ConceptChangeSet:
        return service.propose_change(concept_id, **request.model_dump())

    @router.post(
        "/{concept_id}/changes/{change_set_id}/approve",
        response_model=ConceptChangeSet,
    )
    def approve_change(
        concept_id: str, change_set_id: str, request: ApproveChangeRequest
    ) -> ConceptChangeSet:
        return service.approve_change(concept_id, change_set_id, request.reviewer_id)

    @router.post(
        "/{concept_id}/changes/{change_set_id}/apply", response_model=ConceptSpec
    )
    def apply_change(
        concept_id: str, change_set_id: str, request: ApplyChangeRequest
    ) -> ConceptSpec:
        return service.apply_change(
            concept_id,
            change_set_id,
            actor_id=request.command.actor_id,
            correlation_id=request.command.correlation_id,
            causation_id=request.command.causation_id,
        )

    @router.post(
        "/{concept_id}/references", response_model=ConceptReference, status_code=201
    )
    def import_reference(
        concept_id: str, request: ImportReferenceRequest
    ) -> ConceptReference:
        return service.import_reference(
            concept_id, request.concept_version, request.reference
        )

    @router.post(
        "/{concept_id}/variants/import", response_model=ConceptVariant, status_code=201
    )
    def import_variant(
        concept_id: str, request: ImportVariantRequest
    ) -> ConceptVariant:
        return service.create_imported_variant(
            concept_id,
            request.concept_version,
            title=request.title,
            reference_ids=request.reference_ids,
            actor_id=request.command.actor_id,
            correlation_id=request.command.correlation_id,
            causation_id=request.command.causation_id,
        )

    @router.post(
        "/{concept_id}/variants/generate",
        response_model=GenerationOutcome,
        status_code=202,
    )
    def generate_variant(
        concept_id: str, request: GenerateVariantRequest
    ) -> GenerationOutcome:
        if concept_id != request.generation.concept_id:
            raise ConceptLabError(
                "CONCEPT_ID_MISMATCH",
                "Path concept ID and generation request concept ID differ.",
            )
        return service.generate_variant(
            request.generation,
            actor_id=request.command.actor_id,
            correlation_id=request.command.correlation_id,
            causation_id=request.command.causation_id,
        )

    @router.post(
        "/{concept_id}/variants/{variant_id}/style-checks",
        response_model=StyleCheck,
        status_code=201,
    )
    def add_style_check(
        concept_id: str, variant_id: str, request: StyleCheckRequest
    ) -> StyleCheck:
        return service.add_style_check(
            concept_id,
            request.concept_version,
            variant_id,
            request.evidence,
            created_by=request.created_by,
        )

    @router.post(
        "/{concept_id}/variants/{variant_id}/comments",
        response_model=VariantComment,
        status_code=201,
    )
    def comment(
        concept_id: str, variant_id: str, request: CommentRequest
    ) -> VariantComment:
        return service.comment_on_variant(
            concept_id, variant_id, request.body, request.author_id
        )

    @router.post("/{concept_id}/comparisons", response_model=VariantComparison)
    def compare(concept_id: str, request: CompareRequest) -> VariantComparison:
        return service.compare_variants(
            concept_id, request.concept_version, request.variant_ids
        )

    @router.post(
        "/{concept_id}/variants/{variant_id}/review",
        response_model=ConceptDecision,
    )
    def review(
        concept_id: str, variant_id: str, request: ReviewRequest
    ) -> ConceptDecision:
        return service.review_variant(
            concept_id,
            request.concept_version,
            variant_id,
            request.action,
            rationale=request.rationale,
            reviewer_id=request.command.actor_id,
            acknowledge_license_warning=request.acknowledge_license_warning,
            correlation_id=request.command.correlation_id,
            causation_id=request.command.causation_id,
        )

    @router.post(
        "/{concept_id}/asset-spec-drafts",
        response_model=AssetSpecDraft,
        status_code=201,
    )
    def compile_asset_spec(
        concept_id: str, request: CompileAssetSpecRequest
    ) -> AssetSpecDraft:
        return service.compile_asset_spec_draft(
            concept_id,
            request.concept_version,
            request.variant_id,
            actor_id=request.command.actor_id,
            correlation_id=request.command.correlation_id,
            causation_id=request.command.causation_id,
        )

    return router


def concept_lab_error_handler(_: Request, error: ConceptLabError) -> JSONResponse:
    status = 404 if error.code == "NOT_FOUND" else 409
    if error.code == "INTEGRATION_OFFLINE":
        status = 503
    return JSONResponse(
        status_code=status,
        content={
            "code": error.code,
            "message": error.message,
            "details": error.details,
            "request_id": None,
            "retryable": error.retryable,
            "suggested_actions": error.suggested_actions,
        },
    )
