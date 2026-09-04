"""Stable identity relationships across published assets and Unity objects."""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from .errors import ErrorCode, UnityIntegrationError


class IdentityMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_asset_id: str = Field(pattern=r"^ast_")
    source_asset_version_id: str = Field(pattern=r"^astv_")
    source_object_id: str = Field(min_length=1)
    sceneops_id: str = Field(pattern=r"^sobj_")
    unity_asset_guid: str = Field(min_length=1)
    prefab_id: Optional[str] = Field(default=None, pattern=r"^prefab_")
    scene_instance_id: Optional[str] = Field(default=None, pattern=r"^sinst_")
    copied_from_scene_instance_id: Optional[str] = Field(default=None, pattern=r"^sinst_")
    display_name: str = ""

    def renamed(self, display_name: str) -> "IdentityMap":
        return self.model_copy(update={"display_name": display_name})

    def prefab_instance(self, prefab_id: str, scene_instance_id: str) -> "IdentityMap":
        return self.model_copy(
            update={"prefab_id": prefab_id, "scene_instance_id": scene_instance_id}
        )

    def copied(self, scene_instance_id: str, display_name: str = "") -> "IdentityMap":
        if not self.scene_instance_id:
            raise UnityIntegrationError(
                ErrorCode.IDENTITY_CONFLICT,
                "Only a scene instance can be copied.",
            )
        if scene_instance_id == self.scene_instance_id:
            raise UnityIntegrationError(
                ErrorCode.IDENTITY_CONFLICT,
                "A copied Unity GameObject must receive a new scene-instance identity.",
            )
        return self.model_copy(
            update={
                "scene_instance_id": scene_instance_id,
                "copied_from_scene_instance_id": self.scene_instance_id,
                "display_name": display_name or self.display_name,
            }
        )

    def telemetry_fields(self) -> Dict[str, Optional[str]]:
        return {
            "source_asset_id": self.source_asset_id,
            "source_asset_version_id": self.source_asset_version_id,
            "source_object_id": self.source_object_id,
            "sceneops_id": self.sceneops_id,
            "unity_asset_guid": self.unity_asset_guid,
            "prefab_id": self.prefab_id,
            "scene_instance_id": self.scene_instance_id,
        }


class IdentityRegistry:
    """A module-local read model keyed by stable IDs rather than names or paths."""

    def __init__(self, records: Iterable[IdentityMap] = ()) -> None:
        self._by_instance: Dict[str, IdentityMap] = {}
        self._by_asset_object: Dict[Tuple[str, str], IdentityMap] = {}
        for record in records:
            self.register(record)

    def register(self, record: IdentityMap) -> None:
        object_key = (record.source_asset_version_id, record.sceneops_id)
        existing_object = self._by_asset_object.get(object_key)
        if existing_object and existing_object.unity_asset_guid != record.unity_asset_guid:
            raise UnityIntegrationError(
                ErrorCode.IDENTITY_CONFLICT,
                "Published object identity is already mapped to a different Unity asset.",
                details={"sceneops_id": record.sceneops_id},
            )
        if record.scene_instance_id:
            existing_instance = self._by_instance.get(record.scene_instance_id)
            if existing_instance and existing_instance != record:
                raise UnityIntegrationError(
                    ErrorCode.IDENTITY_CONFLICT,
                    "Unity scene-instance identity is already registered.",
                    details={"scene_instance_id": record.scene_instance_id},
                )
            self._by_instance[record.scene_instance_id] = record
        self._by_asset_object[object_key] = record

    def by_scene_instance(self, scene_instance_id: str) -> IdentityMap:
        try:
            return self._by_instance[scene_instance_id]
        except KeyError as exc:
            raise UnityIntegrationError(
                ErrorCode.MISSING_REFERENCE,
                "Unity scene-instance identity is not mapped.",
                details={"scene_instance_id": scene_instance_id},
            ) from exc
    def by_published_object(self, asset_version_id: str, sceneops_id: str) -> IdentityMap:
        try:
            return self._by_asset_object[(asset_version_id, sceneops_id)]
        except KeyError as exc:
            raise UnityIntegrationError(
                ErrorCode.MISSING_REFERENCE,
                "Published object identity is not mapped into Unity.",
                details={
                    "source_asset_version_id": asset_version_id,
                    "sceneops_id": sceneops_id,
                },
            ) from exc
