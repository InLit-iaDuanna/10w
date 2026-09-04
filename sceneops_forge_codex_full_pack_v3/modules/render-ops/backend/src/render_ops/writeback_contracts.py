"""Typed editable writeback and ChangeSet-like approval contracts."""

from datetime import datetime
import math
from typing import Any, Literal, Optional, Tuple

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base_contracts import (
    ApprovalState,
    SceneCameraRef,
    StrictModel,
    WritebackProperty,
    WritebackTarget,
    require_utc,
)


class WritebackOperation(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target: WritebackTarget
    target_object_id: str = Field(min_length=1)
    property: WritebackProperty
    parameter_name: Optional[str] = None
    previous_value: Any
    proposed_value: Any

    @model_validator(mode="before")
    @classmethod
    def normalize_bounded_values(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        property_name = normalized.get("property")
        if property_name in {
            WritebackProperty.LIGHT_COLOR,
            WritebackProperty.LIGHT_COLOR.value,
            WritebackProperty.MATERIAL_COLOR,
            WritebackProperty.MATERIAL_COLOR.value,
        }:
            for field_name in ("previous_value", "proposed_value"):
                field_value = normalized.get(field_name)
                if isinstance(field_value, list):
                    normalized[field_name] = tuple(field_value)
        return normalized

    @model_validator(mode="after")
    def named_parameter_contract(self) -> "WritebackOperation":
        named = {
            WritebackProperty.MATERIAL_SCALAR,
            WritebackProperty.MATERIAL_COLOR,
            WritebackProperty.POST_PARAMETER,
            WritebackProperty.CAMERA_SETTING,
        }
        if self.property in named and not self.parameter_name:
            raise ValueError("this property requires an allowlisted parameter_name")
        if self.property not in named and self.parameter_name is not None:
            raise ValueError("parameter_name is not valid for this property")
        self._validate_value(self.proposed_value, allow_none=False)
        self._validate_value(self.previous_value, allow_none=True)
        return self

    def _validate_value(self, value: Any, *, allow_none: bool) -> None:
        if value is None and allow_none:
            return
        numeric = {
            WritebackProperty.LIGHT_INTENSITY,
            WritebackProperty.LIGHT_TEMPERATURE,
            WritebackProperty.MATERIAL_SCALAR,
            WritebackProperty.EXPOSURE,
            WritebackProperty.CAMERA_SETTING,
        }
        colors = {WritebackProperty.LIGHT_COLOR, WritebackProperty.MATERIAL_COLOR}
        if self.property in numeric:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("writeback property requires a numeric value")
            if not math.isfinite(float(value)):
                raise ValueError("writeback numeric value must be finite")
            if self.property == WritebackProperty.LIGHT_INTENSITY and value < 0:
                raise ValueError("light intensity cannot be negative")
            if (
                self.property == WritebackProperty.LIGHT_TEMPERATURE
                and not 1000 <= value <= 40000
            ):
                raise ValueError("light temperature must be between 1000K and 40000K")
            return
        if self.property in colors:
            if not isinstance(value, (list, tuple)) or len(value) not in {3, 4}:
                raise ValueError("color writeback requires three or four channels")
            if any(
                isinstance(channel, bool)
                or not isinstance(channel, (int, float))
                or not math.isfinite(float(channel))
                or not 0 <= channel <= 1
                for channel in value
            ):
                raise ValueError("color channels must be finite values between zero and one")
            return
        if self.property == WritebackProperty.OBJECT_VISIBILITY:
            if not isinstance(value, bool):
                raise ValueError("object visibility requires a boolean")
            return
        if self.property == WritebackProperty.PBR_TEXTURE:
            if not isinstance(value, str) or not value or "/" in value or "\\" in value:
                raise ValueError(
                    "PBR texture writeback requires a stable artifact ID, not a path"
                )
            return
        if self.property == WritebackProperty.POST_PARAMETER:
            if isinstance(value, (dict, list, tuple)) or value is None:
                raise ValueError("post parameter value must be a bounded scalar")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("post parameter numeric value must be finite")
            if isinstance(value, str) and (not value or len(value) > 256):
                raise ValueError("post parameter string is empty or too long")


class WritebackApprovalSnapshot(StrictModel):
    """Immutable payload that the ChangeSet approval covered."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1)
    changeset_id: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_at: datetime
    variant_id: str = Field(min_length=1)
    brief_id: str = Field(min_length=1)
    scene: SceneCameraRef
    base_scene_version: str = Field(min_length=1)
    operations: Tuple[WritebackOperation, ...] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: Tuple[str, ...] = Field(min_length=1)
    allowed_object_ids: Tuple[str, ...] = Field(min_length=1)
    risk: Literal["low", "medium", "high"]
    validation_plan: str = Field(min_length=1)
    rollback_plan: str = Field(min_length=1)
    approval_requirements: Tuple[str, ...] = Field(min_length=1)

    _approved_at_utc = field_validator("approved_at")(require_utc)


class WritebackProposal(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1)
    changeset_id: Optional[str] = Field(default=None, min_length=1)
    variant_id: str = Field(min_length=1)
    brief_id: str = Field(min_length=1)
    scene: SceneCameraRef
    base_scene_version: str = Field(min_length=1)
    operations: Tuple[WritebackOperation, ...] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    impact_scope: Tuple[str, ...] = Field(min_length=1)
    allowed_object_ids: Tuple[str, ...] = Field(min_length=1)
    risk: Literal["low", "medium", "high"]
    validation_plan: str = Field(min_length=1)
    rollback_plan: str = Field(min_length=1)
    approval_requirements: Tuple[str, ...] = Field(min_length=1)
    approval_state: ApprovalState = ApprovalState.PENDING
    approved_by: Optional[str] = Field(default=None, min_length=1)
    approved_at: Optional[datetime] = None
    approval_snapshot: Optional[WritebackApprovalSnapshot] = None

    _approved_at_utc = field_validator("approved_at")(
        lambda value: require_utc(value) if value is not None else value
    )

    @model_validator(mode="after")
    def approved_changeset_contract(self) -> "WritebackProposal":
        if len({operation.target for operation in self.operations}) != 1:
            raise ValueError("one proposal may target only one integration")
        operation_scope = tuple(sorted({item.target_object_id for item in self.operations}))
        if tuple(self.impact_scope) != operation_scope:
            raise ValueError("impact_scope must exactly match operation target IDs")
        if len(self.allowed_object_ids) != len(set(self.allowed_object_ids)):
            raise ValueError("allowed_object_ids must be unique")
        if not set(operation_scope).issubset(set(self.allowed_object_ids)):
            raise ValueError("writeback operations exceed the brief-owned object allowlist")
        if not set(self.allowed_object_ids).issubset(set(self.scene.scene_object_ids)):
            raise ValueError("writeback object allowlist must belong to the exact scene")
        if len(self.approval_requirements) != len(set(self.approval_requirements)):
            raise ValueError("approval_requirements must be unique")
        if not {"render:approve", "render:writeback"}.issubset(
            set(self.approval_requirements)
        ):
            raise ValueError("writeback requires approve and writeback permissions")
        if self.base_scene_version != self.scene.scene_version:
            raise ValueError("writeback base version must match its exact scene reference")
        approved = self.approval_state == ApprovalState.APPROVED
        if approved and not (
            self.changeset_id
            and self.approved_by
            and self.approved_at
            and self.approval_snapshot
        ):
            raise ValueError("approved writeback requires ChangeSet ID and approver")
        if not approved and (self.approved_by or self.approved_at or self.approval_snapshot):
            raise ValueError("unapproved writeback cannot include approval identity")
        if approved and self.approval_snapshot != self.snapshot_payload():
            raise ValueError("approved writeback differs from its approval snapshot")
        return self

    def snapshot_payload(
        self,
        *,
        changeset_id: Optional[str] = None,
        approved_by: Optional[str] = None,
        approved_at: Optional[datetime] = None,
    ) -> WritebackApprovalSnapshot:
        resolved_changeset_id = changeset_id or self.changeset_id
        resolved_approved_by = approved_by or self.approved_by
        resolved_approved_at = approved_at or self.approved_at
        if not (
            resolved_changeset_id and resolved_approved_by and resolved_approved_at
        ):
            raise ValueError("approval snapshot requires ChangeSet approval identity")
        return WritebackApprovalSnapshot(
            proposal_id=self.proposal_id,
            changeset_id=resolved_changeset_id,
            approved_by=resolved_approved_by,
            approved_at=resolved_approved_at,
            variant_id=self.variant_id,
            brief_id=self.brief_id,
            scene=SceneCameraRef.model_validate(self.scene.model_dump(mode="python")),
            base_scene_version=self.base_scene_version,
            operations=tuple(
                WritebackOperation.model_validate(item.model_dump(mode="python"))
                for item in self.operations
            ),
            rationale=self.rationale,
            expected_result=self.expected_result,
            impact_scope=self.impact_scope,
            allowed_object_ids=self.allowed_object_ids,
            risk=self.risk,
            validation_plan=self.validation_plan,
            rollback_plan=self.rollback_plan,
            approval_requirements=self.approval_requirements,
        )
