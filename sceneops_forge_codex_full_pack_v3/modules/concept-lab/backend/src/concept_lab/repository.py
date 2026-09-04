from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Protocol

from .errors import NotFoundError
from .generation_schemas import GenerationRun
from .schemas import (
    AssetSpecDraft,
    ConceptChangeSet,
    ConceptDecision,
    ConceptReference,
    ConceptSpec,
    ConceptVariant,
    StyleCheck,
    VariantComment,
)


@dataclass
class ConceptRecord:
    specs: List[ConceptSpec]
    references: Dict[str, ConceptReference] = field(default_factory=dict)
    variants: Dict[str, ConceptVariant] = field(default_factory=dict)
    change_sets: Dict[str, ConceptChangeSet] = field(default_factory=dict)
    style_checks: Dict[str, List[StyleCheck]] = field(default_factory=dict)
    comments: Dict[str, List[VariantComment]] = field(default_factory=dict)
    decisions: List[ConceptDecision] = field(default_factory=list)
    generation_runs: Dict[str, GenerationRun] = field(default_factory=dict)
    asset_spec_drafts: Dict[str, AssetSpecDraft] = field(default_factory=dict)

    @property
    def latest_spec(self) -> ConceptSpec:
        return self.specs[-1]

    def spec_at(self, version: int) -> ConceptSpec:
        for spec in self.specs:
            if spec.version == version:
                return spec
        raise NotFoundError("concept version", f"{self.latest_spec.concept_id}@{version}")


class ConceptRepository(Protocol):
    def add(self, record: ConceptRecord) -> None: ...

    def get(self, concept_id: str) -> ConceptRecord: ...

    def save(self, concept_id: str, record: ConceptRecord) -> None: ...


class InMemoryConceptRepository:
    """Deterministic development repository; production persistence is injected."""

    def __init__(self) -> None:
        self._records: Dict[str, ConceptRecord] = {}

    def add(self, record: ConceptRecord) -> None:
        concept_id = record.latest_spec.concept_id
        if concept_id in self._records:
            raise ValueError(f"concept already exists: {concept_id}")
        self._records[concept_id] = deepcopy(record)

    def get(self, concept_id: str) -> ConceptRecord:
        try:
            return deepcopy(self._records[concept_id])
        except KeyError as error:
            raise NotFoundError("concept", concept_id) from error

    def save(self, concept_id: str, record: ConceptRecord) -> None:
        if concept_id not in self._records:
            raise NotFoundError("concept", concept_id)
        self._records[concept_id] = deepcopy(record)
