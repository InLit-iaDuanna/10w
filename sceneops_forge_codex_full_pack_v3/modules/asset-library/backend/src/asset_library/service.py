from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Callable, Iterable, List, Optional, Set

from .repository import AssetRepository
from .schemas import (
    AssetRecord,
    AssetSearchFilter,
    AssetVersion,
    GateStatus,
    PublicationRequest,
    PublicationStatus,
)
from .verification import (
    ArtifactVerifier,
    DenyUnfinalizedCandidate,
    DenyUnverifiedApproval,
    DenyUnverifiedArtifacts,
    FinalizedCandidateResolver,
    PublicationApprovalVerifier,
)


class AssetNotFoundError(LookupError):
    pass


class PublicationBlockedError(ValueError):
    def __init__(self, reasons: List[str]) -> None:
        super().__init__("publication blocked: " + "; ".join(reasons))
        self.reasons = reasons


class AssetLibraryService:
    def __init__(
        self,
        repository: AssetRepository,
        approval_verifier: PublicationApprovalVerifier = DenyUnverifiedApproval(),
        artifact_verifier: ArtifactVerifier = DenyUnverifiedArtifacts(),
        candidate_resolver: FinalizedCandidateResolver = DenyUnfinalizedCandidate(),
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._repository = repository
        self._approval_verifier = approval_verifier
        self._artifact_verifier = artifact_verifier
        self._candidate_resolver = candidate_resolver
        self._clock = clock
        self._publish_lock = Lock()

    def get(self, asset_id: str) -> AssetRecord:
        record = self._repository.get(asset_id)
        if record is None:
            raise AssetNotFoundError(asset_id)
        return record

    def register(self, record: AssetRecord) -> AssetRecord:
        with self._publish_lock:
            existing = self._repository.get(record.spec.asset_id)
            if existing is not None and (
                existing.spec != record.spec
                or existing.source != record.source
                or existing.source_objects != record.source_objects
                or existing.versions != record.versions
            ):
                raise ValueError("registered asset origin and versions are immutable")
            self._repository.save(record)
        return record

    def search(self, filters: AssetSearchFilter) -> List[AssetRecord]:
        records = [record for record in self._repository.list() if self._matches(record, filters)]
        return sorted(records, key=lambda record: record.spec.display_name.casefold())

    def publish(self, request: PublicationRequest) -> AssetVersion:
        with self._publish_lock:
            record = self.get(request.asset_id)
            try:
                candidate = self._candidate_resolver.resolve(request)
            except LookupError as error:
                raise PublicationBlockedError(
                    ["candidate was not resolved from trusted finalized-run storage"]
                ) from error
            reasons = self._publication_blockers(record, request, candidate)
            if reasons:
                raise PublicationBlockedError(reasons)
            published = candidate.model_copy(
                update={
                    "status": PublicationStatus.PUBLISHED,
                    "approval_id": request.approval_id,
                    "published_at": self._clock(),
                },
                deep=True,
            )
            updated = record.model_copy(
                update={"versions": [*record.versions, published]}, deep=True
            )
            self._repository.save(updated)
            return published

    def _publication_blockers(
        self,
        record: AssetRecord,
        request: PublicationRequest,
        candidate: AssetVersion,
    ) -> List[str]:
        reasons: List[str] = []
        if candidate.asset_id != record.spec.asset_id:
            reasons.append("candidate asset_id does not match the catalog record")
        if candidate.source_asset_id != record.source.source_asset_id:
            reasons.append("candidate source_asset_id does not match the catalog record")
        if candidate.asset_version_id != request.asset_version_id:
            reasons.append("resolved candidate does not match the requested asset version")
        if candidate.status != PublicationStatus.APPROVED:
            reasons.append("candidate must be approved before publication")
        if candidate.execution_mode.value not in {"live", "cached", "mock"}:
            reasons.append("approved publication requires an executed mode")
        if candidate.approval_id != request.approval_id:
            reasons.append("candidate approval_id does not match the publication request")
        if candidate.published_at is not None:
            reasons.append("candidate cannot supply its own publication timestamp")
        expected_version = 1 + max((item.version for item in record.versions), default=0)
        if candidate.version != expected_version:
            reasons.append("candidate version must be %d" % expected_version)
        existing_ids = {item.asset_version_id for item in record.versions}
        if candidate.asset_version_id in existing_ids:
            reasons.append("asset_version_id already exists")
        if any(
            identity.source_asset_id != record.source.source_asset_id
            for identity in candidate.object_identities
        ):
            reasons.append("candidate objects do not belong to the catalog source asset")
        available_formats = {artifact.format.casefold() for artifact in candidate.outputs}
        missing_formats = sorted(set(record.spec.required_formats) - available_formats)
        if missing_formats:
            reasons.append("required formats missing: " + ", ".join(missing_formats))
        metrics = candidate.metrics
        if metrics.triangle_count > record.spec.triangle_budget:
            reasons.append("candidate exceeds the catalog triangle budget")
        if record.spec.requires_uv and not metrics.has_uv:
            reasons.append("catalog AssetSpec requires UV data")
        if record.spec.requires_rig and not metrics.is_rigged:
            reasons.append("catalog AssetSpec requires a rig")
        if record.spec.requires_lods and metrics.lod_count < 1:
            reasons.append("catalog AssetSpec requires at least one LOD")
        if record.spec.requires_collider and not metrics.collider_kind:
            reasons.append("catalog AssetSpec requires a collider")
        if any(
            item.source_project != record.spec.project_id
            for item in candidate.provenance
        ):
            reasons.append("artifact provenance project does not match the catalog record")
        gate_by_id = {gate.gate_id: gate for gate in candidate.quality_gates}
        missing = sorted(set(record.spec.required_gate_ids) - set(gate_by_id))
        if missing:
            reasons.append("required gates not run: " + ", ".join(missing))
        failed = sorted(
            gate.gate_id
            for gate in candidate.quality_gates
            if gate.blocking and gate.status != GateStatus.PASSED
        )
        if failed:
            reasons.append("blocking gates did not pass: " + ", ".join(failed))
        reasons.extend(self._approval_verifier.verify(request, candidate))
        for artifact in candidate.outputs:
            reasons.extend(self._artifact_verifier.verify(record.spec.project_id, artifact))
        return reasons

    def _matches(self, record: AssetRecord, filters: AssetSearchFilter) -> bool:
        latest = record.latest_version
        if filters.project_id and record.spec.project_id != filters.project_id:
            return False
        haystack = " ".join(
            [
                record.spec.asset_id,
                record.spec.display_name,
                record.spec.category,
                record.spec.description,
                record.spec.intended_use,
                record.source.source_asset_id,
                record.source.source_version,
                record.source.license_name,
                record.source.project_relative_path,
                record.source.origin_uri or "",
                *(version.asset_version_id for version in record.versions),
                *(output.format for version in record.versions for output in version.outputs),
                *(
                    provenance.ai.provider
                    for version in record.versions
                    for provenance in version.provenance
                    if provenance.ai
                ),
                *(
                    provenance.ai.model
                    for version in record.versions
                    for provenance in version.provenance
                    if provenance.ai
                ),
                *(usage.scene_id for usage in record.usage_references),
                *(usage.scene_instance_id for usage in record.usage_references),
                *(usage.unity_prefab_id or "" for usage in record.usage_references),
                *(
                    build_id
                    for usage in record.usage_references
                    for build_id in usage.build_ids
                ),
            ]
        ).casefold()
        if filters.query.casefold() not in haystack:
            return False
        if filters.license_name and record.source.license_name != filters.license_name:
            return False
        if latest is None:
            return not self._requires_published_metrics(filters)
        formats: Set[str] = {item.format.casefold() for item in latest.outputs}
        if filters.formats and not set(item.casefold() for item in filters.formats).issubset(formats):
            return False
        metrics = latest.metrics
        checks = (
            (filters.has_uv, metrics.has_uv),
            (filters.rigged, metrics.is_rigged),
            (filters.has_animations, bool(metrics.animation_names)),
            (filters.has_lod, metrics.lod_count > 0),
            (filters.has_collider, metrics.collider_kind is not None),
            (
                filters.has_ai_provenance,
                any(item.ai is not None for item in latest.provenance),
            ),
        )
        if any(expected is not None and expected != actual for expected, actual in checks):
            return False
        if filters.min_triangles is not None and metrics.triangle_count < filters.min_triangles:
            return False
        if filters.max_triangles is not None and metrics.triangle_count > filters.max_triangles:
            return False
        if filters.gate_status and not any(
            gate.status == filters.gate_status for gate in latest.quality_gates
        ):
            return False
        if filters.execution_modes and latest.execution_mode not in filters.execution_modes:
            return False
        if filters.unity_status and not any(
            usage.unity_status == filters.unity_status
            for usage in record.usage_references
            if usage.asset_version_id == latest.asset_version_id
        ):
            return False
        return True

    @staticmethod
    def _requires_published_metrics(filters: AssetSearchFilter) -> bool:
        return any(
            value is not None and value != []
            for value in (
                filters.formats,
                filters.gate_status,
                filters.unity_status,
                filters.has_uv,
                filters.rigged,
                filters.has_animations,
                filters.has_lod,
                filters.has_collider,
                filters.has_ai_provenance,
                filters.min_triangles,
                filters.max_triangles,
                filters.execution_modes,
            )
        )
