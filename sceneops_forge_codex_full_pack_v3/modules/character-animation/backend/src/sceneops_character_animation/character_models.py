"""Character, rig, and skin contracts."""

from typing import List, Literal, Optional

from pydantic import Field, model_validator

from .common import ApprovalRecord, CoordinateSystem, FeatureLink, Provenance, StrictModel, Vector3


class CharacterSpec(StrictModel):
    character_id: str = Field(min_length=3)
    display_name: str = Field(min_length=1)
    source_asset_id: str = Field(min_length=3)
    source_kind: Literal["imported", "generated"]
    feature_links: List[FeatureLink] = Field(min_length=1)
    expected_bone_names: List[str] = Field(min_length=1)
    coordinate_system: CoordinateSystem
    provenance: Provenance

    @model_validator(mode="after")
    def source_and_character_are_distinct(self) -> "CharacterSpec":
        if self.source_asset_id == self.character_id:
            raise ValueError("source asset and character identities must be distinct")
        if self.provenance.artifact_id != self.character_id:
            raise ValueError("character provenance must identify the character")
        return self


class BoneSpec(StrictModel):
    bone_id: str = Field(min_length=3)
    name: str = Field(min_length=1)
    parent_bone_id: Optional[str] = None
    rest_translation_meters: Vector3 = (0.0, 0.0, 0.0)


class RigVersion(StrictModel):
    rig_version_id: str = Field(min_length=3)
    character_id: str = Field(min_length=3)
    version_number: int = Field(ge=1)
    previous_version_id: Optional[str] = None
    source_rig_id: str = Field(min_length=3)
    bones: List[BoneSpec] = Field(min_length=1)
    coordinate_system: CoordinateSystem
    approval: ApprovalRecord = ApprovalRecord()
    provenance: Provenance

    @model_validator(mode="after")
    def rig_identity_kinds_are_distinct(self) -> "RigVersion":
        if len({self.rig_version_id, self.character_id, self.source_rig_id}) != 3:
            raise ValueError("rig version, character, and source rig identities must be distinct")
        if self.provenance.artifact_id != self.rig_version_id:
            raise ValueError("rig provenance must identify the rig version")
        if self.approval.state != self.provenance.approval_state:
            raise ValueError("rig approval and provenance approval state must match")
        return self


class SkinInfluence(StrictModel):
    bone_id: str = Field(min_length=3)
    weight: float


class VertexWeights(StrictModel):
    vertex_index: int = Field(ge=0)
    influences: List[SkinInfluence]


class SkinVersion(StrictModel):
    skin_version_id: str = Field(min_length=3)
    character_id: str = Field(min_length=3)
    rig_version_id: str = Field(min_length=3)
    version_number: int = Field(ge=1)
    previous_version_id: Optional[str] = None
    max_supported_influences: int = Field(default=4, ge=1)
    vertices: List[VertexWeights] = Field(min_length=1)
    approval: ApprovalRecord = ApprovalRecord()
    provenance: Provenance

    @model_validator(mode="after")
    def identities_are_distinct(self) -> "SkinVersion":
        ids = {self.skin_version_id, self.character_id, self.rig_version_id}
        if len(ids) != 3:
            raise ValueError("skin, character, and rig identities must be distinct")
        if self.provenance.artifact_id != self.skin_version_id:
            raise ValueError("skin provenance must identify the skin version")
        if self.approval.state != self.provenance.approval_state:
            raise ValueError("skin approval and provenance approval state must match")
        return self
