"""Opt-in S4 acceptance: one real model repairs one real browser-detected bug."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from sceneops_ai_agents import AgentTaskService, AuthorizeAgentTask, PrepareAgentTask
from sceneops_ai_agents.context_projection import project_game_diagnostics
from sceneops_ai_provider import ProviderService
from sceneops_project_workspace import SqliteWorkspaceRepository
import test_game_project_runtime_smoke as fixture


SEQUENCE = {'check': 'movement-collection', 'state_id': 'start', 'steps': [
    {'keys': ['ArrowDown'], 'duration_ms': 400}, {'keys': [], 'duration_ms': 160},
    {'keys': ['ArrowUp'], 'duration_ms': 400}, {'keys': ['ArrowDown'], 'duration_ms': 400},
]}


def prepare_dependencies(worktree):
    result = subprocess.run([os.environ.get('SCENEOPS_S4_PNPM', 'pnpm'), 'install',
        '--offline', '--ignore-scripts', '--ignore-workspace', '--no-lockfile'],
        cwd=worktree, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=180, check=False)
    if result.returncode:
        raise AssertionError(result.stdout)


class BrowserArchitectureRegression(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.environ.get('SCENEOPS_S4_REAL_BROWSER') == '1',
                         'explicit real browser regression required')
    async def test_current_behavior_and_delivery_input_on_both_architectures(self):
        evidence_root = Path(os.environ['SCENEOPS_S4_EVIDENCE_DIRECTORY']).resolve()
        evidence_root.mkdir(parents=True, exist_ok=True)
        for architecture in ('object-component', 'ecs'):
            if os.environ.get('SCENEOPS_S4_ARCHITECTURE') not in (None, architecture):
                continue
            with self.subTest(architecture=architecture), tempfile.TemporaryDirectory(
                    prefix=f'sceneops-s4-{architecture}-') as directory:
                root = Path(directory).resolve()
                database = root / 'sceneops.sqlite3'
                repository = SqliteWorkspaceRepository(database)
                project = repository.create_folder_project(root, f'S4 {architecture} regression')
                repository.commit_design_version(project.project_id, 1, {'version': 1})
                repository.initialize_game_project(project.project_id, {
                    'target_platform': 'web', 'engine': 'threejs',
                    'code_architecture': architecture, 'architecture_label': architecture,
                    'selection_method': 'manual', 'rationale': 'S4 browser regression',
                    'tradeoffs': [], 'ecs_library': 'miniplex' if architecture == 'ecs' else None,
                }, 1)
                repository.open_card_worktree(project.project_id, 'card_regression', 'Regression')
                worktree = Path(repository.get_card_worktree(project.project_id,
                                                             'card_regression')['worktree_path'])
                prepare_dependencies(worktree)
                provider = SimpleNamespace(database_path=database,
                    settings=lambda: SimpleNamespace(provider='fixture', model='fixture'))
                service = AgentTaskService(database, repository, root, provider=provider)
                try:
                    task = service.prepare(PrepareAgentTask(project_id=project.project_id,
                        card_id='card_regression', task_profile='card-development',
                        goal='两种架构受控输入回归', allow_game_execution=True,
                        allow_browser_interaction=True))
                    main = (worktree / 'src/main.ts').read_text(encoding='utf-8')
                    actions = [
                        fixture.action('touch-source', 'code.file.write', path='src/main.ts',
                            expected_content=main, content=main + '\n// S4 isolated regression\n'),
                        fixture.action('check-types', 'code.project.check'),
                        fixture.action('build-test', 'code.project.build_test'),
                        fixture.action('check-behavior', 'code.browser.interact', **SEQUENCE),
                        fixture.action('build-delivery', 'code.project.build'),
                        fixture.action('start-preview', 'code.preview.start'),
                        fixture.action('check-input', 'code.browser.interact', check='current-input',
                            state_id='start', steps=SEQUENCE['steps'][:2]),
                        fixture.action('finish', 'agent.finish', summary='S4 bounded regression evidence'),
                    ]
                    service.authorize(task.id, AuthorizeAgentTask(
                        authorization_card_id=task.authorization_card.id,
                        accept_unknown_cost=True), actions=actions)
                    await asyncio.wait_for(asyncio.gather(*list(service.jobs.values())), timeout=180)
                    completed = service.get(task.id)
                    diagnostics = project_game_diagnostics(completed)
                    self.assertEqual(completed.status, 'review_required', completed.reason)
                    self.assertEqual(diagnostics['checks']['movement-collection']['evidence_status'],
                                     'pass', diagnostics)
                    self.assertEqual(diagnostics['checks']['current-input']['evidence_status'],
                                     'pass', diagnostics)
                    (evidence_root / f'{architecture}-regression.json').write_text(json.dumps({
                        'architecture': architecture, 'status': completed.status,
                        'reason': completed.reason, 'diagnostics': diagnostics,
                    }, ensure_ascii=False, indent=2), encoding='utf-8')
                finally:
                    await service.close()


class RealAgentRepairAcceptance(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.environ.get('SCENEOPS_S4_REAL_MODEL') == '1',
                         'explicit real model and browser acceptance required')
    async def test_agent_repairs_repeat_scoring_from_structured_browser_evidence(self):
        evidence_root = Path(os.environ['SCENEOPS_S4_EVIDENCE_DIRECTORY']).resolve()
        evidence_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='sceneops-s4-') as directory:
            root = Path(directory).resolve()
            database = root / 'sceneops.sqlite3'
            repository = SqliteWorkspaceRepository(database)
            project = repository.create_folder_project(root, 'S4 repeat scoring acceptance')
            repository.commit_design_version(project.project_id, 1, {'version': 1})
            repository.initialize_game_project(project.project_id, {
                'target_platform': 'web', 'engine': 'threejs',
                'code_architecture': 'object-component',
                'architecture_label': 'Object / component', 'selection_method': 'manual',
                'rationale': 'S4 isolated acceptance', 'tradeoffs': [], 'ecs_library': None,
            }, 1)
            card = repository.open_card_worktree(project.project_id, 'card_repeat_score',
                                                 'Repeat score repair')
            worktree = Path(card['worktree_path'])
            prepare_dependencies(worktree)
            source_path = worktree / 'src/game/objects/Collectible.ts'
            original = source_path.read_text(encoding='utf-8')
            bug = original.replace(
                "if (this.collected || this.mesh.position.distanceTo(player) >= 0.9) return false",
                "if (this.mesh.position.distanceTo(player) >= 0.9) { this.collected = false; return false }\n"
                "    if (this.collected) return false",
            )
            self.assertNotEqual(original, bug)
            source_path.write_text(bug, encoding='utf-8')
            protected = (worktree / 'src/game/sceneops-test.ts').read_text(encoding='utf-8')
            provider = ProviderService(database)
            provider.update_settings(provider='codexcli', model='cli-default')
            service = AgentTaskService(database, repository, root, provider=provider)
            try:
                task = service.prepare(PrepareAgentTask(project_id=project.project_id,
                    card_id='card_repeat_score', task_profile='card-development',
                    goal=('修复当前游戏里同一个收集物离开后再次经过会重复加分的问题。用同一条固定玩家输入做修复前后对比：'
                          'ArrowDown 400ms、松键 160ms、ArrowUp 400ms、ArrowDown 400ms，'
                          '检查范围为 movement-collection、起点为 start。先用现有受控检查读取真实失败证据，'
                          '诊断并增量修改原游戏实现；不要修改断言、测试 hooks、测试起点或检查脚本，也不要删除收集功能。'
                          '修复后复跑同一检查，并用普通交付构建确认基础移动仍正常。按实际证据报告。'),
                    allow_game_execution=True, allow_browser_interaction=True,
                    allow_model_image_input=True, allow_dependency_install=False))
                service.authorize(task.id, AuthorizeAgentTask(
                    authorization_card_id=task.authorization_card.id,
                    accept_unknown_cost=True))
                await asyncio.wait_for(asyncio.gather(*list(service.jobs.values())), timeout=1200)
                completed = service.get(task.id)
                (evidence_root / 'real-agent-repair-attempt.json').write_text(
                    completed.model_dump_json(indent=2), encoding='utf-8')
                browser_entries = [entry for entry in completed.actions
                    if entry.action.capability_id == 'code.browser.interact'
                    and isinstance(entry.result, dict) and 'evidence' in entry.result]
                browser_evidence = [entry.result['evidence']['run'] for entry in browser_entries]
                behavior = [run for run in browser_evidence
                    if (run.get('observation') or {}).get('check_scope') == 'movement-collection']
                delivery = [run for run in browser_evidence
                    if (run.get('observation') or {}).get('check_scope') == 'current-input']
                failed = next(run for run in behavior
                    if run.get('failure_code') == 'BROWSER_BEHAVIOR_CHECK_FAILED')
                passed = next(run for run in reversed(behavior)
                    if run.get('status') == 'succeeded' and run.get('passed') is True)
                ordinary = next(run for run in reversed(delivery)
                    if run.get('status') == 'succeeded' and run.get('passed') is True)
                failed_ids = [item['id'] for item in failed['observation']['assertions']
                              if item['passed'] is False]
                self.assertIn('same-items-not-scored-twice', failed_ids)
                self.assertEqual(completed.status, 'review_required', completed.reason)
                self.assertLessEqual(completed.model_calls_used, 16)
                self.assertGreater(completed.model_calls_used, 0)
                self.assertNotEqual(source_path.read_text(encoding='utf-8'), bug)
                self.assertEqual((worktree / 'src/game/sceneops-test.ts').read_text(encoding='utf-8'), protected)
                audits = completed.observations.get('model_image_inputs', [])
                self.assertTrue(any(item.get('status') == 'provided'
                                    and item.get('artifact_id') in failed['artifact_ids'] for item in audits))
                diagnostics = project_game_diagnostics(completed)
                self.assertEqual(diagnostics['checks']['movement-collection']['evidence_status'], 'pass')
                self.assertEqual(diagnostics['checks']['current-input']['evidence_status'], 'pass')
                report = {
                    'task_id': completed.id, 'project_id': completed.project_id,
                    'provider': completed.provider_id, 'model': completed.provider_model,
                    'status': completed.status, 'reason': completed.reason,
                    'model_calls_used': completed.model_calls_used,
                    'model_tokens_known': completed.model_tokens_known,
                    'model_tokens_reported': completed.model_tokens_known > 0,
                    'actions': [{'action_id': entry.action.action_id,
                                 'capability_id': entry.action.capability_id,
                                 'rationale': entry.action.rationale,
                                 'inputs': entry.action.inputs,
                                 'state': entry.state} for entry in completed.actions],
                    'failed_browser_run': failed,
                    'passed_browser_run': passed,
                    'delivery_browser_run': ordinary,
                    'model_image_inputs': audits,
                    'diagnostics': diagnostics,
                    'changed_file': 'src/game/objects/Collectible.ts',
                    'final_source': source_path.read_text(encoding='utf-8'),
                    'protected_test_adapter_unchanged': True,
                    'execution_driver': completed.observations.get('execution_driver', 'agent'),
                }
                (evidence_root / 'real-agent-repair.json').write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                screenshot = root / 'production-artifacts' / passed['artifact_ids'][0] / '1'
                if screenshot.is_file():
                    shutil.copy2(screenshot, evidence_root / 'post-fix-current-view.png')
            finally:
                await service.close()


if __name__ == '__main__':
    unittest.main()
