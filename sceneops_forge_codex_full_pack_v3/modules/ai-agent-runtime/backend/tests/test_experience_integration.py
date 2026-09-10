"""Injected experience integration; no external providers or tools are invoked."""
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from conversation_home.unified_router import create_ai_router
from sceneops_design_ai.journey import PlanningJourneyService
from sceneops_design_ai.journey_models import PlanningJourney
from sceneops_ai_agents.task_service import AgentTaskService
from sceneops_ai_agents.task_loop import choose
from sceneops_ai_agents.task_tools import TaskTools


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def memory():
    return NS(context=Mock(return_value={"use_id": "use_fixture", "items": [{"text": "经验参考"}],
        "notice": None, "truncated": False}), record_sources=Mock(),
        memory_instructions=Mock(return_value='记忆提案仅限当前用户消息。'))


@pytest.mark.parametrize("notice", [None, "经验读取暂不可用，普通对话继续。"])
def test_chat_saves_original_messages_and_associates_use(tmp_path, memory, notice):
    memory.context.return_value["notice"] = notice
    provider = Mock()
    provider.generate = AsyncMock(return_value=NS(text="实际回复", model="fixture", provider="codexcli"))
    with patch("conversation_home.unified_router.ProviderService", return_value=provider):
        app = FastAPI()
        app.include_router(create_ai_router(tmp_path / "db.sqlite", experience=memory))
        with TestClient(app) as client:
            response = client.post("/api/ai/chat", json={"message": "原始问题"})
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert memory.context.call_args.kwargs["use_key"] == "message:" + messages[-1]["id"]
    assert json.loads(provider.generate.call_args.args[0])["experience_context"]["use_id"] == "use_fixture"
    assert [source["text"] for source in memory.record_sources.call_args.args[1]] == ["原始问题", "实际回复"]


@pytest.mark.anyio
async def test_journey_records_exact_bounded_basis(tmp_path, memory):
    provider = Mock()
    provider.settings.return_value = NS(provider="codexcli", model="fixture")
    provider.generate = AsyncMock(return_value=NS(text="回复"))
    service = PlanningJourneyService(tmp_path / "db.sqlite", Mock(), provider, experience=memory)
    state = PlanningJourney(project_id="project_fixture", root_path=str(tmp_path))
    await service.generate(state, "策划问题", context={"card": "制作卡片"})
    await service.generate(state, "策划问题", context={"card": "制作卡片"})
    assert memory.context.call_count == 2
    assert "memory_context" in provider.generate.call_args.args[0]
    assert memory.record_sources.call_count == 0  # Unpersisted generation is not a source.


@pytest.mark.anyio
async def test_typed_choose_uses_prepared_context_without_changing_authority(memory):
    task = NS(id="task_fixture", project_id="project_fixture", goal="目标", provider_id="codexcli",
        provider_model="fixture", model_calls_used=1,
        observations={"production_preparation_context": {"status": "succeeded", "selected_details": []}})
    service = NS(check_grant=Mock(return_value=task), provider=Mock(), records=Mock(),
        runtimes={"task_fixture": Mock()}, authority=Mock(return_value="existing-authority"),
        experience_context=Mock(return_value={"items": []}),
        preparation_without_memory=AgentTaskService.preparation_without_memory)
    service.provider.settings.return_value = NS(provider="codexcli", model="fixture")
    service.records.update.return_value = task
    service.model_image_input = Mock(return_value={"status": "unavailable"})
    runtime = service.runtimes[task.id]
    runtime.submit.side_effect = RuntimeError("captured")
    with patch("sceneops_ai_agents.task_loop.next_action_inputs", return_value={"context_summary": {}}), patch(
            "sceneops_ai_agents.task_loop.definition", side_effect=lambda task, step: step):
        with pytest.raises(RuntimeError, match="captured"):
            await choose(service, task.id)
    step = runtime.submit.call_args.args[0]
    assert "experience_context" not in step.inputs["context_summary"]
    assert runtime.submit.call_args.args[1] == "existing-authority"


