"""Approval and adapter allowlists for editable scene writeback."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Protocol, Set

from pydantic import Field

from .schemas import (
    ApprovalState,
    ExecutionMode,
    RenderComparison,
    StrictModel,
    WritebackOperation,
    WritebackProperty,
    WritebackProposal,
    WritebackTarget,
)


class WritebackCapabilities(StrictModel):
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    target: WritebackTarget
    supported_properties: List[WritebackProperty] = Field(min_length=1)
    named_parameters: Dict[WritebackProperty, List[str]] = Field(default_factory=dict)
    supports_dry_run: bool
    supports_validation_capture: bool
    supports_idempotent_changesets: bool


class ChangePreview(StrictModel):
    proposal_id: str
    accepted: bool
    summaries: List[str]
    target_object_ids: List[str]
    base_scene_version: str = Field(min_length=1)
    execution_mode: ExecutionMode
    rejection_code: Optional[str] = None


class WritebackResult(StrictModel):
    proposal_id: str
    changeset_id: str
    target: WritebackTarget
    resulting_scene_version: str
    changed_object_ids: List[str]
    execution_mode: ExecutionMode
    adapter_id: str
    adapter_version: str
    rollback_reference: Optional[str] = None


class WritebackExecution(StrictModel):
    result: WritebackResult
    validation_capture: RenderComparison
    reused_changeset: bool = False


class SceneWritebackAdapter(Protocol):
    def capabilities(self) -> WritebackCapabilities:
        ...

    def dry_run(self, proposal: WritebackProposal) -> ChangePreview:
        ...

    def apply(self, proposal: WritebackProposal) -> WritebackResult:
        ...

    def capture_validation(
        self, proposal: WritebackProposal, result: WritebackResult
    ) -> RenderComparison:
        ...

    def find_execution(self, changeset_id: str) -> Optional[WritebackExecution]:
        """Return the durable prior outcome for an already applied ChangeSet."""
        ...


class ChangeSetApprovalVerifier(Protocol):
    def verify(self, proposal: WritebackProposal) -> None:
        """Verify ChangeSet identity and approver permissions with core auth state."""
        ...


DEFAULT_NAMED_PARAMETER_ALLOWLIST: Mapping[
    WritebackTarget, Mapping[WritebackProperty, Set[str]]
] = {
    WritebackTarget.BLENDER: {
        WritebackProperty.MATERIAL_SCALAR: {"roughness", "metallic", "specular_ior_level"},
        WritebackProperty.MATERIAL_COLOR: {"base_color"},
        WritebackProperty.POST_PARAMETER: {"look", "view_transform"},
        WritebackProperty.CAMERA_SETTING: {"lens_mm", "f_stop", "focus_distance_m"},
    },
    WritebackTarget.UNITY: {
        WritebackProperty.MATERIAL_SCALAR: {"_Metallic", "_Smoothness"},
        WritebackProperty.MATERIAL_COLOR: {"_BaseColor"},
        WritebackProperty.POST_PARAMETER: {"post_exposure", "contrast", "saturation"},
        WritebackProperty.CAMERA_SETTING: {"field_of_view", "aperture", "focus_distance_m"},
    },
}


def approve_writeback(
    proposal: WritebackProposal,
    *,
    changeset_id: str,
    approved_by: str,
    approved_at: Optional[datetime] = None,
) -> WritebackProposal:
    proposal = WritebackProposal.model_validate(proposal.model_dump(mode="python"))
    if proposal.approval_state != ApprovalState.PENDING:
        raise ValueError("only pending writeback proposals can be approved")
    timestamp = approved_at or datetime.now(timezone.utc)
    payload = proposal.model_dump(mode="python")
    payload["approval_snapshot"] = proposal.snapshot_payload(
        changeset_id=changeset_id,
        approved_by=approved_by,
        approved_at=timestamp,
    ).model_dump(mode="python")
    payload.update(
        changeset_id=changeset_id,
        approval_state=ApprovalState.APPROVED,
        approved_by=approved_by,
        approved_at=timestamp,
    )
    return WritebackProposal.model_validate(payload)


class WritebackPolicy:
    def __init__(
        self,
        named_parameter_allowlist: Mapping[
            WritebackTarget, Mapping[WritebackProperty, Set[str]]
        ] = DEFAULT_NAMED_PARAMETER_ALLOWLIST,
    ) -> None:
        self._named_parameter_allowlist = named_parameter_allowlist

    def validate(
        self,
        proposal: WritebackProposal,
        capabilities: WritebackCapabilities,
    ) -> None:
        if proposal.approval_state != ApprovalState.APPROVED or not proposal.changeset_id:
            raise PermissionError("writeback requires an approved ChangeSet")
        if not capabilities.supports_dry_run:
            raise PermissionError("writeback adapter must support dry-run")
        if not capabilities.supports_validation_capture:
            raise PermissionError("writeback adapter must support validation capture")
        if not capabilities.supports_idempotent_changesets:
            raise PermissionError("writeback adapter must durably deduplicate ChangeSet IDs")

        target = proposal.operations[0].target
        if capabilities.target != target:
            raise ValueError("writeback adapter target does not match proposal")
        supported = set(capabilities.supported_properties)
        allowed_names = self._named_parameter_allowlist.get(target, {})
        allowed_scope = set(proposal.allowed_object_ids)
        for operation in proposal.operations:
            if operation.property not in supported:
                raise PermissionError(
                    "adapter does not allow property: " + operation.property.value
                )
            if operation.target_object_id not in allowed_scope:
                raise PermissionError("operation target is outside the brief-owned allowlist")
            if operation.parameter_name is not None:
                policy_names = allowed_names.get(operation.property, set())
                adapter_names = set(capabilities.named_parameters.get(operation.property, []))
                if operation.parameter_name not in policy_names.intersection(adapter_names):
                    raise PermissionError(
                        "parameter is not allowlisted: " + operation.parameter_name
                    )


class WritebackExecutor:
    def __init__(
        self,
        policy: Optional[WritebackPolicy] = None,
        approval_verifier: Optional[ChangeSetApprovalVerifier] = None,
    ) -> None:
        self._policy = policy or WritebackPolicy()
        self._approval_verifier = approval_verifier

    def apply(
        self, proposal: WritebackProposal, adapter: SceneWritebackAdapter
    ) -> WritebackExecution:
        # Re-parse at the trust boundary: model_copy and nested collection mutation
        # must not bypass validation of the approved snapshot.
        proposal = WritebackProposal.model_validate(proposal.model_dump(mode="python"))
        capabilities = WritebackCapabilities.model_validate(
            adapter.capabilities().model_dump(mode="python")
        )
        self._policy.validate(proposal, capabilities)
        if self._approval_verifier is None:
            raise PermissionError("trusted ChangeSet approval verifier is required")
        self._approval_verifier.verify(proposal)
        assert proposal.changeset_id is not None
        prior = adapter.find_execution(proposal.changeset_id)
        if prior is not None:
            prior = WritebackExecution.model_validate(prior.model_dump(mode="python"))
            self._validate_execution(proposal, capabilities, prior)
            payload = prior.model_dump(mode="python")
            payload["reused_changeset"] = True
            return WritebackExecution.model_validate(payload)

        preview = ChangePreview.model_validate(
            adapter.dry_run(proposal).model_dump(mode="python")
        )
        if preview.proposal_id != proposal.proposal_id:
            raise ValueError("adapter dry-run returned the wrong proposal ID")
        if not preview.accepted:
            raise PermissionError(preview.rejection_code or "adapter rejected dry-run")
        if preview.execution_mode not in {ExecutionMode.LIVE, ExecutionMode.MOCK}:
            raise ValueError("writeback dry-run mode must be live or mock")
        if preview.base_scene_version != proposal.base_scene_version:
            raise ValueError("adapter dry-run used the wrong base scene version")
        approved_objects = {item.target_object_id for item in proposal.operations}
        if set(preview.target_object_ids) != approved_objects:
            raise PermissionError("adapter dry-run must cover the exact approved object scope")

        result = WritebackResult.model_validate(
            adapter.apply(proposal).model_dump(mode="python")
        )
        comparison = RenderComparison.model_validate(
            adapter.capture_validation(proposal, result).model_dump(mode="python")
        )
        execution = WritebackExecution(result=result, validation_capture=comparison)
        self._validate_execution(proposal, capabilities, execution)
        if result.execution_mode != preview.execution_mode:
            raise ValueError("writeback dry-run and apply modes differ")
        return execution

    @staticmethod
    def _validate_execution(
        proposal: WritebackProposal,
        capabilities: WritebackCapabilities,
        execution: WritebackExecution,
    ) -> None:
        result = execution.result
        if result.proposal_id != proposal.proposal_id:
            raise ValueError("adapter returned the wrong proposal ID")
        if result.changeset_id != proposal.changeset_id:
            raise ValueError("adapter returned the wrong ChangeSet ID")
        if result.target != capabilities.target:
            raise ValueError("adapter returned the wrong writeback target")
        if (result.adapter_id, result.adapter_version) != (
            capabilities.adapter_id,
            capabilities.adapter_version,
        ):
            raise ValueError("writeback result adapter identity is inconsistent")
        if result.execution_mode not in {ExecutionMode.LIVE, ExecutionMode.MOCK}:
            raise ValueError("writeback result cannot be cached, planned, or blocked")
        allowed_objects = {item.target_object_id for item in proposal.operations}
        if not set(result.changed_object_ids).issubset(allowed_objects):
            raise PermissionError("adapter changed an object outside the approved scope")
        comparison = execution.validation_capture
        if comparison.scene != proposal.scene:
            raise ValueError("validation capture used the wrong fixed camera or scene")
        if comparison.execution_mode != result.execution_mode:
            raise ValueError("validation capture and writeback modes differ")
        if set(comparison.changed_object_ids) != set(result.changed_object_ids):
            raise ValueError("validation capture changed-object evidence is inconsistent")
