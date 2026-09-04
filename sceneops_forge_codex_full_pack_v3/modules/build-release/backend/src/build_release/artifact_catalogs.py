"""Typed artifact integrity catalogs for fixtures and configured files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .adapter_support import resolve_regular_file, validated_root
from .checksum import file_sha256
from .enums import ExecutionMode
from .models_common import ArtifactRef
from .ports import ArtifactInspection


class StaticArtifactCatalog:
    def __init__(self, inspections: Dict[str, ArtifactInspection]) -> None:
        self._inspections = dict(inspections)
        self._artifacts: Dict[str, ArtifactRef] = {}

    @classmethod
    def matching(cls, artifacts: List[ArtifactRef]) -> "StaticArtifactCatalog":
        catalog = cls({})
        for artifact in artifacts:
            catalog.register_matching(artifact)
        return catalog

    def inspect(self, artifact: ArtifactRef) -> ArtifactInspection:
        inspection = self._inspections.get(
            artifact.artifact_id,
            ArtifactInspection(
                artifact_id=artifact.artifact_id,
                available=False,
                checksum_matches=False,
                size_matches=False,
                reason="Artifact is not registered in the catalog.",
            ),
        )
        registered = self._artifacts.get(artifact.artifact_id)
        if registered is not None and registered != artifact:
            return ArtifactInspection(
                artifact_id=artifact.artifact_id,
                available=False,
                checksum_matches=False,
                size_matches=False,
                reason="Artifact metadata differs from its registered immutable record.",
            )
        if artifact.mode == ExecutionMode.CACHED and not self._has_live_origin(artifact):
            return ArtifactInspection(
                artifact_id=artifact.artifact_id,
                available=False,
                checksum_matches=False,
                size_matches=False,
                reason="Cached artifact has no matching prior live artifact record.",
            )
        return inspection

    def register_matching(self, artifact: ArtifactRef) -> None:
        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None and existing != artifact:
            raise ValueError(
                "artifact ID is already registered with different immutable metadata"
            )
        self._artifacts[artifact.artifact_id] = artifact
        self._inspections[artifact.artifact_id] = ArtifactInspection(
            artifact_id=artifact.artifact_id,
            available=True,
            checksum_matches=True,
            size_matches=True,
            observed_checksum=artifact.checksum,
            observed_size_bytes=artifact.size_bytes,
            reason="Artifact is present and matches the declared integrity metadata.",
        )

    def register_inspection(self, inspection: ArtifactInspection) -> None:
        self._inspections[inspection.artifact_id] = inspection

    def _has_live_origin(self, artifact: ArtifactRef) -> bool:
        origin = self._artifacts.get(artifact.origin_live_artifact_id or "")
        return bool(
            origin
            and origin.mode == ExecutionMode.LIVE
            and origin.build_run_id == artifact.origin_live_run_id
            and origin.project_id == artifact.project_id
            and origin.game_id == artifact.game_id
            and origin.artifact_type == artifact.artifact_type
            and origin.version == artifact.version
            and origin.source_commit.lower() == artifact.source_commit.lower()
            and origin.checksum == artifact.checksum
            and origin.size_bytes == artifact.size_bytes
        )


class FileArtifactCatalog:
    def __init__(self, artifact_root: Path) -> None:
        self._artifact_root = validated_root(artifact_root)

    def inspect(self, artifact: ArtifactRef) -> ArtifactInspection:
        if artifact.mode == ExecutionMode.CACHED:
            return ArtifactInspection(
                artifact_id=artifact.artifact_id,
                available=False,
                checksum_matches=False,
                size_matches=False,
                reason=(
                    "File catalog cannot verify cached provenance without an "
                    "authoritative prior-live record."
                ),
            )
        try:
            path = resolve_regular_file(self._artifact_root, artifact.uri)
        except (OSError, ValueError) as exc:
            return ArtifactInspection(
                artifact_id=artifact.artifact_id,
                available=False,
                checksum_matches=False,
                size_matches=False,
                reason=str(exc),
            )
        observed_checksum = file_sha256(path)
        observed_size = path.stat().st_size
        matches = (
            observed_checksum == artifact.checksum
            and observed_size == artifact.size_bytes
        )
        return ArtifactInspection(
            artifact_id=artifact.artifact_id,
            available=True,
            checksum_matches=observed_checksum == artifact.checksum,
            size_matches=observed_size == artifact.size_bytes,
            observed_checksum=observed_checksum,
            observed_size_bytes=observed_size,
            reason=(
                "Artifact is present and verified."
                if matches
                else "Artifact bytes or size do not match the declared integrity metadata."
            ),
        )
