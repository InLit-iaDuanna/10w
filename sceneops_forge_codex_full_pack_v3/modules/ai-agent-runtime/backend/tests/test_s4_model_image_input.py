"""S4b authorized screenshot-to-model wiring; no external model is invoked."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from datetime import timedelta

from pydantic import ValidationError

from sceneops_ai_agents import AgentRuntime
from sceneops_ai_agents.production_models import ProductionStep
from sceneops_ai_agents.production_store import ProductionStore
from sceneops_ai_agents.task_models import (AgentTaskRecord, AuthorizationCard, NextActionInput,
                                             PrepareAgentTask, TaskGrant, now)
from sceneops_ai_agents.task_repository import AgentTaskRepository
from sceneops_harness import HarnessError


class CaptureProvider:
    def __init__(self, database_path):
        self.database_path = database_path
        self.call = None

    def settings(self):
        return SimpleNamespace(provider="codexcli", model="vision-fixture")

    async def generate(self, prompt, **kwargs):
        self.call = {"prompt": prompt, **kwargs}
        action = {"action_id": "read_source", "capability_id": "code.file.read",
                  "rationale": "Read the production implementation", "inputs": {"path": "src/game.ts"}}
        return SimpleNamespace(structured=action, text=json.dumps(action), provider="codexcli",
                               model="vision-fixture", latency_ms=1, usage={"total_tokens": 7})


class ModelImageRuntimeTests(IsolatedAsyncioTestCase):
    async def test_registered_image_path_is_passed_as_bytes_transport_and_audited(self):
        with TemporaryDirectory() as directory:
            image = Path(directory) / "immutable-screenshot.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            provider = CaptureProvider(Path(directory) / "state.sqlite3")
            runtime = AgentRuntime(provider)
            metadata = {"status": "ready", "provider": "codexcli", "model": "vision-fixture",
                        "task_id": "task_fixture", "project_id": "project_fixture",
                        "artifact_id": "artifact_fixture", "version": 2,
                        "browser_run_id": "browser_run_fixture", "build_run_id": "build_fixture",
                        "check": "movement-collection", "visual_reviewed": False}
            received = []
            runtime.image_resolver = lambda value: received.append(value) or image
            data = NextActionInput(goal="Fix repeat scoring", context_summary={}, observations={}, history=[],
                capabilities=[{"id": "code.file.read"}], expected_provider="codexcli",
                expected_model="vision-fixture", model_image_input=metadata)

            result = await runtime.next_action(SimpleNamespace(id="invocation_fixture",
                inputs=data.model_dump(mode="json")), SimpleNamespace(raise_if_cancelled=lambda: None))

            self.assertEqual(received, [metadata])
            self.assertEqual(provider.call["images"], [image])
            self.assertNotIn(str(image), provider.call["prompt"])
            self.assertIn("model-image://artifact_fixture/versions/2", result.evidence_refs)
            self.assertIn("model_image_input", result.evidence_types)


class ModelImageAuthorizationTests(TestCase):
    def test_image_input_requires_browser_capture_scope(self):
        with self.assertRaises(ValidationError):
            PrepareAgentTask(project_id="project_fixture", card_id="card_fixture",
                task_profile="card-development", goal="Fix a bug", allow_game_execution=True,
                allow_model_image_input=True)

    def test_image_input_can_be_explicitly_authorized_with_interaction(self):
        request = PrepareAgentTask(project_id="project_fixture", card_id="card_fixture",
            task_profile="card-development", goal="Fix a bug", allow_game_execution=True,
            allow_browser_interaction=True, allow_model_image_input=True)

        self.assertTrue(request.allow_model_image_input)

    def test_native_project_image_input_preserves_typed_mode_restriction(self):
        body = dict(project_id='project_fixture', goal='Review screenshot',
            task_profile='project-demo-agent', execution_mode='agent-full-access',
            native_production=True, allow_game_execution=True, include_demo_assets=True,
            alignment_id='direction_0123456789abcdef0123456789abcdef', allow_browser_observation=True, allow_model_image_input=True)
        self.assertTrue(PrepareAgentTask(**body).allow_model_image_input)
        body.update(native_production=False, execution_mode='typed-tools')
        with self.assertRaises(ValidationError):
            PrepareAgentTask(**body)

    def test_artifact_resolver_accepts_only_the_exact_task_browser_run(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            records = AgentTaskRepository(root / "state.sqlite3")
            card = AuthorizationCard(workspace_root=str(root / "worktree"),
                task_profile="card-development", card_id="card_fixture",
                allow_game_execution=True, allow_browser_interaction=True,
                allow_model_image_input=True, capability_ids=["agent.next_action"])
            task = AgentTaskRecord(project_id="project_fixture", goal="Fix behavior",
                                   authorization_card=card)
            task.grant = TaskGrant(task_id=task.id, project_id=task.project_id,
                workspace_root=card.workspace_root, card_id=card.card_id,
                allow_game_execution=True, allow_browser_interaction=True,
                allow_model_image_input=True, capability_ids=card.capability_ids,
                expires_at=now() + timedelta(minutes=5))
            records.create(task)
            store = ProductionStore(root / "state.sqlite3", root, records)
            run_id = "browser_run_fixture"
            step_id = f"{task.id}:{run_id}"
            store.upsert_step(ProductionStep(id=step_id, project_id=task.project_id,
                task_id=task.id, module_id="ai-playtest", title="Current screenshot",
                capability_id="code.browser.interact", state="completed", mode="live",
                run_id=run_id, effect_state="NONE", updated_at=now().isoformat()))
            screenshot = root / "game-runtime" / "observations" / task.id / run_id / "current-view.png"
            screenshot.parent.mkdir(parents=True)
            screenshot.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            artifact = store.record_observation_artifact(task, step_id, run_id, screenshot)

            resolved = store.model_image_path(task, artifact.id, artifact.version, run_id)

            self.assertEqual(resolved, root / "production-artifacts" / artifact.id / f"{artifact.version}.png")

            import base64
            from unittest.mock import Mock
            from sceneops_ai_agents.native_browser_image import browser_image_content
            service = SimpleNamespace(production=store, check_grant=Mock(return_value=task))
            evidence = {'run': {'id': run_id, 'status': 'succeeded', 'source_stale': False,
                'observation': {'screenshot_artifact': artifact.model_dump(mode='json')}}}
            content = browser_image_content(service, task, evidence)
            self.assertEqual(content[0]['type'], 'image')
            self.assertEqual(base64.b64decode(content[0]['data']), screenshot.read_bytes())
            self.assertFalse(evidence['model_image_input']['visual_reviewed'])
            evidence['run']['source_stale'] = True
            self.assertEqual(browser_image_content(service, task, evidence), [])
            evidence['run']['source_stale'] = False
            task.grant.allow_model_image_input = False
            self.assertEqual(browser_image_content(service, task, evidence), [])
            self.assertEqual(evidence['model_image_input']['status'], 'not_authorized')

            with self.assertRaises(HarnessError) as caught:
                store.model_image_path(task, artifact.id, artifact.version, "other_run")
            self.assertEqual(caught.exception.code, "MODEL_IMAGE_SCOPE_DENIED")


if __name__ == "__main__":
    import unittest
    unittest.main()
