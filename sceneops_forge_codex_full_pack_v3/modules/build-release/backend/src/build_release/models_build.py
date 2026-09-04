"""Build matrix, run, and immutable manifest contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from pydantic import Field, StringConstraints, ValidationInfo, field_validator, model_validator
from typing_extensions import Annotated

from .checksum import canonical_sha256
from .enums import BuildProfile, ExecutionMode, RunStatus
from .models_common import (
    ArtifactRef,
    DomainModel,
    GateEvidence,
    GitCommit,
    Sha256Digest,
    StableId,
    UtcModel,
    VersionBinding,
)

SourceIdentity = Annotated[
    str,
    StringConstraints(pattern=r"^git:(sha1|sha256):[a-fA-F0-9]{40,64}$"),
]


class BuildTarget(DomainModel):
    target_id: StableId
    profile: BuildProfile
    platform: str = Field(min_length=1, max_length=80)
    architecture: str = Field(min_length=1, max_length=80)
    variant: str = Field(min_length=1, max_length=80)
    settings: Dict[str, Any] = Field(min_length=1)


class BuildMatrix(UtcModel):
    matrix_id: StableId
    project_id: StableId
    game_id: StableId
    source_commit: GitCommit
    targets: List[BuildTarget] = Field(min_length=1)
    created_at: datetime

    @field_validator("targets")
    @classmethod
    def targets_are_unique(cls, value: List[BuildTarget]) -> List[BuildTarget]:
        target_ids = [target.target_id for target in value]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("target_id values must be unique")
        coordinates = [
            (target.profile, target.platform, target.architecture, target.variant)
            for target in value
        ]
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("build target coordinates must be unique")
        return value

    @property
    def supported_profiles(self) -> Set[BuildProfile]:
        return {target.profile for target in self.targets}


class BuildManifest(UtcModel):
    manifest_id: StableId
    build_run_id: StableId
    matrix_id: StableId
    target_id: StableId
    target_definition: BuildTarget
    project_id: StableId
    game_id: StableId
    profile: BuildProfile
    mode: ExecutionMode
    source_commit: GitCommit
    source_identity: SourceIdentity
    source_dirty: bool
    module_catalog: Dict[str, str] = Field(min_length=1)
    project_bible_version: str = Field(min_length=1, max_length=120)
    project_bible_checksum: Sha256Digest
    asset_versions: Dict[str, VersionBinding] = Field(min_length=1)
    scene_snapshots: Dict[str, VersionBinding] = Field(min_length=1)
    unity_version: str = Field(min_length=1, max_length=120)
    unity_packages: Dict[str, str] = Field(min_length=1)
    build_recipe_version: str = Field(min_length=1, max_length=120)
    settings: Dict[str, Any] = Field(min_length=1)
    test_evidence: List[GateEvidence] = Field(min_length=1)
    artifacts: List[ArtifactRef] = Field(min_length=1)
    created_at: datetime
    manifest_checksum: Sha256Digest

    @field_validator(
        "module_catalog",
        "asset_versions",
        "scene_snapshots",
        "unity_packages",
        "settings",
    )
    @classmethod
    def mappings_have_nonempty_keys_and_values(
        cls, value: Dict[str, Any]
    ) -> Dict[str, Any]:
        if any(not str(key).strip() or item in (None, "") for key, item in value.items()):
            raise ValueError("manifest maps cannot contain empty keys or values")
        return value

    @model_validator(mode="after")
    def validate_manifest(self, info: ValidationInfo) -> "BuildManifest":
        _, algorithm, identity_commit = self.source_identity.split(":", 2)
        expected_length = 40 if algorithm == "sha1" else 64
        if (
            len(identity_commit) != expected_length
            or identity_commit.lower() != self.source_commit.lower()
        ):
            raise ValueError("source_identity must tag the exact Git object ID")
        if (
            self.target_definition.target_id != self.target_id
            or self.target_definition.profile != self.profile
        ):
            raise ValueError("target_definition must match target_id and profile")
        all_artifacts = [*self.test_evidence, *self.artifacts]
        if len({artifact.artifact_id for artifact in all_artifacts}) != len(all_artifacts):
            raise ValueError("artifact IDs must be unique within a manifest")
        for artifact in all_artifacts:
            if artifact.source_commit.lower() != self.source_commit.lower():
                raise ValueError("artifact source_commit must match the manifest")
            if artifact.project_id != self.project_id or artifact.game_id != self.game_id:
                raise ValueError("artifact project and game must match the manifest")
            if artifact.build_run_id != self.build_run_id:
                raise ValueError("artifact build_run_id must match the manifest")
            if artifact.mode != self.mode:
                raise ValueError("artifact execution mode must match the manifest")
        expected = canonical_sha256(self.checksummed_payload())
        allow_placeholder = bool(info.context and info.context.get("allow_checksum_placeholder"))
        if not allow_placeholder and self.manifest_checksum != expected:
            raise ValueError("manifest_checksum does not match canonical manifest content")
        return self

    def checksummed_payload(self) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude={"manifest_checksum"})

    @classmethod
    def create(cls, **values: Any) -> "BuildManifest":
        provisional = cls.model_validate(
            {**values, "manifest_checksum": "0" * 64},
            context={"allow_checksum_placeholder": True},
        )
        return cls.model_validate(
            {
                **provisional.checksummed_payload(),
                "manifest_checksum": canonical_sha256(provisional.checksummed_payload()),
            }
        )

    @property
    def input_fingerprint(self) -> str:
        behavior_inputs = {
            "project_id": self.project_id,
            "game_id": self.game_id,
            "profile": self.profile.value,
            "mode": self.mode.value,
            "target_id": self.target_id,
            "target_definition": self.target_definition.model_dump(mode="json"),
            "source_commit": self.source_commit.lower(),
            "source_identity": self.source_identity,
            "module_catalog": self.module_catalog,
            "project_bible_version": self.project_bible_version,
            "project_bible_checksum": self.project_bible_checksum,
            "asset_versions": {
                key: value.model_dump(mode="json")
                for key, value in self.asset_versions.items()
            },
            "scene_snapshots": {
                key: value.model_dump(mode="json")
                for key, value in self.scene_snapshots.items()
            },
            "unity_version": self.unity_version,
            "unity_packages": self.unity_packages,
            "build_recipe_version": self.build_recipe_version,
            "settings": self.settings,
            "test_evidence": [
                {
                    "artifact_type": item.artifact_type,
                    "category": item.category.value,
                    "version": item.version,
                    "checksum": item.checksum,
                    "size_bytes": item.size_bytes,
                    "mode": item.mode.value,
                    "origin_live_run_id": item.origin_live_run_id,
                    "origin_live_artifact_id": item.origin_live_artifact_id,
                    "result": item.result.value,
                }
                for item in sorted(
                    self.test_evidence,
                    key=lambda item: (
                        item.category.value,
                        item.artifact_type,
                        item.checksum,
                    ),
                )
            ],
        }
        return canonical_sha256(behavior_inputs)

    @property
    def output_fingerprint(self) -> str:
        outputs = [
            {
                "artifact_type": item.artifact_type,
                "version": item.version,
                "checksum": item.checksum,
                "size_bytes": item.size_bytes,
                "mode": item.mode.value,
                "origin_live_run_id": item.origin_live_run_id,
                "origin_live_artifact_id": item.origin_live_artifact_id,
            }
            for item in sorted(
                self.artifacts,
                key=lambda item: (item.artifact_type, item.checksum, item.size_bytes),
            )
        ]
        return canonical_sha256({"outputs": outputs})


class BuildRun(UtcModel):
    build_run_id: StableId
    matrix_id: StableId
    target_id: StableId
    project_id: StableId
    game_id: StableId
    profile: BuildProfile
    source_commit: GitCommit
    status: RunStatus
    mode: ExecutionMode
    attempt: int = Field(ge=1)
    started_at: datetime
    finished_at: Optional[datetime] = None
    manifest_id: Optional[StableId] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None

    @model_validator(mode="after")
    def outcome_fields_match_status(self) -> "BuildRun":
        terminal = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.BLOCKED}
        if self.status in terminal and self.finished_at is None:
            raise ValueError("terminal build runs require finished_at")
        if self.status == RunStatus.SUCCEEDED and self.manifest_id is None:
            raise ValueError("successful build runs require manifest_id")
        if self.status in {RunStatus.FAILED, RunStatus.BLOCKED}:
            if not self.failure_code or not self.failure_message:
                raise ValueError("failed or blocked build runs require structured failure")
        if self.status != RunStatus.SUCCEEDED and self.manifest_id is not None:
            raise ValueError("only successful build runs may reference a manifest")
        if self.status == RunStatus.SUCCEEDED and self.mode in {
            ExecutionMode.PLANNED,
            ExecutionMode.BLOCKED,
        }:
            raise ValueError("successful build runs require an executed mode")
        if self.status == RunStatus.BLOCKED and self.mode != ExecutionMode.BLOCKED:
            raise ValueError("blocked build runs must use blocked mode")
        return self
