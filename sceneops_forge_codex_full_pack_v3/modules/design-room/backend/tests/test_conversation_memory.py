"""Persisted conversation identities and immediate, source-bound memory updates."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sceneops_ai_distiller import ExperienceService
from sceneops_project_workspace import SqliteWorkspaceRepository
from sceneops_design_ai import PlanningJourneyService
from sceneops_design_ai.journey_models import JourneyCommand


@pytest.fixture
def anyio_backend():
    return 'asyncio'


class Provider:
    def settings(self):
        return SimpleNamespace(provider='fixture', model='fixture')

    async def generate(self, prompt, **kwargs):
        self.prompt = prompt
        source_id = prompt.split('本轮用户来源：')[-1]
        payload = {'text': '记录这条约束。', 'memory_updates': [{
            'source_id': source_id, 'source_quote': '记住：只能横屏',
            'title': '屏幕方向', 'content': '只能横屏', 'category': 'constraint'}]}
        return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False), provider='fixture', model='fixture')


@pytest.mark.anyio
async def test_saved_reply_has_exact_basis_and_correction_source(tmp_path):
    folders = SqliteWorkspaceRepository(tmp_path / 'state.sqlite')
    project = folders.create_folder_project(tmp_path, 'sample')
    provider = Provider()
    experience = ExperienceService(tmp_path / 'state.sqlite', provider, lambda _: True)
    settings = experience.settings()
    experience.update_settings(settings.model_copy(update={'learn_enabled': False}))
    service = PlanningJourneyService(tmp_path / 'state.sqlite', folders, provider, experience=experience)
    experience.set_memory_providers(service.memory_source, service.project_memory, service.update_project_memory)
    state = await service.command(project.project_id, JourneyCommand(
        request_id='remember-direction', expected_revision=0, operation='message', text='记住：只能横屏'))
    user, assistant = state.messages[-2:]
    key = f'journey:{project.project_id}:message:{assistant.id}'
    assert experience.repo.exact_uses(project.project_id, key)[0].use_key == key
    activity = experience.memory_activity(project.project_id, f'journey:{project.project_id}:message:{user.id}')
    assert activity.events[0].after.content == '只能横屏'
    assert service.memory_source(project.project_id, f'journey:another:message:{user.id}') is None
    assert 'memory_updates' not in assistant.text
    assert experience.project_memory(project.project_id).entries[0].content == '只能横屏'


@pytest.mark.anyio
async def test_foreground_proposal_cannot_reuse_another_user_source(tmp_path):
    folders = SqliteWorkspaceRepository(tmp_path / 'state.sqlite')
    project = folders.create_folder_project(tmp_path, 'sample')
    provider = Provider()
    original = provider.generate
    async def wrong_source(prompt, **kwargs):
        result = await original(prompt, **kwargs)
        payload = json.loads(result.text)
        payload['memory_updates'][0]['source_id'] = 'journey:another:message:user'
        result.text = json.dumps(payload)
        return result
    provider.generate = wrong_source
    experience = ExperienceService(tmp_path / 'state.sqlite', provider, lambda _: True)
    experience.update_settings(experience.settings().model_copy(update={'learn_enabled': False}))
    service = PlanningJourneyService(tmp_path / 'state.sqlite', folders, provider, experience=experience)
    experience.set_memory_providers(service.memory_source, service.project_memory, service.update_project_memory)
    await service.command(project.project_id, JourneyCommand(
        request_id='source-check', expected_revision=0, operation='message', text='记住：只能横屏'))
    assert experience.project_memory(project.project_id).entries == []


@pytest.mark.anyio
async def test_invalid_optional_memory_does_not_retry_valid_reply(tmp_path):
    folders = SqliteWorkspaceRepository(tmp_path / 'state.sqlite')
    project = folders.create_folder_project(tmp_path, 'sample')
    provider = Provider()
    calls = []
    async def malformed_memory(prompt, **kwargs):
        calls.append(prompt)
        return SimpleNamespace(text=json.dumps({'text': '这是有效回复', 'memory_updates': [{'bad': True}]}),
                               provider='fixture', model='fixture')
    provider.generate = malformed_memory
    experience = ExperienceService(tmp_path / 'state.sqlite', provider, lambda _: True)
    experience.update_settings(experience.settings().model_copy(update={'learn_enabled': False}))
    service = PlanningJourneyService(tmp_path / 'state.sqlite', folders, provider, experience=experience)
    experience.set_memory_providers(service.memory_source, service.project_memory, service.update_project_memory)
    state = await service.command(project.project_id, JourneyCommand(
        request_id='invalid-memory', expected_revision=0, operation='message', text='记住：只能横屏'))
    assert state.messages[-1].text == '这是有效回复'
    assert len(calls) == 1
    origin = f'journey:{project.project_id}:message:{state.messages[-2].id}'
    assert experience.memory_activity(project.project_id, origin).events[0].state == 'failed'
