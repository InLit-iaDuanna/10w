from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable, List, Optional

from .errors import NotFoundError
from .repository import ConceptRecord
from .schemas import (
    AiGenerationMetadata,
    ConceptReference,
    ConceptSpec,
    ConceptStatus,
    ConceptVariant,
    ExecutionMode,
)


IdFactory = Callable[[str], str]
Clock = Callable[[], datetime]


def get_variant(
    record: ConceptRecord, variant_id: str, version: Optional[int] = None
) -> ConceptVariant:
    try:
        variant = record.variants[variant_id]
    except KeyError as error:
        raise NotFoundError("concept variant", variant_id) from error
    if version is not None and variant.concept_version != version:
        raise NotFoundError("concept variant version", f"{variant_id}@{version}")
    return variant


def get_references(
    record: ConceptRecord, reference_ids: Iterable[str]
) -> List[ConceptReference]:
    values = []
    for reference_id in reference_ids:
        try:
            values.append(record.references[reference_id])
        except KeyError as error:
            raise NotFoundError("concept reference", reference_id) from error
    return values


def attach_reference_to_spec(
    record: ConceptRecord, reference_id: str, version: int
) -> None:
    for index, spec in enumerate(record.specs):
        if spec.version == version:
            record.specs[index] = spec.model_copy(
                update={"reference_ids": [*spec.reference_ids, reference_id]}
            )
            return


def set_spec_status(
    record: ConceptRecord, version: int, status: ConceptStatus
) -> None:
    for index, spec in enumerate(record.specs):
        if spec.version == version:
            record.specs[index] = spec.model_copy(update={"status": status})
            return


def new_variant(
    spec: ConceptSpec,
    title: str,
    references: List[ConceptReference],
    mode: ExecutionMode,
    id_factory: IdFactory,
    clock: Clock,
    generation: Optional[AiGenerationMetadata] = None,
) -> ConceptVariant:
    return ConceptVariant(
        variant_id=id_factory("var"),
        concept_id=spec.concept_id,
        concept_version=spec.version,
        title=title,
        reference_ids=[reference.reference_id for reference in references],
        covered_views=list(dict.fromkeys(reference.view for reference in references)),
        execution_mode=mode,
        generation=generation,
        created_at=clock(),
    )


def derived_mode(modes: Iterable[ExecutionMode]) -> ExecutionMode:
    values = set(modes)
    for mode in (
        ExecutionMode.BLOCKED,
        ExecutionMode.PLANNED,
        ExecutionMode.MOCK,
        ExecutionMode.CACHED,
    ):
        if mode in values:
            return mode
    return ExecutionMode.LIVE
