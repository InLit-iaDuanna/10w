"""Isolated application acceptance; no external model, project build or tool runs."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from conversation_home import AIRepository
from sceneops_ai_distiller.experience_models import ExperienceSettingsUpdate
from services.api.app import create_app


class ConversationMemoryHttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {'SCENEOPS_DATA_DIR': self.directory.name,
                                                  'SCENEOPS_LOCAL_TOKEN': 'memory-http-test'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.app = create_app()
        self.app.state.experience.update_settings(ExperienceSettingsUpdate(learn_enabled=False))
        self.client = TestClient(self.app, base_url='http://127.0.0.1', headers={
            'x-sceneops-token': 'memory-http-test', 'origin': 'http://127.0.0.1:4300'})
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.repository = self.app.state.workspace_repository
        self.project = self.repository.create_project('隔离记忆验收')
        self.other = self.repository.create_project('另一个隔离项目')
        self.messages = AIRepository(Path(self.directory.name) / 'sceneops.sqlite3')
        self.messages.append_exchange(self.project.project_id, '请记住：使用横屏', '收到约束', 'fixture',
                                      message_ids=('user-source', 'assistant-source'))

    def remember(self):
        result = self.client.post('/api/experience/memories', json={
            'project_id': self.project.project_id, 'origin_key': 'message:user-source',
            'source_id': 'message:user-source', 'title': '方向约束', 'content': '使用横屏',
            'category': 'constraint', 'request_id': 'remember-once'})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_save_correct_next_request_and_undo_through_real_api(self):
        first = self.remember()
        self.assertEqual(self.remember()['id'], first['id'])
        memory = self.client.get('/api/experience/project-memory', params={'project_id': self.project.project_id})
        self.assertEqual(memory.status_code, 200, memory.text)
        self.assertEqual(len(memory.json()['entries']), 1)
        old = self.app.state.experience.context(self.project.project_id, '继续', use_key='task:qa:call:one')
        correction = self.client.post('/api/experience/memories', json={
            'project_id': self.project.project_id, 'origin_key': 'message:user-source',
            'source_id': 'message:user-source', 'title': '方向约束', 'content': '跟随设备方向',
            'category': 'constraint', 'entry_id': first['entry_id'], 'expected_revision': 1,
            'request_id': 'correct-once'})
        self.assertEqual(correction.status_code, 200, correction.text)
        new = self.app.state.experience.context(self.project.project_id, '继续', use_key='task:qa:call:two')
        self.assertEqual(new['items'][0]['content'], '跟随设备方向')
        self.assertEqual(old['items'][0]['content'], '使用横屏')
        undo = self.client.post('/api/experience/events/' + correction.json()['id'] + '/undo',
            json={'project_id': self.project.project_id, 'expected_revision': 2})
        self.assertEqual(undo.status_code, 200, undo.text)
        self.assertEqual(undo.json()['after']['revision'], 3)
        self.assertEqual(undo.json()['after']['content'], '使用横屏')
        activity = self.client.get('/api/experience/activity', params={
            'project_id': self.project.project_id, 'origin_key': 'message:user-source'})
        self.assertEqual(len(activity.json()['events']), 3)
        self.assertFalse(self.app.state.experience.settings().learn_enabled)

    def test_source_scope_and_revision_conflict_do_not_write(self):
        event = self.remember()
        body = {'project_id': self.other.project_id, 'origin_key': 'message:user-source',
                'source_id': 'message:user-source', 'title': '错误来源', 'content': '不可保存'}
        result = self.client.post('/api/experience/memories', json=body)
        self.assertEqual(result.status_code, 404, result.text)
        body.update(project_id=self.project.project_id, entry_id=event['entry_id'], expected_revision=8)
        result = self.client.post('/api/experience/memories', json=body)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(self.app.state.experience.get_entry(event['entry_id'], self.project.project_id).revision, 1)
        self.assertEqual(self.app.state.experience.project_memory(self.other.project_id).entries, [])

    def test_project_direction_correction_updates_owning_state_and_undo(self):
        folder = self.repository.create_folder_project(Path(self.directory.name).resolve(), 'direction-project')
        self.messages.append_exchange(folder.project_id, '把初版范围纠正为一个关卡', '待更新', 'fixture',
                                      message_ids=('direction-user', 'direction-assistant'))
        confirmed = self.client.post(f'/api/design/journeys/{folder.project_id}/command', json={
            'request_id': 'initial-direction', 'expected_revision': 0, 'operation': 'confirm_demo_direction',
            'core_experience': '收集物品', 'perspective_style': '俯视简洁风格',
            'simplified_scope': '两个关卡', 'code_architecture': 'object-component'})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        revision = confirmed.json()['revision']
        changed = self.client.post('/api/experience/memories', json={
            'project_id': folder.project_id, 'source_id': 'message:direction-user',
            'origin_key': 'message:direction-user', 'reference_id': 'journey:direction:simplified_scope',
            'expected_revision': revision, 'title': '初版范围', 'content': '一个关卡', 'category': 'constraint'})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(self.app.state.planning_journey.get(folder.project_id).initial_demo_direction.simplified_scope, '一个关卡')
        self.assertEqual(self.app.state.experience.project_memory(folder.project_id).entries, [])
        undone = self.client.post('/api/experience/events/' + changed.json()['id'] + '/undo', json={
            'project_id': folder.project_id, 'expected_revision': changed.json()['reference']['revision']})
        self.assertEqual(undone.status_code, 200, undone.text)
        self.assertEqual(self.app.state.planning_journey.get(folder.project_id).initial_demo_direction.simplified_scope, '两个关卡')