@pytest.mark.anyio
async def test_native_execute_receives_prepared_data_with_original_scope(tmp_path, memory):
    task = NS(id="task_fixture", project_id="project_fixture", goal="原始目标", provider_id="codexcli",
        provider_model="fixture", observations={"production_preparation_context": {
            "status": "succeeded", "selected_details": [{"content": "准备内容"}]}},
        authorization_card=NS(task_profile="card-development", scope="原授权"),
        grant=NS(execution_mode="agent-full-access", workspace_root=str(tmp_path), card_id="card", branch="branch",
            include_demo_assets=False, expires_at=None, allow_image_generation=False))
    service = NS(check_grant=Mock(return_value=task), card_workspace=Mock(), provider=Mock(), records=Mock(),
        experience_context=Mock(return_value={"items": []}),
        preparation_without_memory=AgentTaskService.preparation_without_memory)
    service.provider.execute_task = AsyncMock(side_effect=RuntimeError("captured"))
    tools = object.__new__(TaskTools)
    tools.service, tools.task_id = service, task.id
    invocation = NS(capability_id="agent.task.execute", inputs={"goal": task.goal}, dry_run=False, run_id="run_fixture")
    with pytest.raises(RuntimeError, match="captured"):
        await tools.dispatch(invocation, Mock())
    call = service.provider.execute_task.call_args
    assert "本次制作准备" in call.args[0]
    assert "准备内容" in call.args[0]
    assert "experience_context" not in call.args[0]
    assert call.kwargs["authorized_scope"] == "原授权"
    assert memory.context.call_count == 0


def test_settled_unknown_action_never_becomes_verified(memory):
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc)
    verification = NS(execution_status="COMPLETED", verdict="PASS", model_dump_json=lambda: '{"verdict":"PASS"}')
    entry = NS(action=NS(action_id="action_fixture", capability_id="agent.task.execute"),
        state="uncertain", effect_state="UNKNOWN", reason="连接中断", result={"reported": "完成"},
        run_ids=["run_fixture"], verification_result=verification)
    task = NS(id="task_fixture", project_id="project_fixture", goal="目标", created_at=stamp,
        updated_at=stamp, status="failed", reason="连接中断", actions=[entry], observations={})
    service = object.__new__(AgentTaskService)
    service.experience = memory
    service.get = Mock(return_value=task)
    service.events = Mock(side_effect=[NS(events=[NS(event_type="agent.action.observed",
        payload={"action_id":"action_fixture"}, occurred_at=stamp)], next_cursor=1), NS(events=[], next_cursor=1)])
    service.record_experience(task.id)
    sources = memory.record_sources.call_args.args[1]
    assert sources[1]["evidence_status"] == sources[2]["evidence_status"] == "unknown"
    assert "task-action://action_fixture/result" in sources[1]["text"]
    assert '"status": "failed"' in sources[-1]["text"]


@pytest.mark.parametrize("scope", ["main", "card", "modeling", "context"])
def test_journey_query_uses_current_user_message(tmp_path, scope):
    from sceneops_design_ai.journey_models import JourneyMessage, CardModelingSession, CardConversation
    state = PlanningJourney(project_id="project_fixture", root_path=str(tmp_path))
    old = JourneyMessage(id="old", role="user", text="普通方向", created_at="2026-09-08T00:00:00+00:00")
    current = JourneyMessage(id="current", role="user", text="用 gyro 控制角色", created_at="2026-09-08T00:01:00+00:00")
    state.messages = [old]
    context = None
    if scope == "main":
        state.messages.append(current)
    elif scope == "card":
        state.active_card_id = "card"
        state.active_conversation_ids = {"card": "conversation"}
        state.card_conversations = {"card": [CardConversation(id="conversation", title="制作", messages=[current])]}
    elif scope == "modeling":
        state.active_modeling_id = "modeling"
        state.modeling_sessions = [CardModelingSession(id="modeling", card_id="card", source="create", stage="brief", messages=[current])]
    else:
        context = {"messages": [current.model_dump(mode="json")]}
    query = PlanningJourneyService.experience_query(state, "生成结构化策划", context)
    assert query.startswith("用 gyro 控制角色")
    assert "普通方向" not in query


def test_each_request_refreshes_selected_revision_and_keeps_prior_snapshot():
    service = object.__new__(AgentTaskService)
    service.experience = NS(get_entry=Mock(), record_provided=Mock(side_effect=lambda *args, **kwargs: args[2]))
    task = NS(id="task_fixture", project_id="project_fixture", goal="镜头", observations={
        "production_preparation_context": {"selected_details": [{"identity": {"kind": "experience"},
            "status": "provided", "content": {"id": "camera", "revision": 1}}]}})
    service.experience.get_entry.return_value = NS(enabled=True, status="supported",
        model_dump=lambda **kwargs: {"id": "camera", "revision": 2})
    first = service.experience_context(task, call_key="typed:1")
    service.experience.get_entry.return_value = NS(enabled=False, status="supported")
    second = service.experience_context(task, call_key="typed:2")
    assert first == [{"id": "camera", "revision": 2}]
    assert second == []
    assert task.observations["production_preparation_context"]["selected_details"][0]["content"]["revision"] == 1
    assert service.experience.record_provided.call_args.args[1] == "task:task_fixture:call:typed:2"
