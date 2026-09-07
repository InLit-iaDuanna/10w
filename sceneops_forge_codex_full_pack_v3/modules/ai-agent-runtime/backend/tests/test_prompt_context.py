"""Deterministic prompt assembly and task-context projection regressions."""
import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase

from sceneops_ai_agents import AgentRuntime
from sceneops_ai_agents.context_projection import (
    action_input_reference,
    action_result_reference,
    project_action_history,
    project_observations,
    read_history_reference,
    task_context_summary,
)
from sceneops_ai_agents.prompting import (
    ASSET_TOOL_GUIDANCE,
    CORE_SYSTEM_INSTRUCTION,
    DIRECTOR_ROLE_INSTRUCTION,
    PROTOTYPE_TOOL_GUIDANCE,
)
from sceneops_ai_agents.task_loop import next_action_inputs
from sceneops_ai_agents.task_models import (
    ActionRecord,
    AgentAction,
    AgentTaskRecord,
    AuthorizationCard,
    NextActionInput,
    TaskGrant,
    now,
)
from sceneops_ai_agents.task_tools import TaskTools
from sceneops_harness import HarnessError


class CancellationFixture:
    def raise_if_cancelled(self):
        return None


class CaptureProvider:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.call = None

    def settings(self):
        return SimpleNamespace(provider="fixture", model="fixture-model")

    async def generate(self, prompt, **kwargs):
        self.call = {"prompt": prompt, **kwargs}
        action = {"action_id": "inspect", "capability_id": "code.workspace.inspect",
                  "rationale": "Inspect current workspace", "inputs": {}}
        return SimpleNamespace(structured=action, text=json.dumps(action), provider="fixture",
                               model="fixture-model", latency_ms=1, usage=None)


def next_action_input(capabilities):
    return NextActionInput(goal="Add sprint cooldown", context_summary={}, observations={}, history=[],
        capabilities=[{"id": capability} for capability in capabilities],
        expected_provider="fixture", expected_model="fixture-model", input_schemas={})


