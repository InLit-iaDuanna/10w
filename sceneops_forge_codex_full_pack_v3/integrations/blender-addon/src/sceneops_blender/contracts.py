from __future__ import annotations

import json
import math
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionMode(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    MOCK = "mock"
    PLANNED = "planned"
    BLOCKED = "blocked"


class BlenderOperation(str, Enum):
    SCAN_SCENE = "scan_scene"
    ASSIGN_STABLE_IDS = "assign_stable_ids"
    INSPECT_OBJECT = "inspect_object"
    SET_TRANSFORM = "set_transform"
    SET_NORMALS = "set_normals"
    SET_MATERIAL_PARAMETER = "set_material_parameter"
    SET_LIGHT_PARAMETER = "set_light_parameter"
    CAPTURE_CONTEXT = "capture_context"
    RENDER_AOV = "render_aov"
    CHECK_GEOMETRY = "check_geometry"
    GENERATE_LOD = "generate_lod"
    GENERATE_COLLIDER = "generate_collider"
    SAVE_SNAPSHOT = "save_snapshot"
    ROLLBACK_SNAPSHOT = "rollback_snapshot"
    EXPORT_ASSET = "export_asset"


READ_ONLY_OPERATIONS = {
    BlenderOperation.SCAN_SCENE,
    BlenderOperation.INSPECT_OBJECT,
    BlenderOperation.CAPTURE_CONTEXT,
    BlenderOperation.CHECK_GEOMETRY,
}

PERSISTENT_SCENE_MUTATIONS = {
    BlenderOperation.ASSIGN_STABLE_IDS,
    BlenderOperation.SET_TRANSFORM,
    BlenderOperation.SET_NORMALS,
    BlenderOperation.SET_MATERIAL_PARAMETER,
    BlenderOperation.SET_LIGHT_PARAMETER,
    BlenderOperation.GENERATE_LOD,
    BlenderOperation.GENERATE_COLLIDER,
}


OPERATION_PARAMETERS = {
    BlenderOperation.SCAN_SCENE: {"include_hidden"},
    BlenderOperation.ASSIGN_STABLE_IDS: {"identity_assignments"},
    BlenderOperation.INSPECT_OBJECT: {"include_materials"},
    BlenderOperation.SET_TRANSFORM: {"location_m", "rotation_degrees", "scale"},
    BlenderOperation.SET_NORMALS: {"mode", "angle_degrees"},
    BlenderOperation.SET_MATERIAL_PARAMETER: {"material_name", "parameter", "value"},
    BlenderOperation.SET_LIGHT_PARAMETER: {"light_name", "parameter", "value"},
    BlenderOperation.CAPTURE_CONTEXT: {"camera_name"},
    BlenderOperation.RENDER_AOV: {"camera_name", "passes", "width", "height", "samples"},
    BlenderOperation.CHECK_GEOMETRY: {"triangle_budget", "require_uv", "allow_nonmanifold"},
    BlenderOperation.GENERATE_LOD: {"ratios"},
    BlenderOperation.GENERATE_COLLIDER: {"method"},
    BlenderOperation.SAVE_SNAPSHOT: set(),
    BlenderOperation.ROLLBACK_SNAPSHOT: {"snapshot_id"},
    BlenderOperation.EXPORT_ASSET: {"formats", "include_extras", "selection_only"},
}


class MutationAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_set_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)


class BlenderCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1, max_length=200, pattern="^[A-Za-z0-9_.:-]+$")
    project_id: str = Field(min_length=1)
    operation: BlenderOperation
    source_path: Optional[str] = None
    output_paths: List[str] = Field(default_factory=list, max_length=8)
    object_ids: List[str] = Field(default_factory=list, max_length=10_000)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    authorization: Optional[MutationAuthorization] = None
    dry_run: bool = False

    @model_validator(mode="after")
    def command_is_allowlisted_and_authorized(self) -> "BlenderCommand":
        operation = self.operation
        parameters = self.parameters
        if operation != BlenderOperation.SCAN_SCENE and not self.source_path:
            raise ValueError("Blender command requires a project source path")
        unknown = sorted(set(parameters) - OPERATION_PARAMETERS[operation])
        if unknown:
            raise ValueError("parameters are not allowlisted: " + ", ".join(unknown))
        if (
            operation not in READ_ONLY_OPERATIONS
            and self.authorization is None
            and not self.dry_run
        ):
            raise ValueError("mutating Blender operations require ChangeSet approval")
        required_output = {
            BlenderOperation.RENDER_AOV,
            BlenderOperation.SAVE_SNAPSHOT,
            BlenderOperation.ROLLBACK_SNAPSHOT,
            BlenderOperation.EXPORT_ASSET,
        }
        if operation in required_output and not self.output_paths:
            raise ValueError("operation requires an output path")
        if operation == BlenderOperation.SAVE_SNAPSHOT and len(self.output_paths) != 2:
            raise ValueError("snapshot operation requires rollback and working-copy paths")
        if operation == BlenderOperation.ROLLBACK_SNAPSHOT and len(self.output_paths) != 1:
            raise ValueError("rollback operation requires the working-copy output path")
        targeted_operations = {
            BlenderOperation.ASSIGN_STABLE_IDS,
            BlenderOperation.INSPECT_OBJECT,
            BlenderOperation.SET_TRANSFORM,
            BlenderOperation.SET_NORMALS,
            BlenderOperation.GENERATE_LOD,
            BlenderOperation.GENERATE_COLLIDER,
            BlenderOperation.EXPORT_ASSET,
        }
        if operation in targeted_operations and not self.object_ids:
            raise ValueError("operation requires explicit sceneops_id targets")
        if len(self.object_ids) != len(set(self.object_ids)):
            raise ValueError("object_ids must be unique")
        if any(not value or len(value) > 160 for value in self.object_ids):
            raise ValueError("object_ids must be non-empty and at most 160 characters")
        paths = [value for value in [self.source_path, *self.output_paths] if value]
        if any(len(value) > 1024 for value in paths):
            raise ValueError("Blender paths must be at most 1024 characters")
        try:
            encoded_parameters = json.dumps(
                parameters, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError) as error:
            raise ValueError("Blender parameters must be finite JSON values") from error
        if len(encoded_parameters) > 1_000_000:
            raise ValueError("Blender parameters exceed the one-megabyte limit")
        self._validate_parameter_values(operation, parameters)
        if operation == BlenderOperation.RENDER_AOV and (
            len(self.output_paths) != 1
            or not self.output_paths[0].casefold().endswith(".exr")
        ):
            raise ValueError("AOV render requires exactly one EXR output")
        if operation == BlenderOperation.EXPORT_ASSET:
            formats = {str(item).casefold() for item in parameters["formats"]}
            suffixes = {
                value.rsplit(".", 1)[-1].casefold()
                for value in self.output_paths
                if "." in value.rsplit("/", 1)[-1]
            }
            if len(self.output_paths) != len(formats) or suffixes != formats:
                raise ValueError("export outputs must match the requested formats")
        return self

    @staticmethod
    def _validate_parameter_values(operation: BlenderOperation, parameters: Dict[str, Any]) -> None:
        if operation == BlenderOperation.EXPORT_ASSET:
            raw_formats = parameters.get("formats", [])
            if (
                not isinstance(raw_formats, list)
                or not raw_formats
                or len(raw_formats) > 2
            ):
                raise ValueError("export formats must be a bounded list")
            formats = {str(item).lower() for item in raw_formats}
            if len(formats) != len(raw_formats) or not formats.issubset({"glb", "fbx"}):
                raise ValueError("export formats must be a non-empty subset of GLB/FBX")
            if parameters.get("include_extras") is not True:
                raise ValueError("export must include sceneops_id extras")
            if parameters.get("selection_only") is not True:
                raise ValueError("export must be limited to selected asset objects")
        if operation == BlenderOperation.RENDER_AOV:
            _optional_bounded_string(parameters, "camera_name")
            raw_passes = parameters.get("passes", [])
            if not isinstance(raw_passes, list) or len(raw_passes) > 5:
                raise ValueError("render passes must be a bounded list")
            passes = set(raw_passes)
            if len(passes) != len(raw_passes) or not passes or not passes.issubset(
                {"beauty", "depth", "normal", "object_id", "material_id"}
            ):
                raise ValueError("render pass is not allowlisted")
            _bounded_integer(parameters, "width", 1, 8192)
            _bounded_integer(parameters, "height", 1, 8192)
            _bounded_integer(parameters, "samples", 1, 4096)
        if operation == BlenderOperation.GENERATE_COLLIDER:
            if parameters.get("method") not in {"bounding_box", "convex_hull"}:
                raise ValueError("collider method is not allowlisted")
        if operation == BlenderOperation.SET_NORMALS:
            if parameters.get("mode") not in {"recalculate_outside", "auto_smooth"}:
                raise ValueError("normal operation is not allowlisted")
            if "angle_degrees" in parameters:
                _bounded_number(parameters["angle_degrees"], "angle_degrees", 0, 180)
        if operation == BlenderOperation.SET_MATERIAL_PARAMETER:
            _required_bounded_string(parameters, "material_name")
            parameter = parameters.get("parameter")
            if parameter not in {"base_color", "metallic", "roughness", "alpha"}:
                raise ValueError("material parameter is not allowlisted")
            value = parameters.get("value")
            if parameter == "base_color":
                _numeric_vector(value, "base_color", length=4, minimum=0, maximum=1)
            else:
                _bounded_number(value, "material value", 0, 1)
        if operation == BlenderOperation.SET_LIGHT_PARAMETER:
            _required_bounded_string(parameters, "light_name")
            parameter = parameters.get("parameter")
            if parameter not in {"energy", "color", "temperature"}:
                raise ValueError("light parameter is not allowlisted")
            value = parameters.get("value")
            if parameter == "color":
                _numeric_vector(value, "light color", minimum=0, maximum=1)
            elif parameter == "temperature":
                _bounded_number(value, "temperature", 800, 40_000)
            else:
                _bounded_number(value, "energy", 0, 1_000_000_000)
        if operation == BlenderOperation.GENERATE_LOD:
            ratios = parameters.get("ratios", [])
            if (
                not ratios
                or len(ratios) > 8
                or len(ratios) != len(set(ratios))
                or any(
                    not isinstance(item, (int, float))
                    or isinstance(item, bool)
                    or not math.isfinite(item)
                    or item <= 0
                    or item >= 1
                    for item in ratios
                )
            ):
                raise ValueError("LOD ratios must be between zero and one")
        if operation == BlenderOperation.CHECK_GEOMETRY:
            _bounded_integer(parameters, "triangle_budget", 1, 2_000_000_000)
            if not isinstance(parameters.get("require_uv"), bool):
                raise ValueError("require_uv must be boolean")
            if not isinstance(parameters.get("allow_nonmanifold"), bool):
                raise ValueError("allow_nonmanifold must be boolean")
        if operation == BlenderOperation.SET_TRANSFORM:
            if not parameters:
                raise ValueError("transform operation requires at least one value")
            for key in ("location_m", "rotation_degrees", "scale"):
                if key in parameters:
                    _numeric_vector(parameters[key], key)
        if operation == BlenderOperation.ASSIGN_STABLE_IDS:
            assignments = parameters.get("identity_assignments", {})
            if not isinstance(assignments, dict) or len(assignments) > 10_000:
                raise ValueError("identity assignments must be a bounded object")
            if any(
                not isinstance(key, str)
                or not isinstance(value, str)
                or not key
                or not value
                or len(key) > 256
                or len(value) > 160
                for key, value in assignments.items()
            ):
                raise ValueError("identity assignment names and IDs are invalid")
        if operation == BlenderOperation.SCAN_SCENE and "include_hidden" in parameters:
            if not isinstance(parameters["include_hidden"], bool):
                raise ValueError("include_hidden must be boolean")
        if operation == BlenderOperation.INSPECT_OBJECT and not isinstance(
            parameters.get("include_materials"), bool
        ):
            raise ValueError("include_materials must be boolean")
        if operation == BlenderOperation.CAPTURE_CONTEXT:
            _optional_bounded_string(parameters, "camera_name")
        if operation == BlenderOperation.ROLLBACK_SNAPSHOT:
            _required_bounded_string(parameters, "snapshot_id")


