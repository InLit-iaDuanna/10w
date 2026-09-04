from __future__ import annotations

import shutil
from pathlib import Path
import json
from typing import Callable, Dict, List, Optional, Tuple

from .artifacts import artifact_sha256, build_mock_glb
from .contracts import (
    BlenderAdapterError,
    BlenderCommand,
    BlenderOperation,
    BlenderResult,
    CapabilityReport,
    ChangePreview,
    ExecutionMode,
    IntegrationHealth,
    PERSISTENT_SCENE_MUTATIONS,
    StructuredLog,
)
from .path_policy import ProjectPathPolicy
from .support import capabilities, preview


class DeterministicMockBlenderAdapter:
    mode = ExecutionMode.MOCK

    def __init__(
        self,
        project_root: Path,
        *,
        triangle_count: int = 840,
        has_uv: bool = True,
        fail_operations: Optional[Dict[BlenderOperation, BlenderAdapterError]] = None,
    ) -> None:
        self.paths = ProjectPathPolicy(project_root)
        self.project_root = self.paths.project_root
        self.triangle_count = triangle_count
        self.has_uv = has_uv
        self.fail_operations = fail_operations or {}
        self.call_counts: Dict[BlenderOperation, int] = {}
        self.rollback_count = 0
        self.generated_identities: List[Dict[str, str]] = []
        self._completed: Dict[str, Tuple[str, BlenderResult]] = {}

    def health_check(self, timeout_seconds: float = 5) -> IntegrationHealth:
        return IntegrationHealth(
            healthy=True,
            mode=ExecutionMode.MOCK,
            version="mock-1",
            code="BLENDER_MOCK_READY",
            message="Deterministic Blender fixture adapter is selected.",
            checked_at="2026-09-04T00:00:00Z",
        )

    def capabilities(self) -> CapabilityReport:
        return capabilities()

    def dry_run(self, command: BlenderCommand) -> ChangePreview:
        if not command.dry_run:
            raise BlenderAdapterError("DRY_RUN_REQUIRED", "preview command must set dry_run=true")
        self._validate_paths(command)
        return preview(command)

    def execute(
        self,
        command: BlenderCommand,
        timeout_seconds: float,
        is_cancelled: Callable[[], bool] = lambda: False,
        on_progress: Callable[[float, str], None] = lambda _progress, _message: None,
    ) -> BlenderResult:
        if command.dry_run:
            raise BlenderAdapterError("DRY_RUN_EXECUTION_FORBIDDEN", "dry-run command cannot execute")
        self._validate_paths(command)
        signature = json.dumps(
            command.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        if command.request_id in self._completed:
            prior_signature, prior_result = self._completed[command.request_id]
            if signature != prior_signature:
                raise BlenderAdapterError(
                    "IDEMPOTENCY_CONFLICT", "request_id is bound to different inputs"
                )
            return prior_result.model_copy(deep=True)
        self.call_counts[command.operation] = self.call_counts.get(command.operation, 0) + 1
        failure = self.fail_operations.get(command.operation)
        if failure:
            raise failure
        if is_cancelled():
            raise BlenderAdapterError("BLENDER_CANCELLED", "mock command cancelled")
        on_progress(0.5, "Deterministic fixture operation running")
        data = self._result_data(command)
        on_progress(1.0, "Deterministic fixture operation completed")
        result = BlenderResult(
            request_id=command.request_id,
            operation=command.operation,
            mode=ExecutionMode.MOCK,
            succeeded=True,
            data=data,
            logs=[
                StructuredLog(
                    timestamp="2026-09-04T00:00:00Z",
                    level="info",
                    code="MOCK_OPERATION_COMPLETED",
                    message="Deterministic fixture output; Blender was not invoked.",
                    request_id=command.request_id,
                )
            ],
        )
        self._completed[command.request_id] = (signature, result.model_copy(deep=True))
        return result

    def _validate_paths(self, command: BlenderCommand) -> None:
        if command.source_path:
            self.paths.resolve(command.source_path, must_exist=True)
        self.paths.validate_all(command.output_paths)
        if command.operation in PERSISTENT_SCENE_MUTATIONS and not command.dry_run:
            self.paths.require_asset_factory_working_copy(command.source_path or "", must_exist=True)
        if command.operation == BlenderOperation.SAVE_SNAPSHOT:
            self.paths.require_asset_factory_snapshot(command.output_paths[0])
            self.paths.require_asset_factory_working_copy(command.output_paths[1])
        if command.operation == BlenderOperation.ROLLBACK_SNAPSHOT:
            self.paths.require_asset_factory_snapshot(command.source_path or "")
            self.paths.require_asset_factory_working_copy(command.output_paths[0])

    def _result_data(self, command: BlenderCommand) -> Dict[str, object]:
        operation = command.operation
        if operation == BlenderOperation.SCAN_SCENE:
            return self._scan_result()
        if operation == BlenderOperation.CHECK_GEOMETRY:
            return self._geometry_result(command)
        if operation == BlenderOperation.SAVE_SNAPSHOT:
            return self._save_snapshot(command)
        if operation == BlenderOperation.ROLLBACK_SNAPSHOT:
            self.rollback_count += 1
            source = self.paths.resolve(command.source_path or "", must_exist=True)
            working = self.paths.resolve(command.output_paths[0])
            working.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, working)
            return {"snapshot_id": command.parameters["snapshot_id"], "rolled_back": True}
        if operation == BlenderOperation.GENERATE_LOD:
            self.generated_identities.extend(
                {
                    "sceneops_id": "%s_lod%d" % (source_id, index),
                    "display_name": "LOD%d" % index,
                    "source_object_locator": "Generated/%s_LOD%d" % (source_id, index),
                }
                for source_id in command.object_ids
                for index, _ratio in enumerate(command.parameters["ratios"], start=1)
            )
            return {"created_sceneops_ids": [item["sceneops_id"] for item in self.generated_identities]}
        if operation == BlenderOperation.GENERATE_COLLIDER:
            created = [
                {
                    "sceneops_id": source_id + "_collider",
                    "display_name": "Collider",
                    "source_object_locator": "Generated/%s_COLLIDER" % source_id,
                }
                for source_id in command.object_ids
            ]
            self.generated_identities.extend(created)
            return {"created_sceneops_ids": [item["sceneops_id"] for item in created]}
        if operation == BlenderOperation.EXPORT_ASSET:
            identities = [
                *(command.object_ids or ["sop_hero_key_mesh"]),
                *[item["sceneops_id"] for item in self.generated_identities],
            ]
            artifacts = [self._write_artifact(value, identities) for value in command.output_paths]
            return {
                "artifacts": artifacts,
                "sceneops_ids": identities,
                "object_identities": self.generated_identities,
            }
        if operation == BlenderOperation.RENDER_AOV:
            return {"passes": command.parameters.get("passes", []), "artifacts": []}
        return {"changed_object_ids": command.object_ids, "operation": operation.value}

    def _scan_result(self) -> Dict[str, object]:
        return {
            "scene": "MockAssetScene",
            "objects": [
                {
                    "name": "HeroKey",
                    "type": "MESH",
                    "sceneops_id": "sop_hero_key_mesh",
                    "triangle_count": self.triangle_count,
                    "has_uv": self.has_uv,
                }
            ],
        }

    def _geometry_result(self, command: BlenderCommand) -> Dict[str, object]:
        budget = int(command.parameters.get("triangle_budget", self.triangle_count))
        require_uv = bool(command.parameters.get("require_uv", False))
        lod_count = len(
            [item for item in self.generated_identities if "_lod" in item["sceneops_id"]]
        )
        has_collider = any(
            item["sceneops_id"].endswith("_collider") for item in self.generated_identities
        )
        return {
            "metrics": {
                "dimensions_m": {"x": 0.04, "y": 0.01, "z": 0.1},
                "triangle_count": self.triangle_count,
                "vertex_count": 460,
                "material_count": 1,
                "texture_count": 2,
                "has_uv": self.has_uv,
                "is_rigged": False,
                "animation_names": [],
                "lod_count": lod_count,
                "collider_kind": "convex_hull" if has_collider else None,
                "nonmanifold_edge_count": 0,
            },
            "gates": [
                {
                    "gate_id": "geometry",
                    "status": "passed" if self.triangle_count <= budget else "failed",
                    "blocking": True,
                    "measurements": {
                        "triangle_count": self.triangle_count,
                        "nonmanifold_edge_count": 0,
                    },
                },
                {"gate_id": "uv_material", "status": "passed" if self.has_uv or not require_uv else "failed", "blocking": True},
                {"gate_id": "identity", "status": "passed", "blocking": True},
            ],
        }

    def _save_snapshot(self, command: BlenderCommand) -> Dict[str, object]:
        source = self.paths.resolve(command.source_path or "", must_exist=True)
        snapshot = self.paths.resolve(command.output_paths[0])
        working = self.paths.resolve(command.output_paths[1])
        for target in (snapshot, working):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return {
            "snapshot_id": snapshot.stem,
            "snapshot_path": command.output_paths[0],
            "working_copy_path": command.output_paths[1],
        }

    def _write_artifact(self, relative_path: str, identities: List[str]) -> Dict[str, object]:
        path = self.paths.resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.casefold() == ".glb":
            path.write_bytes(build_mock_glb(identities))
            media_type, format_name = "model/gltf-binary", "glb"
        elif path.suffix.casefold() == ".fbx":
            path.write_bytes(b"; FBX 7.4.0 project file\n; deterministic SceneOps mock\n")
            media_type, format_name = "application/octet-stream", "fbx"
        else:
            raise BlenderAdapterError("OUTPUT_FORMAT_INVALID", "mock export path must end in .glb or .fbx")
        return {
            "artifact_id": "art_%s_%s" % (path.stem.replace("-", "_"), format_name),
            "format": format_name,
            "project_relative_path": path.relative_to(self.paths.project_root).as_posix(),
            "media_type": media_type,
            "byte_size": path.stat().st_size,
            "sha256": artifact_sha256(path),
        }
