from __future__ import annotations

from typing import Optional

from .repository import ConceptRepository
from .workspace_schemas import ConceptReviewWorkspace


class ConceptWorkspaceReader:
    def __init__(self, repository: ConceptRepository) -> None:
        self.repository = repository

    def get(
        self, concept_id: str, version: Optional[int] = None
    ) -> ConceptReviewWorkspace:
        record = self.repository.get(concept_id)
        spec = record.spec_at(version) if version else record.latest_spec
        variant_ids = {
            value.variant_id
            for value in record.variants.values()
            if value.concept_version == spec.version
        }
        return ConceptReviewWorkspace(
            concept=spec,
            references=sorted(
                (
                    value
                    for value in record.references.values()
                    if value.concept_version == spec.version
                ),
                key=lambda value: value.reference_id,
            ),
            variants=sorted(
                (
                    value
                    for value in record.variants.values()
                    if value.variant_id in variant_ids
                ),
                key=lambda value: value.variant_id,
            ),
            style_checks=sorted(
                (
                    value
                    for checks in record.style_checks.values()
                    for value in checks
                    if value.concept_version == spec.version
                ),
                key=lambda value: value.style_check_id,
            ),
            comments=sorted(
                (
                    value
                    for values in record.comments.values()
                    for value in values
                    if value.variant_id in variant_ids
                ),
                key=lambda value: value.comment_id,
            ),
            decisions=[
                value
                for value in record.decisions
                if value.concept_version == spec.version
            ],
            change_sets=sorted(
                record.change_sets.values(), key=lambda value: value.change_set_id
            ),
            generation_runs=sorted(
                (
                    value
                    for value in record.generation_runs.values()
                    if value.request.concept_version == spec.version
                ),
                key=lambda value: value.run_id,
            ),
            asset_spec_drafts=sorted(
                (
                    value
                    for value in record.asset_spec_drafts.values()
                    if value.source_concept_version == spec.version
                ),
                key=lambda value: value.asset_spec_draft_id,
            ),
        )
