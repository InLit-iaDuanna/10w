"""Production-only authorization and delivery smoke; no model or editor launch."""
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from engine_unity import PrototypeSpec
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask
from sceneops_ai_agents.task_models import AuthorizationCard
from sceneops_ai_agents.prototype_execution import finish_prototype
from sceneops_harness import HarnessError


class ProductionOnlySmoke(unittest.IsolatedAsyncioTestCase):
    def test_default_excludes_playtest_and_explicit_authorization_preserves_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = NS(create_project=lambda name: NS(project_id='prj_fixture'),
                get_project=lambda project: NS(project_id=project))
            provider = NS(database_path=root/'state.sqlite3', settings=lambda: NS(provider='codebuddycli', model='glm-5.3-flash'))
            service = AgentTaskService(root/'state.sqlite3', workspace, root, provider=provider)
            for profile in ('auto', 'survival-prototype'):
                for enabled in (False, True):
                    task = service.prepare(PrepareAgentTask(goal='fixture', task_profile=profile, allow_playtest=enabled))
                    self.assertEqual(task.authorization_card.allow_playtest, enabled)
                    for capability in ('play', 'capture', 'verify'):
                        self.assertEqual('unity.prototype.' + capability in task.authorization_card.capability_ids, enabled)
            old = AuthorizationCard.model_validate({'workspace_root': str(root), 'capability_ids': ['unity.prototype.verify']})
            self.assertTrue(old.allow_playtest)

    async def test_saved_compiled_scene_delivers_without_gameplay_and_rejects_drift(self):
        spec = PrototypeSpec(prototype_id='sobj_fixture123', title='fixture').model_dump(mode='json')
        compose = NS(action=NS(action_id='compose', capability_id='unity.prototype.compose'), state='succeeded',
            result={'evidence': {'result': {'project_revision': 'chg_fixture', 'spec': spec}}})
        task = NS(id='task_fixture', project_id='prj_fixture', actions=[compose],
            authorization_card=AuthorizationCard(workspace_root='/fixture'))
        artifact = NS(id='artifact_fixture', version=1, step_id='task_fixture:compose',
            source_path='unity/Assets/SceneOpsPrototype.unity', size_bytes=5)
        production = NS(snapshot=lambda project: NS(artifacts=[artifact]),
            artifact_content=lambda *args: (io.BytesIO(b'scene'), None),
            _open_regular=lambda path: (io.BytesIO(b'scene'), NS(st_size=5)))
        async def session(tool): return NS(project_root=Path('/fixture/unity'))
        async def sync(session, operation):
            if operation == 'inspect': return {'errors': []}
            return {'project_revision': 'chg_fixture', 'compiling': False, 'spec': spec}
        tools = NS(session=session, sync=sync, service=NS(production=production), validate_readback=lambda *args: None)
        result = await finish_prototype(tools, task)
        self.assertEqual(result['delivery_status'], 'production_ready')
        self.assertFalse(result['gameplay_verified'])
        self.assertNotIn('verification', result)
        production._open_regular = lambda path: (io.BytesIO(b'drift'), NS(st_size=5))
        with self.assertRaises(HarnessError): await finish_prototype(tools, task)
