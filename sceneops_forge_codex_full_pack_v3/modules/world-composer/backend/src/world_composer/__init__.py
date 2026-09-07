"""Public local proposal API for World Composer."""
from .workbench import workbench_router
from .environment_scene import (
    AiBuildRequest,
    AiBuildResult,
    AiEnvironmentPlan,
    AiPlacement,
    AssetVersionRebindResult,
    BehaviorParameterDescriptor,
    SharedProjectMemory,
    EnvironmentMessage,
    EnvironmentObject,
    EnvironmentScene,
    EnvironmentSceneError,
    EnvironmentSceneService,
    EnvironmentTransform,
    KeyDoorBehavior,
    KeyDoorBehaviorDefinition,
    WorldScaleProfile,
    ManualPlacementRequest,
    RebindAssetVersionRequest,
    RemoveObjectRequest,
    TransformObjectRequest,
    UpdateKeyDoorBehaviorRequest,
    create_environment_scene_router,
    key_door_behavior_definition,
)

__all__ = [
    "AiBuildRequest", "AiBuildResult", "AiEnvironmentPlan", "AiPlacement",
    "AssetVersionRebindResult", "BehaviorParameterDescriptor", "SharedProjectMemory",
    "EnvironmentMessage", "EnvironmentObject", "EnvironmentScene", "EnvironmentSceneError",
    "EnvironmentSceneService", "EnvironmentTransform", "KeyDoorBehavior", "KeyDoorBehaviorDefinition",
    "WorldScaleProfile", "ManualPlacementRequest", "RebindAssetVersionRequest",
    "RemoveObjectRequest", "TransformObjectRequest", "UpdateKeyDoorBehaviorRequest",
    "create_environment_scene_router", "key_door_behavior_definition",
    "workbench_router",
]
