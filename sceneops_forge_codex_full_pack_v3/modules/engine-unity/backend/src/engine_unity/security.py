"""Project-root and typed-command security checks."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Union

from .contracts import (
    BuildPayload,
    CapturePayload,
    CommandName,
    CommandRequest,
    ExecutionContext,
    ImportAssetPayload,
    MapIdentityPayload,
    NavMeshPayload,
    ProfilerPayload,
    RunTestsPayload,
    SetComponentPropertyPayload,
    StrictModel,
    UpsertColliderPayload,
    UpsertPrefabPayload,
)
from .errors import ErrorCode, UnityIntegrationError
from .prototype_contracts import PrototypeSpec
from .policy import (
    ALLOWLISTED_COMPONENT_PROPERTIES,
    ALLOWLISTED_PREFAB_COMPONENTS,
    command_policy,
)


def canonical_path(path: Union[str, Path]) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def is_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path), str(root)]) == str(root)
    except ValueError:
        return False


def resolve_project_root(requested: str, configured_roots: Iterable[str]) -> Path:
    root = canonical_path(requested)
    allowed = [canonical_path(item) for item in configured_roots]
    if root not in allowed:
        raise UnityIntegrationError(
            ErrorCode.PATH_OUTSIDE_PROJECT,
            "Unity project root is not configured for this execution context.",
            details={"requested_root": str(root)},
        )
    return root


def resolve_inside_project(root: Path, value: str) -> Path:
    candidate = canonical_path(value if Path(value).is_absolute() else root / value)
    if not is_within(candidate, root):
        raise UnityIntegrationError(
            ErrorCode.PATH_OUTSIDE_PROJECT,
            "Path resolves outside the configured Unity project root.",
            details={"path": value, "project_root": str(root)},
        )
    return candidate


def validate_project_shape(root: Path) -> None:
    if not (root / "Assets").is_dir() or not (root / "ProjectSettings").is_dir():
        raise UnityIntegrationError(
            ErrorCode.PROJECT_INVALID,
            "Unity project must contain Assets and ProjectSettings directories.",
            details={"project_root": str(root)},
        )


def validate_command_request(
    request: CommandRequest,
    context: ExecutionContext,
    *,
    require_project_shape: bool = True,
    enforce_approval: bool = True,
) -> tuple[Path, StrictModel, List[str]]:
    root = resolve_project_root(request.project_root, context.configured_project_roots)
    if require_project_shape:
        validate_project_shape(root)

    policy = command_policy(request.command)
    if policy.permission not in context.permissions:
        raise UnityIntegrationError(
            ErrorCode.PERMISSION_DENIED,
            f"Permission {policy.permission} is required for {request.command.value}.",
            details={"required_permission": policy.permission},
        )

    try:
        payload = request.typed_payload()
    except Exception as exc:
        raise UnityIntegrationError(
            ErrorCode.INVALID_PAYLOAD,
            f"Invalid payload for {request.command.value}.",
            details={"validation_error": str(exc)},
        ) from exc

    if request.base_version != context.current_base_version:
        raise UnityIntegrationError(
            ErrorCode.BASE_VERSION_MISMATCH,
            "Command base version does not match the current Unity project version.",
            details={
                "provided": request.base_version,
                "current": context.current_base_version,
            },
        )

    if policy.mutating:
        _validate_change_set(
            request,
            context,
            policy.approval_required and enforce_approval,
            payload,
        )

    target_paths = _validate_payload_paths(root, request.command, payload)
    _validate_payload_allowlists(payload)
    return root, payload, target_paths


def _validate_change_set(
    request: CommandRequest,
    context: ExecutionContext,
    approval_required: bool,
    payload: StrictModel,
) -> None:
    change_set = request.change_set
    if change_set is None:
        raise UnityIntegrationError(
            ErrorCode.CHANGESET_REQUIRED,
            f"{request.command.value} requires a typed ChangeSet.",
        )
    if change_set.base_version != context.current_base_version:
        raise UnityIntegrationError(
            ErrorCode.BASE_VERSION_MISMATCH,
            "ChangeSet base version does not match the current Unity project version.",
            details={
                "provided": change_set.base_version,
                "current": context.current_base_version,
            },
        )
    if change_set.command is not request.command:
        raise UnityIntegrationError(
            ErrorCode.CHANGESET_MISMATCH,
            "ChangeSet command does not match the requested Unity command.",
            details={
                "change_set_command": change_set.command.value,
                "request_command": request.command.value,
            },
        )
    proposed_values = payload.model_dump(mode="json")
    if change_set.proposed_values != proposed_values:
        raise UnityIntegrationError(
            ErrorCode.CHANGESET_MISMATCH,
            "ChangeSet proposed values do not match the normalized command payload.",
        )
    expected_targets = set(expected_change_targets(request, payload))
    provided_targets = set(change_set.target_object_ids)
    if provided_targets != expected_targets:
        raise UnityIntegrationError(
            ErrorCode.CHANGESET_MISMATCH,
            "ChangeSet targets do not match the command's stable target identities.",
            details={
                "expected_targets": sorted(expected_targets),
                "provided_targets": sorted(provided_targets),
            },
        )
    if approval_required and change_set.approval_state.value != "approved":
        raise UnityIntegrationError(
            ErrorCode.APPROVAL_REQUIRED,
            f"{request.command.value} requires explicit ChangeSet approval.",
            details={"approval_state": change_set.approval_state.value},
        )
    if approval_required:
        trusted = context.approved_change_sets.get(change_set.change_set_id)
        if trusted is None or trusted.model_dump(mode="json") != change_set.model_dump(
            mode="json"
        ):
            raise UnityIntegrationError(
                ErrorCode.APPROVAL_REQUIRED,
                "ChangeSet approval is absent or does not match the trusted approval record.",
                details={"change_set_id": change_set.change_set_id},
            )


def expected_change_targets(
    request: CommandRequest,
    payload: StrictModel,
) -> List[str]:
    """Return the complete stable-ID target set bound to a mutating command."""

    targets: List[str]
    if isinstance(payload, PrototypeSpec):
        targets = [payload.prototype_id]
    elif isinstance(payload, ImportAssetPayload):
        targets = [payload.source_asset_id, payload.source_asset_version_id]
        targets.extend(value for value in (payload.sceneops_id, payload.scene_instance_id) if value)
    elif isinstance(payload, MapIdentityPayload):
        targets = [
            payload.source_asset_id,
            payload.source_asset_version_id,
            payload.source_object_id,
            payload.sceneops_id,
            payload.unity_asset_guid,
        ]
        targets.extend(
            value
            for value in (
                payload.prefab_id,
                payload.scene_instance_id,
                payload.copied_from_scene_instance_id,
            )
            if value
        )
    elif isinstance(payload, UpsertPrefabPayload):
        targets = [
            payload.source_asset_id,
            payload.source_asset_version_id,
            payload.source_asset_guid,
            payload.sceneops_id,
            payload.prefab_id,
        ]
    elif isinstance(payload, (SetComponentPropertyPayload, UpsertColliderPayload)):
        targets = [payload.sceneops_id]
        if payload.scene_instance_id:
            targets.append(payload.scene_instance_id)
    elif isinstance(payload, NavMeshPayload):
        targets = [payload.scene_id]
    elif isinstance(payload, BuildPayload):
        targets = [request.project_id, payload.build_id]
        for source in payload.source_assets:
            targets.extend([source.source_asset_id, source.source_asset_version_id])
    else:
        targets = [request.project_id]
    return list(dict.fromkeys(targets))


def _validate_payload_paths(
    root: Path,
    command: CommandName,
    payload: StrictModel,
) -> List[str]:
    values: List[str] = []
    if isinstance(payload, ImportAssetPayload):
        values.extend(
            [payload.source_path, payload.destination_asset_path, payload.manifest_path]
        )
        if payload.destination_scene_path:
            values.append(payload.destination_scene_path)
    elif isinstance(payload, UpsertPrefabPayload):
        values.append(payload.prefab_asset_path)
    elif isinstance(payload, NavMeshPayload):
        values.append(payload.scene_asset_path)
    elif isinstance(payload, CapturePayload):
        values.append(payload.output_path)
    elif isinstance(payload, RunTestsPayload):
        values.append(payload.results_path)
    elif isinstance(payload, ProfilerPayload):
        values.append(payload.output_path)
    elif isinstance(payload, BuildPayload):
        values.append(payload.output_path)
        values.extend(payload.scenes)
    return [str(resolve_inside_project(root, value)) for value in values]


def _validate_payload_allowlists(payload: StrictModel) -> None:
    if isinstance(payload, SetComponentPropertyPayload):
        properties = ALLOWLISTED_COMPONENT_PROPERTIES.get(payload.component_type)
        if properties is None or payload.property_path not in properties:
            raise UnityIntegrationError(
                ErrorCode.COMMAND_NOT_ALLOWED,
                "Component property is not on the Unity mutation allowlist.",
                details={
                    "component_type": payload.component_type,
                    "property_path": payload.property_path,
                },
            )
    if isinstance(payload, UpsertPrefabPayload):
        denied = sorted(set(payload.component_types) - ALLOWLISTED_PREFAB_COMPONENTS)
        if denied:
            raise UnityIntegrationError(
                ErrorCode.COMMAND_NOT_ALLOWED,
                "Prefab contains component types outside the allowlist.",
                details={"denied_component_types": denied},
            )
