"""Product game runtime: fixed commands, exact card worktree and repair evidence."""
import asyncio
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from sceneops_ai_agents import AgentAction, AgentTaskService, AuthorizeAgentTask, PrepareAgentTask
from sceneops_ai_agents.game_runtime import GameProjectRuntime
from sceneops_ai_agents.task_models import GameExecutionRun, GameOperationRequest
from sceneops_ai_agents.task_repository import AgentTaskRepository
from sceneops_harness import HarnessError


class WorkspaceFixture:
    def __init__(self, root):
        self.root = root

    def get_project(self, project_id):
        return SimpleNamespace(project_id=project_id)

    def get_card_worktree(self, project_id, card_id):
        root = (self.root / card_id).resolve()
        if not root.is_dir():
            raise ValueError('unknown card')
        return {'project_id': project_id, 'card_id': card_id, 'branch': f'codex/card-{card_id}',
                'worktree_path': str(root), 'base_commit': 'fixture'}


def action(identifier, capability, **inputs):
    return AgentAction(action_id=identifier, capability_id=capability,
                       rationale='fixture product operation', inputs=inputs)


class GameProjectRuntimeSmoke(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.worktrees = self.root / 'worktrees'
        self.worktrees.mkdir()
        for card in ('card_one', 'card_two'):
            project = self.worktrees / card
            (project / 'src').mkdir(parents=True)
            (project / 'package.json').write_text(
                '{"dependencies":{"three":"0.183.2"},"devDependencies":{"typescript":"6.0.3","vite":"8.0.0"}}',
                encoding='utf-8')
            (project / 'src/main.ts').write_text('export const value: number = 1;\n', encoding='utf-8')
        self.pnpm = self.root / 'fixture-pnpm'
        self.pnpm.write_text(f'''#!{Path(__import__('sys').executable).resolve()}
import pathlib, sys
root = pathlib.Path.cwd()
if sys.argv[1] == 'install':
    target = root / 'node_modules/.bin'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'tsc').write_text('fixture')
    (target / 'vite').write_text('fixture')
    print('dependencies prepared')
elif sys.argv[1:3] == ['exec', 'tsc']:
    bad = [p for p in root.rglob('*.ts') if 'TYPE_ERROR' in p.read_text()]
    if bad:
        print(str(bad[0]) + ':1: error TS2322: fixture type error')
        raise SystemExit(2)
    print('TypeScript check passed')
elif sys.argv[1:3] == ['exec', 'vite']:
    output = root / 'dist'
    output.mkdir(exist_ok=True)
    (output / 'index.html').write_text('<!doctype html><title>Fixture game</title><main>ready</main>')
    print('Vite build passed')
else:
    raise SystemExit(64)
''', encoding='utf-8')
        self.pnpm.chmod(self.pnpm.stat().st_mode | stat.S_IXUSR)
        self.workspace = WorkspaceFixture(self.worktrees)
        self.provider = SimpleNamespace(database_path=self.root / 'state.sqlite3',
            settings=lambda: SimpleNamespace(provider='codebuddycli', model='fixture'),
            generate=AsyncMock(side_effect=AssertionError('deterministic fixture must not call a model')))
        self.service = AgentTaskService(self.provider.database_path, self.workspace, self.root,
            provider=self.provider, pnpm_executable=str(self.pnpm))

    async def asyncTearDown(self):
        await self.service.close()
        self.directory.cleanup()

    def prepare(self, card='card_one', *, execution=True, install=True):
        return self.service.prepare(PrepareAgentTask(project_id='prj_fixture0001', card_id=card,
            task_profile='card-development', goal='修复并运行卡片游戏', allow_game_execution=execution,
            allow_dependency_install=install if execution else False))

    async def run_actions(self, task, actions):
        self.service.authorize(task.id, AuthorizeAgentTask(
            authorization_card_id=task.authorization_card.id, accept_unknown_cost=True), actions=actions)
        await asyncio.wait_for(asyncio.gather(*list(self.service.jobs.values())), timeout=10)
        return self.service.get(task.id)

    async def authorize_empty(self, task):
        return await self.run_actions(task, [])

    async def test_source_only_tasks_preserve_old_semantics(self):
        task = self.prepare(execution=False)
        self.assertEqual(task.authorization_card.max_model_calls, 8)
        self.assertNotIn('code.project.build', task.authorization_card.capability_ids)
        finished = await self.run_actions(task, [
            action('write', 'code.file.write', path='src/main.ts',
                   expected_content='export const value: number = 1;\n',
                   content='export const value: number = 2;\n'),
            action('finish', 'agent.finish', summary='source only'),
        ])
        self.assertEqual(finished.observations['code']['delivery_status'], 'code_written')
        with self.assertRaises(HarnessError):
            self.service.game_status(finished.id)

    async def test_fixture_error_is_observed_repaired_built_and_previewed(self):
        source = self.worktrees / 'card_one/src/main.ts'
        source.write_text('export const value: number = TYPE_ERROR;\n', encoding='utf-8')
        task = self.prepare()
        self.assertEqual(task.authorization_card.max_model_calls, 16)
        result = await self.run_actions(task, [
            action('status', 'code.project.status'),
            action('deps', 'code.dependencies.prepare'),
            action('bad_check', 'code.project.check'),
            action('read', 'code.file.read', path='src/main.ts'),
            action('repair', 'code.file.write', path='src/main.ts',
                   expected_content='export const value: number = TYPE_ERROR;\n',
                   content='export const value: number = 1;\n'),
            action('good_check', 'code.project.check'),
            action('build', 'code.project.build'),
            action('preview', 'code.preview.start'),
            action('finish', 'agent.finish', summary='fixed and running'),
        ])
        self.assertEqual(result.status, 'review_required', result.reason)
        self.assertEqual(result.observations['game_project']['delivery_status'], 'build_ready')
        failed_check = result.actions[2]
        self.assertEqual(failed_check.state, 'succeeded')
        self.assertFalse(failed_check.result['evidence']['run']['passed'])
        self.assertIn('TS2322', failed_check.result['evidence']['run']['log'])
        snapshot = self.service.game_status(task.id)
        self.assertEqual(snapshot.workspace_id, 'card_one')
        self.assertEqual(snapshot.preview.status, 'running')
        self.assertTrue(snapshot.preview.preview_url.startswith('http://127.0.0.1:'))
        self.assertEqual(snapshot.update_state, 'updated')
        self.assertEqual(snapshot.current_playable_candidate.id, snapshot.latest_candidate.id)
        self.assertEqual(snapshot.current_playable_candidate.build_run_id, snapshot.build.id)
        self.provider.generate.assert_not_awaited()

    async def test_failed_build_keeps_current_playable_candidate(self):
        task = await self.authorize_empty(self.prepare())
        await self.service.game_operation(task.id, GameOperationRequest(operation='prepare'))
        succeeded = await self.service.game_operation(task.id, GameOperationRequest(operation='build'))
        current_id = succeeded.current_playable_candidate.id
        (self.worktrees / 'card_one/src/main.ts').write_text(
            'export const value: number = TYPE_ERROR;\n', encoding='utf-8')

        failed = await self.service.game_operation(task.id, GameOperationRequest(operation='build'))

        self.assertEqual(failed.build.status, 'failed')
        self.assertEqual(failed.update_state, 'failed')
        self.assertEqual(len(failed.build_candidates), 2)
        self.assertEqual(failed.latest_candidate.status, 'failed')
        self.assertEqual(failed.latest_candidate.build_run_id, failed.build.id)
        self.assertEqual(failed.current_playable_candidate.id, current_id)
        self.assertEqual(failed.current_playable_candidate.status, 'succeeded')

    async def test_older_candidate_completion_cannot_replace_newer_candidate(self):
        task = await self.authorize_empty(self.prepare())
        grant = task.grant
        old_run = GameExecutionRun(operation='build', project_id=task.project_id,
            workspace_id=grant.card_id, card_id=grant.card_id, task_id=task.id,
            workspace_root=grant.workspace_root, branch=grant.branch)
        new_run = old_run.model_copy(update={'id': 'game_run_newer'})
        old_candidate = self.service.game._begin_candidate(old_run)
        new_candidate = self.service.game._begin_candidate(new_run)
        new_run.status, new_run.passed, new_run.artifact_path = 'succeeded', True, '/fixture/new'
        old_run.status, old_run.passed, old_run.artifact_path = 'succeeded', True, '/fixture/old'

        self.service.game._finish_candidate(new_run, new_candidate)
        self.service.game._finish_candidate(old_run, old_candidate)
        candidates, latest, current, update_state = self.service.game._candidate_snapshot(
            task.project_id, grant.card_id)

        self.assertEqual([item.sequence for item in candidates], [1, 2])
        self.assertEqual(candidates[0].status, 'superseded')
        self.assertEqual(latest.id, new_candidate.id)
        self.assertEqual(current.id, new_candidate.id)
        self.assertEqual(update_state, 'updated')

    async def test_legacy_card_runs_gain_workspace_identity_and_nullable_scope_columns(self):
        records = AgentTaskRepository(self.root / 'legacy.sqlite3')
        run = GameExecutionRun(operation='build', project_id='prj_legacy', workspace_id='legacy_card',
            card_id='legacy_card', task_id='task_legacy', workspace_root=str(self.worktrees / 'card_one'),
            branch='codex/card-legacy', status='succeeded', passed=True, artifact_path='/fixture/legacy')
        historical = run.model_dump(mode='json', exclude={'workspace_id', 'candidate_id', 'candidate_sequence'})
        with records.connect() as connection:
            connection.execute('''CREATE TABLE game_project_runs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, card_id TEXT NOT NULL,
                task_id TEXT NOT NULL, workspace_root TEXT NOT NULL, branch TEXT NOT NULL,
                operation TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL)''')
            connection.execute('INSERT INTO game_project_runs VALUES(?,?,?,?,?,?,?,?,?)',
                (run.id, run.project_id, run.card_id, run.task_id, run.workspace_root, run.branch,
                 run.operation, json.dumps(historical), run.started_at.isoformat()))

        runtime = GameProjectRuntime(records, self.root / 'legacy-data', pnpm_executable=str(self.pnpm))
        try:
            migrated = runtime._latest('prj_legacy', 'legacy_card', 'build')
            self.assertEqual(migrated.workspace_id, 'legacy_card')
            with records.connect() as connection:
                columns = {row[1]: row for row in connection.execute('PRAGMA table_info(game_project_runs)')}
            self.assertEqual(columns['card_id'][3], 0)
            self.assertEqual(columns['branch'][3], 0)
            self.assertEqual(columns['workspace_id'][3], 1)
        finally:
            await runtime.close()

    async def test_manual_operations_share_runtime_and_only_stop_owned_preview(self):
        first = await self.authorize_empty(self.prepare('card_one'))
        second = await self.authorize_empty(self.prepare('card_two'))
        for task in (first, second):
            await self.service.game_operation(task.id, GameOperationRequest(operation='prepare'))
            await self.service.game_operation(task.id, GameOperationRequest(operation='check'))
            await self.service.game_operation(task.id, GameOperationRequest(operation='build'))
            started = await self.service.game_operation(task.id, GameOperationRequest(operation='preview_start'))
            repeated = await self.service.game_operation(task.id, GameOperationRequest(operation='preview_start'))
            self.assertEqual(started.preview.id, repeated.preview.id)
        await self.service.game_operation(first.id, GameOperationRequest(operation='preview_stop'))
        self.assertNotEqual(self.service.game_status(first.id).preview.status, 'running')
        self.assertEqual(self.service.game_status(second.id).preview.status, 'running')

        before = (self.worktrees / 'card_two/src/main.ts').read_text()
        changed = await self.run_actions(self.prepare('card_two'), [
            action('change', 'code.file.write', path='src/main.ts', expected_content=before,
                   content='export const value: number = 9;\n')])
        stale = self.service.game_status(changed.id)
        self.assertEqual(stale.build.status, 'stale')
        self.assertTrue(stale.preview.source_stale)

    async def test_restart_does_not_trust_persisted_preview_process(self):
        task = await self.authorize_empty(self.prepare())
        for operation in ('prepare', 'check', 'build', 'preview_start'):
            await self.service.game_operation(task.id, GameOperationRequest(operation=operation))
        self.assertEqual(self.service.game_status(task.id).preview.status, 'running')
        await self.service.close()
        replacement = AgentTaskService(self.provider.database_path, self.workspace, self.root,
            provider=self.provider, pnpm_executable=str(self.pnpm))
        self.service = replacement
        self.assertNotEqual(replacement.game_status(task.id).preview.status, 'running')

    async def test_build_and_preview_reject_linked_output_directory(self):
        task = await self.authorize_empty(self.prepare())
        await self.service.game_operation(task.id, GameOperationRequest(operation='prepare'))
        outside = self.root / 'outside-output'
        outside.mkdir()
        (self.worktrees / 'card_one/dist').symlink_to(outside, target_is_directory=True)
        result = await self.service.game_operation(task.id, GameOperationRequest(operation='build'))
        self.assertEqual(result.build.status, 'failed')
        self.assertEqual(result.build.failure_code, 'BUILD_OUTPUT_INVALID')
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
