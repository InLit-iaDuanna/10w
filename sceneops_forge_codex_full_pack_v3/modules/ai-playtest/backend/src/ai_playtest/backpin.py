from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Sequence

from .schemas import (
    Backpin,
    BackpinStatus,
    EvidenceBundle,
    FailureSignal,
    SourceCandidate,
)


@dataclass(frozen=True)
class BackpinPolicy:
    minimum_confidence: float = 0.70
    ambiguity_margin: float = 0.10


class BackpinReviewError(ValueError):
    code = "BACKPIN_REVIEW_INVALID"


class BackpinResolver:
    def __init__(self, policy: BackpinPolicy = BackpinPolicy()):
        self.policy = policy

    def resolve(
        self,
        backpin_id: str,
        signal: FailureSignal,
        evidence: EvidenceBundle,
        candidates: Sequence[SourceCandidate],
    ) -> Backpin:
        eligible = [
            candidate for candidate in candidates if candidate.build_id == evidence.build_id
        ]
        ranked = sorted(
            ((self._score(signal, evidence, candidate), candidate) for candidate in eligible),
            key=lambda item: (-item[0], item[1].target_id),
        )
        if not ranked or ranked[0][0] < self.policy.minimum_confidence:
            return Backpin(
                backpin_id=backpin_id,
                status=BackpinStatus.UNRESOLVED,
                confidence=ranked[0][0] if ranked else 0,
                evidence_ids=[evidence.evidence_id],
                reasons=["没有候选源达到配置的最低置信度。"],
                alternatives=[item[1].target_id for item in ranked[:3]],
            )
        top_score, top = ranked[0]
        ambiguous = len(ranked) > 1 and top_score - ranked[1][0] < self.policy.ambiguity_margin
        status = BackpinStatus.AMBIGUOUS if ambiguous else BackpinStatus.RESOLVED
        return Backpin(
            backpin_id=backpin_id,
            source_record_id=top.source_record_id,
            source_record_uri=top.source_record_uri,
            target_type=top.target_type,
            target_id=top.target_id,
            sceneops_id=top.sceneops_id,
            locator=top.locator,
            owning_module=top.owning_module,
            status=status,
            confidence=top_score,
            evidence_ids=[evidence.evidence_id] + top.evidence_artifact_ids,
            reasons=self._reasons(signal, evidence, top),
            alternatives=[candidate.target_id for _, candidate in ranked[1:4]],
        )

    def reject(
        self, backpin: Backpin, reviewer_id: str, reviewed_at: datetime
    ) -> Backpin:
        self._require_unreviewed(backpin)
        payload = backpin.model_dump(mode="python")
        payload.update(
            {
                "status": BackpinStatus.REJECTED,
                "reviewed_by": reviewer_id,
                "reviewed_at": reviewed_at,
                "reasons": backpin.reasons + ["人工审核拒绝此候选；原始证据已保留。"],
            }
        )
        return Backpin.model_validate(payload)

    def confirm(
        self, backpin: Backpin, reviewer_id: str, reviewed_at: datetime
    ) -> Backpin:
        self._require_unreviewed(backpin)
        if backpin.status != BackpinStatus.RESOLVED:
            raise BackpinReviewError("only a uniquely resolved backpin can be confirmed")
        payload = backpin.model_dump(mode="python")
        payload.update(
            {
                "reviewed_by": reviewer_id,
                "reviewed_at": reviewed_at,
                "reasons": backpin.reasons + ["人工审核确认此回钉候选。"],
            }
        )
        return Backpin.model_validate(payload)

    @staticmethod
    def _require_unreviewed(backpin: Backpin) -> None:
        if backpin.reviewed_by or backpin.reviewed_at:
            raise BackpinReviewError("backpin review is already recorded")

    @staticmethod
    def _score(
        signal: FailureSignal,
        evidence: EvidenceBundle,
        candidate: SourceCandidate,
    ) -> float:
        score = 0.0
        if signal.target_sceneops_id and signal.target_sceneops_id == candidate.sceneops_id:
            score += 0.55
        elif signal.target_sceneops_id in candidate.related_sceneops_ids:
            score += 0.40
        if signal.kind in candidate.failure_kinds:
            score += 0.25
        if set(signal.evidence_artifact_ids).intersection(
            candidate.evidence_artifact_ids
        ):
            score += 0.15
        if evidence.build_id == candidate.build_id:
            score += 0.05
        return min(score, 1.0)

    @staticmethod
    def _reasons(
        signal: FailureSignal,
        evidence: EvidenceBundle,
        candidate: SourceCandidate,
    ) -> List[str]:
        reasons = []
        if signal.target_sceneops_id == candidate.sceneops_id:
            reasons.append("运行时 target sceneops_id 与源候选精确一致。")
        elif signal.target_sceneops_id in candidate.related_sceneops_ids:
            reasons.append("源候选显式声明与运行时目标的因果关系。")
        if signal.kind in candidate.failure_kinds:
            reasons.append("源候选声明可解释该故障类别。")
        if set(signal.evidence_artifact_ids).intersection(
            candidate.evidence_artifact_ids
        ):
            reasons.append("源候选与故障信号共享证据工件。")
        if evidence.build_id == candidate.build_id:
            reasons.append("源候选元数据来自同一构建。")
        return reasons
