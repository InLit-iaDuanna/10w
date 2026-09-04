from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable, List

from .errors import ReviewGateError
from .schemas import (
    ConceptSpec,
    ConceptVariant,
    ReviewVerdict,
    StyleAssessment,
    StyleCheck,
    StyleEvidenceInput,
)


def evaluate_declared_style_evidence(
    spec: ConceptSpec,
    variant: ConceptVariant,
    evidence: Iterable[StyleEvidenceInput],
    *,
    style_check_id: str,
    created_by: str,
    now: datetime,
) -> StyleCheck:
    items = list(evidence)
    if not items:
        raise ReviewGateError("STYLE_EVIDENCE_REQUIRED", "Style evidence is required.")

    expected = {
        ("style_constraint", criterion) for criterion in spec.style_constraints
    } | {("forbidden_element", criterion) for criterion in spec.forbidden_elements}
    submitted = {(item.criterion_kind, item.criterion) for item in items}
    unexpected = submitted - expected
    if unexpected:
        raise ReviewGateError(
            "UNKNOWN_STYLE_CRITERION",
            "Style evidence references a criterion outside this concept version.",
            criteria=sorted(f"{kind}:{value}" for kind, value in unexpected),
        )

    duplicates = _duplicates(items, lambda item: (item.criterion_kind, item.criterion))
    if duplicates:
        raise ReviewGateError(
            "DUPLICATE_STYLE_EVIDENCE",
            "Each style criterion accepts one evidence statement per check.",
            criteria=duplicates,
        )

    unevaluated = sorted(criterion for _, criterion in expected - submitted)
    coverage = len(submitted) / len(expected) if expected else 1.0
    confidence = sum(item.confidence for item in items) / len(items)
    verdicts = {item.verdict for item in items}

    if ReviewVerdict.MISMATCH in verdicts:
        assessment = StyleAssessment.INCONSISTENT
    elif ReviewVerdict.UNCERTAIN in verdicts or unevaluated:
        assessment = StyleAssessment.NEEDS_REVIEW
    else:
        assessment = StyleAssessment.CONSISTENT

    return StyleCheck(
        style_check_id=style_check_id,
        concept_id=spec.concept_id,
        concept_version=spec.version,
        variant_id=variant.variant_id,
        evidence=items,
        assessment=assessment,
        confidence=round(confidence, 4),
        evidence_coverage=round(coverage, 4),
        unevaluated_criteria=unevaluated,
        created_by=created_by,
        created_at=now,
    )


def _duplicates(items: List[StyleEvidenceInput], key: Callable) -> List[str]:
    seen = set()
    duplicates = set()
    for item in items:
        value = key(item)
        if value in seen:
            duplicates.add(f"{value[0]}:{value[1]}")
        seen.add(value)
    return sorted(duplicates)
