"""Fail-closed authority used until trusted upstream adapters are composed."""

from __future__ import annotations

from .models_build import BuildManifest, BuildMatrix, BuildRun
from .models_common import Approval
from .ports import AuthorityVerification


class UnavailableReleaseAuthority:
    def verify_source(
        self,
        matrix: BuildMatrix,
        run: BuildRun,
        manifest: BuildManifest,
    ) -> AuthorityVerification:
        return AuthorityVerification(
            verified=False,
            code="SOURCE_AUTHORITY_UNAVAILABLE",
            message=(
                "Authoritative Git cleanliness and build provenance are not configured."
            ),
        )

    def verify_approval(self, approval: Approval) -> AuthorityVerification:
        return AuthorityVerification(
            verified=False,
            code="APPROVAL_AUTHORITY_UNAVAILABLE",
            message="Authoritative approval resolution is not configured.",
        )
