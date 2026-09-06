"""Root-run local output-manifest fixture; never starts a model or external tool."""
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sceneops_ai_agents.output_manifest import register_output_manifest
from sceneops_ai_agents.production_models import ProductionStep
from sceneops_ai_agents.production_store import ProductionStore
from sceneops_ai_agents.task_models import ActionRecord, AgentAction, AgentTaskRecord, AuthorizationCard, TaskGrant, now
from sceneops_ai_agents.task_repository import AgentTaskRepository


class OutputManifestSmoke(unittest.TestCase):
    def test_only_real_contained_outputs_become_reported_module_artifacts(self):
        with tempfile.TemporaryDirectory(prefix='sceneops-manifest-fixture-') as directory:
            data_dir = Path(directory).resolve()
            workspace_base = data_dir / 'agent-workspaces'
            root = workspace_base / 'prj_manifest_fixture'
            root.mkdir(parents=True)
            records = AgentTaskRepository(data_dir / 'fixture.sqlite3')
            task = AgentTaskRecord(project_id=root.name, goal='确定性产物清单夹具',
                authorization_card=AuthorizationCard(workspace_root=str(root), execution_mode='codex-full-access',
                    capability_ids=['codex.task.execute']))
            records.create(task)
            def authorize(current):
                current.grant = TaskGrant(task_id=current.id, project_id=current.project_id,
                    workspace_root=str(root), execution_mode='codex-full-access', capability_ids=['codex.task.execute'],
                    expires_at=now() + timedelta(minutes=5))
                current.status = 'queued'
                current.actions = [ActionRecord(action=AgentAction(action_id='codex_execution',
                    capability_id='codex.task.execute', rationale='本地夹具', inputs={'goal': current.goal}),
                    state='running', run_ids=['run_fixture'])]
            task = records.update(task.id, authorize, 'agent.task.authorized')
            production = ProductionStore(records.path, data_dir, records)
            service = SimpleNamespace(records=records, production=production, workspace_base=workspace_base, get=records.get)
            entry = task.actions[0]
            production.upsert_step(ProductionStep(id=f'{task.id}:codex_execution', project_id=task.project_id,
                task_id=task.id, module_id='integration-ops', title='主步骤夹具', capability_id='codex.task.execute',
                state='running', verification='reported', mode='live', updated_at=now().isoformat()))
            self.assertEqual(register_output_manifest(service, task, entry), [])
            self.assertEqual(records.events(task.id).events[-1].event_type, 'production.outputs.missing')

            (root / 'outputs').mkdir()
            (root / 'outputs' / 'draft.txt').write_text('Actual fixture content, not independently verified.', encoding='utf-8')
            manifest = root / 'sceneops-outputs.json'
            manifest.write_text(json.dumps({'version': 1, 'artifacts': [
                {'path': 'outputs/draft.txt', 'module_id': 'concept-assets'},
                {'path': 'outputs/not-created.png', 'module_id': 'render-ops'}
            ]}), encoding='utf-8')
            artifacts = register_output_manifest(service, task, entry)
            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0].verification, 'unverified')
            steps = production.snapshot(task.project_id).steps
            output = next(step for step in steps if step.id == f'{task.id}:outputs:concept-assets')
            self.assertEqual((output.state, output.verification), ('review_required', 'reported'))
            self.assertIn(artifacts[0].id, output.artifact_ids)
            self.assertFalse(any(step.module_id == 'render-ops' for step in steps))
            self.assertTrue(any(event.event_type == 'production.outputs.rejected' for event in records.events(task.id).events))

            for invalid in [
                {'version': True, 'artifacts': []},
                {'version': 1, 'artifacts': [{'path': '../outside.txt', 'module_id': 'concept-assets'}]},
                {'version': 1, 'artifacts': [{'path': '.credentials', 'module_id': 'concept-assets'}]},
                {'version': 1, 'artifacts': [], 'unexpected': 'secret-sentinel'},
            ]:
                manifest.write_text(json.dumps(invalid), encoding='utf-8')
                with patch.object(production, 'record_artifact') as register:
                    self.assertEqual(register_output_manifest(service, task, entry), [])
                    register.assert_not_called()
            outside = data_dir / 'outside.json'
            outside.write_text('secret-outside-manifest', encoding='utf-8')
            manifest.unlink()
            manifest.symlink_to(outside)
            self.assertEqual(register_output_manifest(service, task, entry), [])
            payloads = json.dumps([event.payload for event in records.events(task.id).events])
            self.assertNotIn('secret-outside-manifest', payloads)
            self.assertNotIn('secret-sentinel', payloads)


if __name__ == '__main__':
    unittest.main()
