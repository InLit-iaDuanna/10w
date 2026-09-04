from __future__ import annotations

import json
import unittest

from engine_unity.contracts import CommandName, ExecutionMode
from engine_unity.runner import UnityBatchRunner

from engine_unity.tests.support import request


class RunnerContractTests(unittest.TestCase):
    def test_router_method_is_fixed(self) -> None:
        self.assertEqual(
            "SceneOps.Forge.Unity.Editor.SceneOpsBatchCommandRouter.Execute",
            UnityBatchRunner.ROUTER_METHOD,
        )

    def test_component_value_is_encoded_as_data_not_a_method_or_flag(self) -> None:
        command = request(
            CommandName.SET_COMPONENT_PROPERTY,
            {
                "sceneops_id": "sobj_home_key",
                "component_type": "BoxCollider",
                "property_path": "m_IsTrigger",
                "value": True,
            },
            mode=ExecutionMode.LIVE,
        )
        wire = UnityBatchRunner._wire_request(command)
        payload = json.loads(wire["payloadJson"])
        self.assertNotIn("value", payload)
        self.assertEqual("true", payload["value_json"])
        self.assertNotIn("executeMethod", payload)
        change_set = json.loads(wire["changeSetJson"])
        self.assertEqual(command.command.value, change_set["command"])
        self.assertEqual(wire["payloadJson"], change_set["proposed_payload_json"])
        self.assertEqual(["sobj_home_key"], change_set["target_object_ids"])


if __name__ == "__main__":
    unittest.main()