def _bounded_integer(parameters: Dict[str, Any], key: str, minimum: int, maximum: int) -> None:
    value = parameters.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError("%s must be between %d and %d" % (key, minimum, maximum))


def _bounded_number(value: Any, key: str, minimum: float, maximum: float) -> None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError("%s must be between %s and %s" % (key, minimum, maximum))


def _numeric_vector(
    value: Any,
    key: str,
    *,
    length: int = 3,
    minimum: float = -1_000_000,
    maximum: float = 1_000_000,
) -> None:
    if (
        not isinstance(value, list)
        or len(value) != length
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(item)
            or not minimum <= item <= maximum
            for item in value
        )
    ):
        raise ValueError(key + " must be a bounded numeric vector")


def _required_bounded_string(parameters: Dict[str, Any], key: str) -> None:
    value = parameters.get(key)
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError(key + " must be a non-empty string of at most 256 characters")


def _optional_bounded_string(parameters: Dict[str, Any], key: str) -> None:
    if key in parameters:
        _required_bounded_string(parameters, key)


class IntegrationHealth(BaseModel):
    integration_id: Literal["blender"] = "blender"
    healthy: bool
    mode: ExecutionMode
    version: Optional[str] = None
    code: str
    message: str
    checked_at: str


class CapabilityReport(BaseModel):
    integration_id: Literal["blender"] = "blender"
    adapter_version: str
    operations: List[BlenderOperation]
    export_formats: List[str]
    render_passes: List[str]
    collider_methods: List[str]
    arbitrary_python: Literal[False] = False


class StructuredLog(BaseModel):
    timestamp: str
    level: str = Field(pattern="^(debug|info|warning|error)$")
    code: str
    message: str
    request_id: str


class BlenderResult(BaseModel):
    request_id: str
    operation: BlenderOperation
    mode: ExecutionMode
    succeeded: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    logs: List[StructuredLog] = Field(default_factory=list)
    retryable: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ChangePreview(BaseModel):
    request_id: str
    operation: BlenderOperation
    mode: ExecutionMode = ExecutionMode.PLANNED
    source_path: Optional[str]
    output_paths: List[str]
    target_object_ids: List[str]
    parameter_keys: List[str]
    requires_approval: bool


class BlenderAdapterError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
