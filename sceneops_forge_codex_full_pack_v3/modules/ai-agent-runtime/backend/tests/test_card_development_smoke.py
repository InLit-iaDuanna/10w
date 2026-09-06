"""Injected card-source tasks: no model, CLI, compiler, or gameplay execution."""
import asyncio
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from sceneops_ai_agents import AgentAction, AgentTaskService, AuthorizeAgentTask, PrepareAgentTask
from sceneops_harness import HarnessError


class CardWorkspaceFixture:
    def __init__(self, root):
        self.root = root
        self.lookups = []

    def get_project(self, project_id):
        return SimpleNamespace(project_id=project_id)

    def get_card_worktree(self, project_id, card_id):
        self.lookups.append((project_id, card_id))
        root = self.root / card_id
        if not root.is_dir():
            raise ValueError('Card worktree not registered')
        return {'project_id': project_id, 'card_id': card_id, 'branch': 'codex/card-' + card_id,
                'worktree_path': str(root), 'base_commit': 'fixture'}


def action(identifier, capability, **inputs):
    return AgentAction(action_id=identifier, capability_id=capability,
                       rationale='确定性源码检查', inputs=inputs)


class CardDevelopmentSmoke(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        self.worktrees = self.root / 'card-worktrees'
        self.worktrees.mkdir()
        (self.worktrees / 'card_one').mkdir()
        (self.worktrees / 'card_two').mkdir()
        self.workspace = CardWorkspaceFixture(self.worktrees)
        self.provider = SimpleNamespace(database_path=self.root / 'state.sqlite3',
            settings=lambda: SimpleNamespace(provider='codebuddycli', model='fixture'),
            generate=AsyncMock(side_effect=AssertionError('No model calls allowed')))
        self.service = AgentTaskService(self.provider.database_path, self.workspace,
                                       self.root, provider=self.provider)

    async def asyncTearDown(self):
        await self.service.close()
        self.directory.cleanup()

    def prepare(self, card='card_one'):
        return self.service.prepare(PrepareAgentTask(project_id='prj_cardfixture', card_id=card,
            task_profile='card-development', goal='实现此卡片的玩法源码'))

    async def execute(self, task, actions):
        self.service.authorize(task.id, AuthorizeAgentTask(
            authorization_card_id=task.authorization_card.id, accept_unknown_cost=True), actions=actions)
        await asyncio.gather(*list(self.service.jobs.values()))
        return self.service.get(task.id)

    async def test_card_write_readback_and_same_branch_continuation(self):
        source = self.worktrees / 'card_one' / 'main.ts'
        source.write_text('const speed = 1; // user edit\n', encoding='utf-8')
        before = source.read_text(encoding='utf-8')
        after = 'const speed = 2; // user edit preserved\n'
        task = self.prepare()
        self.assertEqual(source.read_text(), before)
        self.assertIsNone(task.grant)
        self.assertEqual(task.authorization_card.max_model_calls, 8)
        result = await self.execute(task, [
            action('inspect', 'code.workspace.inspect'),
            action('read', 'code.file.read', path='main.ts'),
            action('write', 'code.file.write', path='main.ts', expected_content=before, content=after),
            action('new', 'code.file.write', path='src/game.ts', expected_content=None, content='export const ready = true;\n'),
            action('finish', 'agent.finish', summary='源码开发完成，待检查'),
        ])
        self.assertEqual(result.status, 'review_required', result.reason)
        self.assertEqual(result.reason, '源码已写入并回读，待检查；未运行或编译。')
        self.assertEqual(source.read_text(), after)
        self.assertEqual(result.model_calls_used, 0)
        self.provider.generate.assert_not_awaited()
        write = result.actions[2]
        self.assertEqual(write.effect_state, 'COMMITTED')
        self.assertEqual(write.change_set.previous_values, {'path': 'main.ts', 'content': before})
        self.assertIsNotNone(write.approval_id)
        self.assertEqual(write.result['evidence']['readback'], after)
        self.assertIn('-const speed = 1;', write.result['evidence']['diff'])
        self.assertFalse(result.observations['code']['compilation_verified'])
        self.assertEqual(result.observations['code']['delivery_status'], 'code_written')
        self.assertFalse(self.service.records.owns_claim(result))
        self.assertFalse(self.service.records.owns_workspace(result.project_id, source.parent))
        second = await self.execute(self.prepare(), [
            action('edit_again', 'code.file.write', path='main.ts', expected_content=after, content='export const speed = 3;\n'),
            action('finish_again', 'agent.finish', summary='第二次源码检查'),
        ])
        self.assertEqual(second.status, 'review_required', second.reason)
        other_card = await self.execute(self.prepare('card_two'), [
            action('other', 'code.file.write', path='main.ts', expected_content=None, content='export const speed = 4;\n'),
            action('finish_other', 'agent.finish', summary='另一个卡片源码检查'),
        ])
        self.assertEqual(other_card.status, 'review_required', other_card.reason)
        self.assertEqual(source.read_text(), 'export const speed = 3;\n')
        snapshot = self.service.production.snapshot(result.project_id)
        self.assertTrue(any(step.capability_id == 'code.file.write' and step.module_id == 'world-logic'
                            for step in snapshot.steps))

    async def test_wrong_preimage_even_matching_target_does_not_claim_a_write(self):
        source = self.worktrees / 'card_one' / 'main.ts'
        source.write_text('user content', encoding='utf-8')
        task = self.prepare()
        result = await self.execute(task, [action('conflict', 'code.file.write', path='main.ts',
            expected_content='stale content', content='user content')])
        self.assertEqual(source.read_text(), 'user content')
        self.assertEqual(result.actions[0].effect_state, 'NONE')
        self.assertEqual(result.actions[0].state, 'failed')
        self.assertEqual(self.service.code.rows(task.id), [])
        self.assertFalse(self.service.records.owns_claim(result))

    async def test_paths_links_and_binary_are_rejected(self):
        card = self.worktrees / 'card_one'
        outside = self.root / 'outside.ts'
        outside.write_text('outside', encoding='utf-8')
        (card / 'link.ts').symlink_to(outside)
        os.link(outside, card / 'hard.ts')
        (card / 'linked').symlink_to(self.root, target_is_directory=True)
        (card / 'binary.ts').write_bytes(b'\0binary')
        for path in ('../outside.ts', '.git/config', '.sceneops/brief.json', '.env',
                     'link.ts', 'hard.ts', 'linked/outside.ts', 'binary.ts', 'package-lock.json'):
            with self.subTest(path=path):
                result = await self.execute(self.prepare(), [action('denied', 'code.file.write',
                    path=path, expected_content=None, content='changed')])
                self.assertEqual(result.actions[0].effect_state, 'NONE')
                self.assertFalse(self.service.records.owns_claim(result))
        self.assertEqual(outside.read_text(), 'outside')

    async def test_grant_rechecks_registration_and_project_serialization(self):
        task = self.prepare()
        authorized = self.service.authorize(task.id, AuthorizeAgentTask(
            authorization_card_id=task.authorization_card.id, accept_unknown_cost=True), actions=[])
        other = self.prepare('card_two')
        with self.assertRaises(HarnessError):
            self.service.authorize(other.id, AuthorizeAgentTask(
                authorization_card_id=other.authorization_card.id, accept_unknown_cost=True), actions=[])
        self.workspace.get_card_worktree = lambda project, card: {
            'project_id': project, 'card_id': card, 'branch': 'codex/wrong',
            'worktree_path': authorized.grant.workspace_root}
        with self.assertRaises(HarnessError):
            self.service.check_grant(task.id, 'code.file.write')
        await asyncio.gather(*list(self.service.jobs.values()))

    async def test_written_result_recovery_is_read_only(self):
        task = self.prepare()
        result = await self.execute(task, [action('write', 'code.file.write', path='main.ts',
            expected_content=None, content='export const value = 1;')])
        self.assertEqual(result.status, 'failed')  # No finish was requested.
        self.assertFalse(self.service.records.owns_claim(result))
        entry = result.actions[0]
        effect, evidence = self.service.code.reconcile(result, entry)
        self.assertEqual(effect, 'COMMITTED')
        self.assertTrue(evidence['recovered'])
        (self.worktrees / 'card_one' / 'main.ts').write_text('user changed', encoding='utf-8')
        effect, evidence = self.service.code.reconcile(result, entry)
        self.assertEqual(effect, 'UNKNOWN')
        self.assertIsNone(evidence)
        self.assertEqual((self.worktrees / 'card_one' / 'main.ts').read_text(), 'user changed')
