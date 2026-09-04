from __future__ import annotations

from typing import List, Protocol

from .schemas import ArtifactOutput, AssetVersion, PublicationRequest


class PublicationApprovalVerifier(Protocol):
    def verify(
        self, request: PublicationRequest, candidate: AssetVersion
    ) -> List[str]: ...


class ArtifactVerifier(Protocol):
    def verify(self, project_id: str, artifact: ArtifactOutput) -> List[str]: ...


class FinalizedCandidateResolver(Protocol):
    def resolve(self, request: PublicationRequest) -> AssetVersion: ...


class DenyUnverifiedApproval:
    def verify(self, request: PublicationRequest, candidate: AssetVersion) -> List[str]:
        return ["publication approval was not verified by an authority"]


class DenyUnverifiedArtifacts:
    def verify(self, project_id: str, artifact: ArtifactOutput) -> List[str]:
        return ["artifact was not verified by trusted storage: " + artifact.artifact_id]


class DenyUnfinalizedCandidate:
    def resolve(self, request: PublicationRequest) -> AssetVersion:
        raise LookupError("finalized asset version is unavailable")
