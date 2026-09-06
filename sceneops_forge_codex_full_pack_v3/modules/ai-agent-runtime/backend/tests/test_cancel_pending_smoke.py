"""One injected lifecycle smoke; no model, Unity or external process."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from sceneops_ai_agents import AgentTaskService, PrepareAgentTask


class CancelPendingSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_is_pending_until_stop_is_confirmed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = SimpleNamespace(create_project=lambda name: SimpleNamespace(project_id='prj_cancel_fixture'),
                get_project=lambda project: SimpleNamespace(project_id=project))
            provider = SimpleNamespace(database_path=root/'state.sqlite3', settings=lambda: SimpleNamespace(provider='codebuddycli', model='glm-5.3-flash'))
            service = AgentTaskService(root/'state.sqlite3', workspace, root, provider=provider)
            task = service.prepare(PrepareAgentTask(goal='fixture'))
            release = asyncio.Event()
            async def stop():
                await release.wait()
                return []
            service.tools[task.id] = SimpleNamespace(stop=stop, has_connected_sessions=lambda: True)
            requested = service.cancel(task.id)
            self.assertEqual(requested.status, 'cancel_pending')
            self.assertIsNone(requested.finished_at)
            release.set()
            await asyncio.gather(*list(service.cleanups.values()))
            self.assertEqual(service.get(task.id).status, 'cancelled')
            self.assertIsNotNone(service.get(task.id).finished_at)
