"""Deterministic conversation memory acceptance; run by the principal agent."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sceneops_ai_distiller import ExperienceService, ExperienceError, MemoryWrite, MemoryUndo
from sceneops_ai_distiller.experience_models import ExperienceSettingsUpdate, utc_now


class ConversationMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.service = ExperienceService(Path(self.directory.name) / 'memory.db', None,
            project_exists=lambda p: p in ('a', 'b'))
        self.source = dict(id='message:user', kind='message', role='user', text='记住：保持横屏',
                           evidence_status='user_statement', created_at=utc_now())
        self.service.set_memory_providers(lambda project, source: self.source if project == 'a' and source == self.source['id'] else None)
        self.service.update_settings(ExperienceSettingsUpdate(learn_enabled=False))

    async def asyncTearDown(self):
        await self.service.close()
        self.directory.cleanup()

    async def remember(self):
        return await self.service.write_memory(MemoryWrite(project_id='a', source_id=self.source['id'],
            origin_key='message:reply', title='方向约束', content='保持横屏', category='constraint'))

    async def test_remember_recall_correct_and_undo_keep_exact_snapshot(self):
        first = await self.remember()
        provided = self.service.context('a', '普通任务', use_key='call:1')
        self.assertEqual(provided['items'][0]['content'], '保持横屏')
        self.assertEqual(self.service.context('b', '普通任务', use_key='call:1')['items'], [])
        corrected = await self.service.write_memory(MemoryWrite(project_id='a', source_id=self.source['id'],
            origin_key='message:reply2', title='方向约束', content='跟随设备旋转', category='constraint',
            entry_id=first.entry_id, expected_revision=1))
        self.assertEqual(self.service.context('a', '', use_key='call:2')['items'][0]['revision'], 2)
        self.assertEqual(self.service.context('a', '', use_key='call:1'), provided)
        restored = await self.service.undo_memory_event(corrected.id, MemoryUndo(project_id='a', expected_revision=2))
        self.assertEqual(restored.after.content, '保持横屏')
        self.assertEqual(restored.after.revision, 3)
        self.assertEqual(len(self.service.memory_activity('a', 'message:reply2').events), 2)

    async def test_ownership_conflicts_candidates_and_disable(self):
        with self.assertRaises(ExperienceError):
            await self.service.write_memory(MemoryWrite(project_id='b', source_id=self.source['id'],
                origin_key='message:reply', title='错误归属', content='不应保存'))
        first = await self.remember()
        with self.assertRaises(ExperienceError):
            await self.service.write_memory(MemoryWrite(project_id='a', source_id=self.source['id'],
                origin_key='message:reply', title='方向', content='竖屏', entry_id=first.entry_id, expected_revision=2))
        events = await self.service.apply_proposals('a', 'message:candidate', [dict(source_id=self.source['id'],
            source_quote='保持横屏', intent='candidate', title='方向', content='也许竖屏', entry_id=first.entry_id, expected_revision=1)], allowed_source_ids=[self.source['id']])
        self.assertEqual(events[0].state, 'pending')
        self.assertEqual(self.service.get_entry(first.entry_id, 'a').revision, 1)
        await self.service.undo_memory_event(first.id, MemoryUndo(project_id='a', expected_revision=1))
        self.assertEqual(self.service.context('a', '', use_key='disabled')['items'], [])
        managed = self.service.project_memory('a').entries
        self.assertEqual(managed[0].id, first.entry_id)
        self.assertFalse(managed[0].enabled)

    async def test_restart_keeps_events_and_explicit_save_with_learning_disabled(self):
        first = await self.remember()
        restarted = ExperienceService(self.service.repo.path, None)
        self.assertEqual(restarted.memory_activity('a', 'message:reply').events[0].id, first.id)
        self.assertEqual(restarted.project_memory('a').entries[0].content, '保持横屏')
        await restarted.close()

    async def test_retry_and_unknown_target_do_not_create_new_memory(self):
        first = await self.remember()
        replay = await self.remember()
        self.assertEqual(first.id, replay.id)
        self.assertEqual(len(self.service.project_memory('a').entries), 1)
        with self.assertRaises(ExperienceError) as raised:
            await self.service.write_memory(MemoryWrite(project_id='a', source_id=self.source['id'],
                origin_key='message:missing', title='不存在', content='内容', entry_id='missing', expected_revision=1))
        self.assertEqual(raised.exception.status_code, 404)

    async def test_current_turn_source_and_combined_context_limits(self):
        failed = await self.service.apply_proposals('a', 'message:new', [dict(source_id=self.source['id'],
            source_quote='保持横屏', title='方向', content='横屏')], allowed_source_ids=['message:other'])
        self.assertEqual(failed[0].state, 'failed')
        self.service.set_memory_providers(lambda p, s: self.source, lambda p: [dict(id=str(i), project_id=p,
            title='决定', content='约束' * 500, category='decision', revision=1, source_ref='message:user') for i in range(20)])
        provided = self.service.record_provided('a', 'bounded', [])
        self.assertLessEqual(len(provided['items']) + len(provided['project_memories']), 8)
        from sceneops_ai_distiller.experience_models import ExperienceUse
        self.assertLessEqual(len(ExperienceUse.model_validate(provided).model_dump_json()), 12000)
        self.assertTrue(provided['truncated'])

    async def test_unavailable_database_does_not_claim_saved_context_or_event(self):
        import sqlite3
        from unittest.mock import patch
        with patch.object(self.service.repo, 'exact_uses', side_effect=sqlite3.OperationalError('fixture unavailable')), \
             patch.object(self.service.repo, 'save_use', side_effect=sqlite3.OperationalError('fixture unavailable')):
            result = self.service.record_provided('a', 'failed-call', [])
        self.assertEqual(result['items'], [])
        self.assertIsNotNone(result['failure_reason'])
        self.assertFalse(result['persisted'])
        with patch.object(self.service.repo, 'connect', side_effect=sqlite3.OperationalError('fixture unavailable')):
            result = await self.service.apply_proposals('a', 'failed-save', [dict(source_id=self.source['id'],
                source_quote='保持横屏', title='方向', content='横屏')], allowed_source_ids=[self.source['id']])
        self.assertEqual(result[0].state, 'failed')
        self.assertFalse(result[0].persisted)

    async def test_expected_owner_error_records_unavailable_without_blocking(self):
        from fastapi import HTTPException
        def unavailable(project):
            raise HTTPException(409, '项目决定暂不可读')
        self.service.set_memory_providers(lambda p, s: self.source, unavailable)
        result = self.service.record_provided('a', 'owner-failed-call', [])
        self.assertIn('项目决定暂不可读', result['failure_reason'])
        self.assertTrue(result['persisted'])
        self.assertEqual(result, self.service.uses('a', 'owner-failed-call', exact=True)[0].model_dump(mode='json'))

    async def test_matched_directory_does_not_fill_unrelated_technical_entries(self):
        self.assertEqual(self.service.ranked_entries('a', '修改这段文案的措辞', matched_only=True), [])
        self.assertTrue(self.service.ranked_entries('a', 'Xcode', matched_only=True))

    async def test_selected_method_and_related_counterexample_share_context_budget(self):
        from sceneops_ai_distiller.experience_models import ExperienceEntry, ExperienceEvidence, ExperienceUse
        evidence = ExperienceEvidence(id='paired-source', summary='测试来源', source_kind='verification', source_ref='paired-source')
        method = ExperienceEntry(id='paired-method', scope='shared', kind='procedure', title='方法', content='方法步骤', evidence=[evidence])
        counter = ExperienceEntry(id='paired-counter', scope='shared', kind='case', title='反证', content='此条件下失败', status='disputed', evidence=[evidence.model_copy(deep=True)])
        fillers = [ExperienceEntry(id=f'filler-{i}', scope='shared', kind='procedure', title=f'独立方法{i}', content='独立内容') for i in range(8)]
        with self.service.repo.connect() as db:
            for entry in [method, counter, *fillers]:
                self.service.repo._write(db, entry, '关联反证夹具')
        # The caller selects only the method; the canonical recorder adds its evidence.
        selected = self.service.record_provided('a', 'pair-first', [method, *fillers])
        ids = [item['id'] for item in selected['items']]
        self.assertEqual(ids[:2], [method.id, counter.id])
        self.assertLessEqual(len(ids), 8)
        # Seven earlier entries leave one slot: the method cannot displace its counterexample.
        limited = self.service.record_provided('a', 'pair-last', [*fillers[:7], method])
        self.assertNotIn(method.id, [item['id'] for item in limited['items']])
        self.assertTrue(limited['truncated'])
        self.assertLessEqual(len(ExperienceUse.model_validate(limited).model_dump_json()), 12000)
        # Oversized non-body evidence also excludes the pair, instead of publishing only the method.
        counter.evidence[0].summary = '证据' * 8000
        counter.revision += 1
        with self.service.repo.connect() as db:
            self.service.repo._write(db, counter, '大体积反证夹具')
        oversized = self.service.record_provided('a', 'pair-oversized', [method])
        self.assertNotIn(method.id, [item['id'] for item in oversized['items']])
        self.assertTrue(oversized['truncated'])
