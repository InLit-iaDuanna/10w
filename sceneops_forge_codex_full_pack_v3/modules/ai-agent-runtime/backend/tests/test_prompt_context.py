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
    read_history_reference,
)
from sceneops_ai_agents.prompting import (
    ASSET_TOOL_GUIDANCE,
    CORE_SYSTEM_INSTRUCTION,
    DIRECTOR_ROLE_INSTRUCTION,
    GAMEPLAY_ENGINEER_SKILL,
    PROTOTYPE_TOOL_GUIDANCE,
)
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
            self.assertIn(GAMEPLAY_ENGINEER_SKILL, instructions)
            self.assertIn("对象/组件或 ECS", instructions)
            self.assertNotIn(ASSET_TOOL_GUIDANCE, provider.call["prompt"])
            self.assertNotIn(PROTOTYPE_TOOL_GUIDANCE, provider.call["prompt"])

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


if __name__ == "__main__":
    import unittest
    unittest.main()