class PromptAssemblyTests(IsolatedAsyncioTestCase):
    async def test_runtime_loads_core_role_and_only_the_relevant_code_skill(self):
        with TemporaryDirectory() as directory:
            provider = CaptureProvider(Path(directory) / "state.sqlite3")
            runtime = AgentRuntime(provider)
            data = next_action_input(["code.workspace.inspect", "code.file.read", "code.file.write"])
            invocation = SimpleNamespace(inputs=data.model_dump(mode="json"), id="invocation_fixture")

            await runtime.next_action(invocation, CancellationFixture())

            instructions = provider.call["instructions"]
            self.assertEqual(provider.call["purpose"], "agent-action")
            self.assertIn(CORE_SYSTEM_INSTRUCTION, instructions)
            self.assertIn(DIRECTOR_ROLE_INSTRUCTION, instructions)
            from importlib.resources import files
            skill = files("sceneops_ai_agents").joinpath(
                "skills/sceneops-threejs-gameplay/SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(instructions.count(skill), 1)
            self.assertIn("对象/组件或 ECS", instructions)
            self.assertNotIn(ASSET_TOOL_GUIDANCE, provider.call["prompt"])
            self.assertNotIn(PROTOTYPE_TOOL_GUIDANCE, provider.call["prompt"])

    async def test_complete_request_compacts_superseded_results_but_keeps_current_read(self):
        with TemporaryDirectory() as directory:
            provider = CaptureProvider(Path(directory) / "state.sqlite3")
            agent_runtime = AgentRuntime(provider)
            old_body = "old history\n" * 4096
            current_body = "export const current = true;\n" * 256
            actions = [
                ActionRecord(action=AgentAction(action_id="history_old",
                    capability_id="agent.history.read", rationale="Read old body",
                    inputs={"reference": "task-action://source/result"}), state="succeeded",
                    result={"evidence": {"tool": "history", "mode": "live",
                        "reference": "task-action://source/result", "value": old_body}}),
                ActionRecord(action=AgentAction(action_id="read_current",
                    capability_id="code.file.read", rationale="Read current file",
                    inputs={"path": "src/current.ts"}), state="succeeded",
                    result={"evidence": {"tool": "code", "mode": "live",
                        "path": "src/current.ts", "content": current_body}}),
            ]
            capabilities = ["code.workspace.inspect", "code.file.read", "code.file.write",
                            "agent.history.read", "agent.finish"]
            card = AuthorizationCard(workspace_root="/fixture", task_profile="card-development",
                card_id="card_fixture", capability_ids=capabilities)
            task = AgentTaskRecord(project_id="prj_fixture", goal="Continue exact edit",
                authorization_card=card, actions=actions, provider_id="fixture",
                provider_model="fixture-model", observations={
                    "history": actions[0].result["evidence"],
                    "code": actions[1].result["evidence"],
                })
            task.grant = TaskGrant(task_id=task.id, project_id=task.project_id,
                workspace_root="/fixture", card_id="card_fixture", capability_ids=capabilities,
                expires_at=now() + timedelta(minutes=5))
            service = SimpleNamespace(get=lambda task_id: task, agents=agent_runtime)
            tools = TaskTools(service, task.id)
            data = NextActionInput.model_validate(next_action_inputs(
                task, SimpleNamespace(registry=tools.registry())))
            invocation = SimpleNamespace(inputs=data.model_dump(mode="json"), id="request_capture")

            await agent_runtime.next_action(invocation, CancellationFixture())

            payload = json.loads(provider.call["prompt"].split("本轮运行时输入：\n", 1)[1])
            encoded = json.dumps(payload, ensure_ascii=False)
            self.assertEqual(payload["observations"]["code"]["content"], current_body)
            self.assertEqual(payload["observations"]["history"]["result_reference"],
                             action_result_reference("history_old"))
            self.assertNotIn(old_body, encoded)
            self.assertIn("agent.history.read", {item["id"] for item in payload["capabilities"]})
            self.assertNotIn("environment.object.transform", payload["input_schemas"])
            self.assertIn("agent.history.read", payload["input_schemas"])
            self.assertIn("SceneOps 游戏制作助手", provider.call["instructions"])

    async def test_code_guidance_does_not_request_an_unavailable_history_tool(self):
        with TemporaryDirectory() as directory:
            provider = CaptureProvider(Path(directory) / "state.sqlite3")
            runtime = AgentRuntime(provider)
            data = next_action_input(["code.workspace.inspect", "code.file.read", "code.file.write"])
            invocation = SimpleNamespace(inputs=data.model_dump(mode="json"), id="legacy_prompt")

            await runtime.next_action(invocation, CancellationFixture())

            self.assertNotIn("agent.history.read", provider.call["prompt"])

    async def test_history_capability_reads_the_current_task_record(self):
        entry = ActionRecord(action=AgentAction(action_id="read_a", capability_id="code.file.read",
            rationale="Read dependency", inputs={"path": "src/a.ts"}), state="succeeded",
            result={"evidence": {"content": "export const a = 1;"}})
        card = AuthorizationCard(workspace_root="/fixture", capability_ids=["agent.history.read"])
        task = AgentTaskRecord(project_id="prj_fixture", goal="Continue", authorization_card=card,
                               actions=[entry])
        service = SimpleNamespace(check_grant=lambda task_id, capability_id: task)
        invocation = SimpleNamespace(id="history_invocation", capability_id="agent.history.read", dry_run=False,
            inputs={"reference": action_result_reference("read_a")})

        result = await TaskTools(service, task.id).dispatch(invocation, CancellationFixture())

        self.assertEqual(result.outputs["evidence"]["value"]["evidence"]["content"],
                         "export const a = 1;")


class ContextProjectionTests(TestCase):
    def task(self, actions):
        card = AuthorizationCard(workspace_root="/fixture", task_profile="card-development",
                                 card_id="card_fixture", capability_ids=["agent.history.read"])
        task = AgentTaskRecord(project_id="prj_fixture", goal="Continue code work",
                               authorization_card=card, actions=actions)
        task.grant = TaskGrant(task_id=task.id, project_id=task.project_id,
            workspace_root="/fixture", card_id="card_fixture",
            capability_ids=["agent.history.read"], expires_at=now() + timedelta(minutes=5))
        return task

    def test_large_write_history_keeps_exact_records_but_not_repeated_bodies(self):
        body = "x" * 8192
        actions = [ActionRecord(action=AgentAction(action_id=f"write_{index}",
            capability_id="code.file.write", rationale="Update source",
            inputs={"path": f"src/file-{index}.ts", "expected_content": body,
                    "content": body + str(index)}), state="succeeded", effect_state="COMMITTED",
            result={"evidence": {"tool": "code", "content": body + str(index),
                                 "log": "checked " + body}}) for index in range(8)]
        task = self.task(actions)

        projection = project_action_history(task.actions)
        encoded = json.dumps(projection)

        self.assertLess(len(encoded), 20000)
        self.assertNotIn(body, encoded)
        self.assertEqual(task.actions[0].action.inputs["expected_content"], body)
        self.assertEqual(read_history_reference(task,
            action_input_reference("write_0", "content")), body + "0")
        self.assertEqual(read_history_reference(task,
            action_result_reference("write_7"))["evidence"]["content"], body + "7")

    def test_two_file_reads_remain_retrievable_by_distinct_result_references(self):
        actions = [ActionRecord(action=AgentAction(action_id=action_id,
            capability_id="code.file.read", rationale="Read dependency",
            inputs={"path": path}), state="succeeded",
            result={"evidence": {"tool": "code", "path": path, "content": content}})
            for action_id, path, content in (("read_a", "src/a.ts", "export type A = string;"),
                                             ("read_b", "src/b.ts", "import type { A } from './a';"))]
        task = self.task(actions)
        projection = project_action_history(task.actions)

        self.assertEqual([item["result_reference"] for item in projection],
                         [action_result_reference("read_a"), action_result_reference("read_b")])
        self.assertEqual(read_history_reference(task, action_result_reference("read_a"))
                         ["evidence"]["content"], "export type A = string;")

    def test_history_reference_cannot_escape_the_current_task_record(self):
        task = self.task([])
        with self.assertRaises(HarnessError) as caught:
            read_history_reference(task, "task-action://missing/result")
        self.assertEqual(caught.exception.code, "HISTORY_REFERENCE_NOT_FOUND")

    def test_legacy_authorization_keeps_exact_history_inline_without_unreadable_refs(self):
        body = "legacy exact body\n" * 512
        action = ActionRecord(action=AgentAction(action_id="legacy_write",
            capability_id="code.file.write", rationale="Historical write",
            inputs={"path": "src/legacy.ts", "expected_content": body,
                    "content": body + "next"}), state="succeeded", effect_state="COMMITTED",
            result={"evidence": {"tool": "code", "content": body + "next"}})
        task = self.task([action])
        task.authorization_card.capability_ids = ["code.file.read", "code.file.write"]
        task.grant.capability_ids = list(task.authorization_card.capability_ids)

        projection = project_action_history(task.actions, can_read_history=False)
        summary = task_context_summary(task, can_read_history=False)

        self.assertEqual(projection[0]["action"]["inputs"]["expected_content"], body)
        self.assertEqual(projection[0]["result"]["evidence"]["content"], body + "next")
        self.assertNotIn("result_reference", projection[0])
        self.assertIn("内联兼容模式", summary["history_policy"])

    def test_summary_names_historical_failure_without_calling_it_unresolved(self):
        failed = ActionRecord(action=AgentAction(action_id="write_old",
            capability_id="code.file.write", rationale="Old failed write", inputs={}),
            state="failed", reason="fixture failure")
        succeeded = ActionRecord(action=AgentAction(action_id="write_new",
            capability_id="code.file.write", rationale="New successful write", inputs={}),
            state="succeeded", effect_state="COMMITTED")
        task = self.task([failed, succeeded])

        summary = task_context_summary(task)

        self.assertEqual(summary["latest_action"]["action_id"], "write_new")
        self.assertEqual(summary["latest_non_success_action"]["action_id"], "write_old")
        self.assertIsNone(summary["current_issue"])
        self.assertNotIn("unresolved_action", summary)

    def test_latest_exact_history_read_is_retained_until_another_action_supersedes_it(self):
        body = "current exact history\n" * 2048
        entry = ActionRecord(action=AgentAction(action_id="history_current",
            capability_id="agent.history.read", rationale="Read exact history",
            inputs={"reference": "task-action://source/result"}), state="succeeded",
            result={"evidence": {"tool": "history", "value": body}})
        task = self.task([entry])
        task.observations["history"] = entry.result["evidence"]

        observations = project_observations(task, can_read_history=True)

        self.assertEqual(observations["history"]["value"], body)


if __name__ == "__main__":
    import unittest
    unittest.main()
