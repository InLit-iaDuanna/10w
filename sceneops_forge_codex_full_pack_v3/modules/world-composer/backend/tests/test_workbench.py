"""World proposal regression cases; pending approval to execute."""
import unittest
from fastapi import HTTPException
from world_composer.workbench import WorldPlanRequest, propose_world


class WorldProposalTests(unittest.TestCase):
    def plan(self):
        return WorldPlanRequest(
            schemaVersion=1, mutationKind="world.graph.update", baseVersion="scene-v1",
            targetModule="world-composer", targetIntegration="unity", targetSceneId="scn_home_hall",
            targetObjectIds=["sobj_home_key"], previousValues={"predicate": "unlocks"},
            proposedValues={"predicate": "opens"}, rationale="Clarify relation",
            expectedResult="Reviewed relation", impactScope=["scene:scn_home_hall"], risk="high",
            validationPlan=["Review stable IDs"], rollbackPlan=["Restore scene-v1"],
            approvalRoles=["level-designer"], dryRunRequired=True, mode="planned",
        )

    def test_world_plan_becomes_existing_core_changeset(self):
        result = propose_world(self.plan())
        self.assertEqual(result.status.value, "waiting_approval")
        self.assertEqual(result.target.object_ids, ["scn_home_hall", "sobj_home_key"])
        self.assertEqual(result.approval_requirements[0].permission, "scene:approve")

    def test_unchanged_proposal_is_rejected(self):
        plan = self.plan()
        plan.proposedValues = plan.previousValues
        with self.assertRaises(HTTPException) as error:
            propose_world(plan)
        self.assertEqual(error.exception.status_code, 422)
