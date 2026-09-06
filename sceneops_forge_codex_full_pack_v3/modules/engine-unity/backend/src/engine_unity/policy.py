"""Command allowlist, permission, property, and approval policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Mapping

from .contracts import CommandName


@dataclass(frozen=True)
class CommandPolicy:
    permission: str
    mutating: bool
    approval_required: bool
    retryable: bool


COMMAND_POLICIES: Mapping[CommandName, CommandPolicy] = {
    CommandName.PROTOTYPE_COMPOSE: CommandPolicy("unity:write", True, True, False),
    CommandName.PROTOTYPE_INSPECT: CommandPolicy("unity:read", False, False, True),
    CommandName.PROTOTYPE_PLAY: CommandPolicy("unity:execute", True, True, False),
    CommandName.PROTOTYPE_CAPTURE: CommandPolicy("unity:execute", True, True, False),
    CommandName.HEALTH: CommandPolicy("unity:read", False, False, True),
    CommandName.SCAN_PROJECT: CommandPolicy("unity:read", False, False, True),
    CommandName.IMPORT_ASSET: CommandPolicy("unity:write", True, True, False),
    CommandName.MAP_IDENTITY: CommandPolicy("unity:write", True, True, False),
    CommandName.UPSERT_PREFAB: CommandPolicy("unity:write", True, True, False),
    CommandName.INSPECT_GAME_OBJECT: CommandPolicy("unity:read", False, False, True),
    CommandName.SET_COMPONENT_PROPERTY: CommandPolicy("unity:write", True, True, False),
    CommandName.UPSERT_COLLIDER: CommandPolicy("unity:write", True, True, False),
    CommandName.RUN_NAVMESH: CommandPolicy("unity:write", True, True, False),
    CommandName.ENTER_PLAY: CommandPolicy("unity:execute", True, False, False),
    CommandName.EXIT_PLAY: CommandPolicy("unity:execute", True, False, False),
    CommandName.CAPTURE: CommandPolicy("unity:execute", True, False, True),
    CommandName.READ_CONSOLE: CommandPolicy("unity:read", False, False, True),
    CommandName.RUN_TESTS: CommandPolicy("unity:execute", False, False, True),
    CommandName.SNAPSHOT_PROFILER: CommandPolicy("unity:execute", False, False, True),
    CommandName.RUN_BUILD: CommandPolicy("unity:build", True, True, False),
}


ALLOWLISTED_COMPONENT_PROPERTIES: Mapping[str, FrozenSet[str]] = {
    "Transform": frozenset(
        {
            "m_LocalPosition",
            "m_LocalRotation",
            "m_LocalScale",
        }
    ),
    "BoxCollider": frozenset({"m_IsTrigger", "m_Center", "m_Size"}),
    "SphereCollider": frozenset({"m_IsTrigger", "m_Center", "m_Radius"}),
    "CapsuleCollider": frozenset(
        {"m_IsTrigger", "m_Center", "m_Radius", "m_Height", "m_Direction"}
    ),
    "MeshCollider": frozenset({"m_IsTrigger", "m_Convex"}),
    "Rigidbody": frozenset(
        {
            "m_Mass",
            "m_Drag",
            "m_AngularDrag",
            "m_UseGravity",
            "m_IsKinematic",
        }
    ),
    "Light": frozenset({"m_Intensity", "m_Range", "m_Color"}),
    "SceneOpsIdentity": frozenset(),
}


ALLOWLISTED_PREFAB_COMPONENTS = frozenset(
    {
        "BoxCollider",
        "SphereCollider",
        "CapsuleCollider",
        "MeshCollider",
        "Rigidbody",
        "LODGroup",
        "SceneOpsIdentity",
    }
)


def command_policy(command: CommandName) -> CommandPolicy:
    return COMMAND_POLICIES[command]
