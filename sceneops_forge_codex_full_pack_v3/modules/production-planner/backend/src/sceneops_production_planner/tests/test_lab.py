"""Lab contract coverage. Not run: broader tests require user approval."""
import unittest
from fastapi.testclient import TestClient
from sceneops_production_planner import create_planning_lab_app
from sceneops_production_planner.fixtures import key_door_snapshot

class LabContractTests(unittest.TestCase):
    def test_create_and_edit_with_version_check(self):
        client = TestClient(create_planning_lab_app())
        response = client.post('/v1/planning-lab/create', json={'snapshot':key_door_snapshot().model_dump(mode='json')})
        self.assertEqual(response.status_code, 200)
        plan = response.json()['plan']
        request = {'expected_version':plan['plan_version'], 'task_id':plan['tasks'][0]['task_id'],
            'title':'检查设计边界', 'description':'审核玩家目标和验收条件。'}
        path = f"/v1/planning-lab/{plan['plan_id']}/edit"
        edited = client.post(path, json=request)
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()['tasks'][0]['title'], request['title'])
        stale = client.post(path, json=request)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()['code'], 'CONCURRENT_PLAN_WRITE')

    def test_reject_claimed_live_projection(self):
        client = TestClient(create_planning_lab_app())
        snapshot = key_door_snapshot().model_dump(mode='json')
        snapshot['source_mode'] = 'live'
        result = client.post('/v1/planning-lab/create', json={'snapshot':snapshot})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json()['code'], 'MOCK_ONLY')
