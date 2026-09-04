from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Dict, Iterable, List


@dataclass(frozen=True)
class BlenderObjectIdentity:
    locator: str
    display_name: str
    sceneops_id: str


class IdentityConflictError(ValueError):
    pass


class BlenderIdentityRegistry:
    """Tracks stable object identity independently from Blender names/locators."""

    def __init__(self, objects: Iterable[BlenderObjectIdentity]) -> None:
        self._objects: Dict[str, BlenderObjectIdentity] = {}
        for item in objects:
            if item.sceneops_id in self._objects:
                raise IdentityConflictError("duplicate sceneops_id: " + item.sceneops_id)
            self._objects[item.sceneops_id] = item

    def rename(self, sceneops_id: str, display_name: str, locator: str) -> BlenderObjectIdentity:
        current = self._objects[sceneops_id]
        renamed = replace(current, display_name=display_name, locator=locator)
        self._objects[sceneops_id] = renamed
        return renamed

    def copy(
        self,
        source_sceneops_id: str,
        display_name: str,
        locator: str,
        id_factory: Callable[[], str],
    ) -> BlenderObjectIdentity:
        if source_sceneops_id not in self._objects:
            raise KeyError(source_sceneops_id)
        new_id = id_factory()
        if new_id in self._objects or new_id == source_sceneops_id:
            raise IdentityConflictError("copy must receive a new sceneops_id")
        copied = BlenderObjectIdentity(locator=locator, display_name=display_name, sceneops_id=new_id)
        self._objects[new_id] = copied
        return copied

    def export_manifest(self) -> List[Dict[str, str]]:
        return [
            {
                "locator": item.locator,
                "display_name": item.display_name,
                "sceneops_id": item.sceneops_id,
            }
            for item in sorted(self._objects.values(), key=lambda candidate: candidate.sceneops_id)
        ]

    @classmethod
    def from_manifest(cls, values: Iterable[Dict[str, str]]) -> "BlenderIdentityRegistry":
        return cls(BlenderObjectIdentity(**item) for item in values)


def extract_sceneops_ids(gltf_json: Dict[str, object]) -> List[str]:
    identities: List[str] = []
    for node in gltf_json.get("nodes", []):
        if not isinstance(node, dict):
            continue
        extras = node.get("extras", {})
        if isinstance(extras, dict) and isinstance(extras.get("sceneops_id"), str):
            identities.append(extras["sceneops_id"])
    if len(identities) != len(set(identities)):
        raise IdentityConflictError("export contains duplicate sceneops_id values")
    return identities
