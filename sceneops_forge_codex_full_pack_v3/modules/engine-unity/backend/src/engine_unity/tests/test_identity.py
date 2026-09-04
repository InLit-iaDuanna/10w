from __future__ import annotations

import unittest

from engine_unity.errors import ErrorCode, UnityIntegrationError
from engine_unity.identity import IdentityMap, IdentityRegistry


def identity(instance_id: str = "sinst_home_key_a") -> IdentityMap:
    return IdentityMap(
        source_asset_id="ast_home_key",
        source_asset_version_id="astv_home_key_001",
        source_object_id="blobj_home_key",
        sceneops_id="sobj_home_key",
        unity_asset_guid="11111111111111111111111111111111",
        prefab_id="prefab_home_key",
        scene_instance_id=instance_id,
        display_name="Home Key",
    )


class IdentityTests(unittest.TestCase):
    def test_rename_preserves_every_stable_identity(self) -> None:
        original = identity()
        renamed = original.renamed("Entrance Key")
        before = original.model_dump(exclude={"display_name"})
        after = renamed.model_dump(exclude={"display_name"})
        self.assertEqual(before, after)
        self.assertEqual("Entrance Key", renamed.display_name)

    def test_copy_preserves_asset_and_prefab_but_gets_new_instance(self) -> None:
        original = identity()
        copied = original.copied("sinst_home_key_b", "Home Key Copy")
        self.assertEqual(original.sceneops_id, copied.sceneops_id)
        self.assertEqual(original.prefab_id, copied.prefab_id)
        self.assertEqual("sinst_home_key_b", copied.scene_instance_id)
        self.assertEqual(original.scene_instance_id, copied.copied_from_scene_instance_id)

    def test_copy_cannot_reuse_scene_instance_id(self) -> None:
        with self.assertRaises(UnityIntegrationError) as captured:
            identity().copied("sinst_home_key_a")
        self.assertEqual(ErrorCode.IDENTITY_CONFLICT, captured.exception.code)

    def test_prefab_instance_relationship_appears_in_telemetry(self) -> None:
        mapped = identity().prefab_instance("prefab_home_key", "sinst_home_key_a")
        telemetry = mapped.telemetry_fields()
        self.assertEqual("astv_home_key_001", telemetry["source_asset_version_id"])
        self.assertEqual("prefab_home_key", telemetry["prefab_id"])
        self.assertEqual("sinst_home_key_a", telemetry["scene_instance_id"])

    def test_registry_rejects_duplicate_instance_relationship(self) -> None:
        registry = IdentityRegistry([identity()])
        conflicting = identity().model_copy(update={"sceneops_id": "sobj_other"})
        with self.assertRaises(UnityIntegrationError) as captured:
            registry.register(conflicting)
        self.assertEqual(ErrorCode.IDENTITY_CONFLICT, captured.exception.code)


if __name__ == "__main__":
    unittest.main()
