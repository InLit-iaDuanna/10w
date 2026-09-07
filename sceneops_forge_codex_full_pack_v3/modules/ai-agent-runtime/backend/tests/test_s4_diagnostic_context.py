"""S4 structured diagnosis and completion evidence; no browser or model calls."""
from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase

from sceneops_ai_agents.context_projection import (
    action_result_reference,
    project_game_diagnostics,
    project_observations,
    task_context_summary,
)
from sceneops_ai_agents.skill_context import select_skills
from sceneops_ai_agents.task_models import (
    ActionRecord,
    AgentAction,
    AgentTaskRecord,
    AuthorizationCard,
    NextActionInput,
    TaskGrant,
    now,
)
from sceneops_ai_agents.task_service import AgentTaskService
from sceneops_harness import HarnessError


def browser_action(action_id="behavior_before", *, failed=True, check="movement-collection"):
    assertions = [
        {"id": "keyboard-moves-player", "passed": True},
        {"id": "same-items-not-scored-twice", "passed": not failed},
    ]
    observation = {
        "status": "failed" if failed else "succeeded",
        "failure_code": "BROWSER_BEHAVIOR_CHECK_FAILED" if failed else None,
        "check_scope": check,
        "request": {"check": check, "state_id": "start"},
        "assertions": assertions,
        "initial_state": {"state_id": "start", "player": {"x": 0, "y": 0, "z": 0},
                          "score": 0, "private_debug_dump": "x" * 8000},
        "input_trace": [{"actual": {"player": {"x": 0, "y": 0, "z": 2}, "score": 1,
                                    "collectibles": [{"id": "coin-1", "collected": True,
                                                      "visible": False}]}}],
        "final_state": {"player": {"x": 0, "y": 0, "z": 2}, "score": 2 if failed else 1,
                        "collectibles": [{"id": "coin-1", "collected": True,
                                          "visible": False}]},
        "console_errors": [], "page_errors": [], "network_errors": [],
        "screenshot_artifact": {"id": "artifact_screen", "version": 3},
    }
    run = {"id": f"run_{action_id}", "operation": "interact", "status": observation["status"],
           "passed": not failed, "failure_code": observation["failure_code"],
           "build_kind": "test" if check != "current-input" else "delivery",
           "build_run_id": "build_1", "preview_run_id": "preview_1", "source_stale": False,
           "observation": observation}
    return ActionRecord(action=AgentAction(action_id=action_id,
        capability_id="code.browser.interact", rationale="Run bounded behavior check",
        inputs={"check": check, "state_id": "start", "steps": []}), state="succeeded",
        effect_state="COMMITTED", result={"evidence": {"tool": "browser_interaction", "run": run}})


def task(actions):
    capabilities = ["agent.next_action", "agent.history.read", "code.file.read",
                    "code.file.write", "code.browser.interact", "agent.finish"]
    card = AuthorizationCard(workspace_root="/fixture", task_profile="card-development",
        card_id="card_fixture", allow_game_execution=True, allow_browser_interaction=True,
        capability_ids=capabilities)
    record = AgentTaskRecord(project_id="project_fixture", goal="修复重复计分并复查普通移动",
                             authorization_card=card, actions=actions,
                             provider_id="fixture", provider_model="fixture-model")
    record.grant = TaskGrant(task_id=record.id, project_id=record.project_id,
        workspace_root="/fixture", card_id="card_fixture", allow_game_execution=True,
        allow_browser_interaction=True, capability_ids=capabilities,
        expires_at=now() + timedelta(minutes=5))
    latest_browser = next((item for item in reversed(actions)
                           if item.action.capability_id == "code.browser.interact"), None)
    record.observations["browser_interaction"] = (latest_browser.result["evidence"]
                                                   if latest_browser else {})
    return record


class DiagnosticProjectionTests(TestCase):
    def test_behavior_failure_keeps_only_decision_evidence_and_original_references(self):
        record = task([browser_action()])

        diagnostics = project_game_diagnostics(record)
        projected = project_observations(record, can_read_history=True)

        behavior = diagnostics["checks"]["movement-collection"]
        self.assertEqual(behavior["evidence_status"], "fail")
        self.assertEqual(behavior["issue_types"], ["behavior_issue"])
        self.assertEqual(behavior["assertions"]["failed"], ["same-items-not-scored-twice"])
        self.assertEqual(behavior["states"]["first_input"]["score"], 1)
        self.assertEqual(behavior["states"]["final"]["score"], 2)
        self.assertEqual(behavior["result_reference"], action_result_reference("behavior_before"))
        self.assertEqual(behavior["screenshot_reference"],
                         {"artifact_id": "artifact_screen", "version": 3})
        self.assertNotIn("private_debug_dump", str(diagnostics))
        self.assertNotIn("run", projected["browser_interaction"])

    def test_successful_code_write_makes_the_old_browser_result_stale(self):
        write = ActionRecord(action=AgentAction(action_id="fix_original",
            capability_id="code.file.write", rationale="Fix collectible state",
            inputs={"path": "src/game/Collectible.ts", "expected_content": "before",
                    "content": "after"}), state="succeeded", effect_state="COMMITTED")
        record = task([browser_action(), write])

        diagnostics = project_game_diagnostics(record)

        self.assertEqual(diagnostics["checks"]["movement-collection"]["evidence_status"], "stale")
        self.assertEqual(task_context_summary(record)["game_diagnostics"], diagnostics)

    def test_structured_behavior_failure_selects_diagnosis_without_log_search(self):
        record = task([browser_action()])
        data = NextActionInput(goal=record.goal,
            context_summary=task_context_summary(record), observations={}, history=[],
            capabilities=[{"id": item} for item in record.authorization_card.capability_ids],
            expected_provider="fixture", expected_model="fixture-model")

        phase, skills = select_skills(data)

        self.assertEqual(phase, "diagnosis")
        self.assertEqual(skills, ["gameplay", "debug"])


class FinishEvidenceTests(TestCase):
    def service(self, record):
        run = SimpleNamespace(status="succeeded", passed=True, source_stale=False)
        preview = SimpleNamespace(status="running", passed=True, source_stale=False,
                                  preview_url="http://127.0.0.1:1234/")
        snapshot = SimpleNamespace(check=run, build=run, preview=preview, card_id="card_fixture",
                                   branch="codex/card_fixture", workspace_root="/fixture")
        return SimpleNamespace(game=SimpleNamespace(snapshot=lambda current: snapshot))

    def test_finish_reports_missing_delivery_input_without_generic_pending_claim(self):
        record = task([browser_action(failed=False)])
        service = self.service(record)

        evidence = AgentTaskService.finish_game(service, record)

        self.assertEqual(evidence["verified_scopes"], ["movement-collection"])
        self.assertIn("movement-collection=pass", evidence["summary"])
        self.assertNotIn("待浏览器", evidence["summary"])

    def test_finish_reports_local_scopes_without_claiming_global_gameplay(self):
        record = task([
            browser_action("behavior_after", failed=False),
            browser_action("delivery_after", failed=False, check="current-input"),
        ])
        service = self.service(record)

        evidence = AgentTaskService.finish_game(service, record)

        self.assertEqual(evidence["verified_scopes"], ["movement-collection", "current-input"])
        self.assertTrue(evidence["browser_errors_verified"])
        self.assertFalse(evidence["gameplay_verified"])
        self.assertIn("未执行完整玩法或视觉评审", evidence["summary"])


if __name__ == "__main__":
    import unittest
    unittest.main()
