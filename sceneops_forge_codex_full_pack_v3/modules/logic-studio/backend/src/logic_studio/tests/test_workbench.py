"""Workbench regression cases. Not run in the independent-Web delivery."""
import unittest

from fastapi import HTTPException
from logic_studio.workbench import (
    GraphProposalRequest, PreviewRequest, PreviewStep, demo_graph, preview, propose_graph,
)


class WorkbenchTests(unittest.TestCase):
    def test_preview_uses_stable_scene_binding(self):
        graph = demo_graph()
        result = preview(PreviewRequest(graph=graph, steps=[
            PreviewStep(target_node_id=node)
            for node in ["quest_active", "target_interaction", "locked_feedback", "collectible_pickup"]
        ]))
        self.assertEqual(result.state["inventory.items"], ["asset_key_home_01"])
        self.assertEqual(result.state["quest.stage"], "open_target")
        self.assertFalse(result.state["target.is_open"])
        self.assertEqual(graph.nodes[4].sceneops_ids, ["sobj_home_key"])

    def test_proposal_preserves_canonical_graph_and_approval(self):
        graph = demo_graph()
        nodes = list(graph.nodes)
        nodes[4] = nodes[4].model_copy(update={"label": "拾取钥匙"})
        draft = graph.model_copy(update={"nodes": nodes, "version": graph.version + 1})
        result = propose_graph(GraphProposalRequest(graph=draft, rationale="Clarify pickup"))
        self.assertEqual(result.change_set.status.value, "waiting_approval")
        self.assertTrue(result.change_set.dry_run_supported)
        self.assertEqual(result.change_set.approval_requirements[0].permission, "logic:approve")
        self.assertEqual(demo_graph().nodes[4].label, "Collect item")
        self.assertEqual(len(result.diff.entries), 1)

    def test_unknown_scene_binding_is_rejected(self):
        graph = demo_graph()
        objects = list(graph.scene_objects)
        objects[0] = objects[0].model_copy(update={"sceneops_id": "sobj_foreign_actor"})
        with self.assertRaises(HTTPException) as error:
            preview(PreviewRequest(graph=graph.model_copy(update={"scene_objects": objects})))
        self.assertEqual(error.exception.status_code, 422)

    def test_unavailable_transition_is_visible_error(self):
        with self.assertRaises(HTTPException) as error:
            preview(PreviewRequest(graph=demo_graph(), steps=[PreviewStep(target_node_id="ending")]))
        self.assertEqual(error.exception.status_code, 422)
