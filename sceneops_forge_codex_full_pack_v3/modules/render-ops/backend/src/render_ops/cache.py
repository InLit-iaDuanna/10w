"""Dependency-aware AOV cache planning."""

from typing import Dict, Iterable, List, Mapping, Optional, Set

from .schemas import (
    AovArtifact,
    AovDependencySnapshot,
    AovPass,
    CachePlan,
    ExecutionMode,
    RenderRecipe,
    SceneCameraRef,
)


MATERIAL_DEPENDENT = frozenset(
    {AovPass.BEAUTY, AovPass.ALBEDO, AovPass.MATERIAL_ID}
)
LIGHTING_DEPENDENT = frozenset({AovPass.BEAUTY})


def _global_invalidation_reason(
    previous: AovDependencySnapshot, current: AovDependencySnapshot
) -> Optional[str]:
    comparisons = (
        ("recipe_id", "recipe changed"),
        ("recipe_version", "recipe version changed"),
        ("geometry_version", "geometry changed"),
        ("camera_version", "camera changed"),
        ("visibility_version", "visibility changed"),
        ("renderer_version", "renderer version changed"),
        ("samples", "sample count changed"),
        ("width", "resolution changed"),
        ("height", "resolution changed"),
    )
    for field, reason in comparisons:
        if getattr(previous, field) != getattr(current, field):
            return reason
    return None


def plan_aov_cache(
    recipe: RenderRecipe,
    scene: SceneCameraRef,
    current: AovDependencySnapshot,
    existing_aovs: Mapping[AovPass, AovArtifact],
    previous: Optional[AovDependencySnapshot],
    execution_mode: ExecutionMode,
) -> CachePlan:
    """Return exact passes to reuse/capture.

    Prompt, negative-prompt, seed, workflow, and model are intentionally absent
    from the AOV dependency snapshot, so prompt-only changes reuse compatible
    deterministic passes.
    """

    reused: List[AovPass] = []
    capture: List[AovPass] = []
    reasons: Dict[AovPass, str] = {}
    required = list(recipe.required_passes)

    if previous is None:
        return CachePlan(
            capture_passes=required,
            reasons={item: "no prior dependency snapshot" for item in required},
        )

    global_reason = _global_invalidation_reason(previous, current)
    for pass_type in required:
        if pass_type not in existing_aovs:
            capture.append(pass_type)
            reasons[pass_type] = "pass is missing from cache"
            continue
        candidate = AovArtifact.model_validate(
            existing_aovs[pass_type].model_dump(mode="python")
        )
        reusable_modes = (
            {ExecutionMode.MOCK}
            if execution_mode == ExecutionMode.MOCK
            else {ExecutionMode.LIVE, ExecutionMode.CACHED}
        )
        if candidate.artifact.execution_mode not in reusable_modes:
            capture.append(pass_type)
            reasons[pass_type] = "cached pass execution mode is incompatible"
            continue
        if candidate.scene != scene:
            capture.append(pass_type)
            reasons[pass_type] = "cached pass scene/camera identity differs"
            continue
        if (candidate.width, candidate.height) != (current.width, current.height):
            capture.append(pass_type)
            reasons[pass_type] = "cached pass resolution differs"
            continue
        if global_reason:
            capture.append(pass_type)
            reasons[pass_type] = global_reason
            continue
        if previous.material_version != current.material_version and pass_type in MATERIAL_DEPENDENT:
            capture.append(pass_type)
            reasons[pass_type] = "material changed"
            continue
        if previous.lighting_version != current.lighting_version and pass_type in LIGHTING_DEPENDENT:
            capture.append(pass_type)
            reasons[pass_type] = "lighting changed"
            continue
        reused.append(pass_type)
        reasons[pass_type] = "dependencies unchanged"

    return CachePlan(reused_passes=reused, capture_passes=capture, reasons=reasons)


def validate_aov_set(
    recipe: RenderRecipe,
    scene: SceneCameraRef,
    width: int,
    height: int,
    aovs: Iterable[AovArtifact],
    execution_mode: ExecutionMode,
) -> Dict[AovPass, AovArtifact]:
    """Validate identity, dimensions, uniqueness, and recipe completeness."""

    return validate_aov_artifacts(
        recipe.required_passes,
        scene,
        width,
        height,
        aovs,
        execution_mode=execution_mode,
    )


def validate_aov_artifacts(
    required_passes: Iterable[AovPass],
    scene: SceneCameraRef,
    width: int,
    height: int,
    aovs: Iterable[AovArtifact],
    *,
    execution_mode: Optional[ExecutionMode] = None,
) -> Dict[AovPass, AovArtifact]:
    """Validate one planned capture, including a cache-driven pass subset."""

    by_pass: Dict[AovPass, AovArtifact] = {}
    for candidate in aovs:
        aov = AovArtifact.model_validate(candidate.model_dump(mode="python"))
        if aov.pass_type in by_pass:
            raise ValueError("duplicate AOV pass: " + aov.pass_type.value)
        if aov.scene != scene:
            raise ValueError("AOV scene/camera version does not match render job")
        if (aov.width, aov.height) != (width, height):
            raise ValueError("AOV dimensions do not match render job")
        if execution_mode is not None:
            if execution_mode == ExecutionMode.MOCK:
                compatible_modes = {ExecutionMode.MOCK}
            elif execution_mode in {ExecutionMode.LIVE, ExecutionMode.CACHED}:
                compatible_modes = {ExecutionMode.LIVE, ExecutionMode.CACHED}
            else:
                raise ValueError("planned or blocked jobs cannot claim captured AOVs")
            if aov.artifact.execution_mode not in compatible_modes:
                raise ValueError("AOV artifact mode does not match render job")
        if (
            aov.artifact.source_project_id != scene.project_id
            or aov.artifact.source_version != scene.scene_version
        ):
            raise ValueError("AOV artifact provenance does not match render job")
        by_pass[aov.pass_type] = aov

    missing: Set[AovPass] = set(required_passes) - set(by_pass)
    if missing:
        labels = ", ".join(sorted(item.value for item in missing))
        raise ValueError("missing required AOV passes: " + labels)
    return by_pass
