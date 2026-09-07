"""Compact task context while keeping exact action data in durable records."""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from sceneops_harness import HarnessError

REFERENCE_ONLY_FIELDS = {
    "after", "before", "content", "diff", "expected_content", "log", "result",
    "stderr", "stdout", "value",
}

BROWSER_CAPABILITIES = {"code.browser.observe", "code.browser.interact"}


def action_input_reference(action_id: str, field: str) -> str:
    return f"task-action://{action_id}/input/{field}"


def action_result_reference(action_id: str) -> str:
    return f"task-action://{action_id}/result"


def _compact_json(value: Any, reference: str, *, depth: int = 0) -> Any:
    """Retain small exact values and point large branches back to the source record."""
    if isinstance(value, str):
        if len(value) <= 400:
            return value
        return {"reference": reference, "characters": len(value)}
    if isinstance(value, dict):
        if depth >= 4:
            return {"reference": reference, "keys": len(value)}
        items = list(value.items())
        projected = {}
        for key, item in items[:24]:
            if key in REFERENCE_ONLY_FIELDS and isinstance(item, str):
                projected[key] = {"reference": reference, "characters": len(item)}
            else:
                projected[key] = _compact_json(item, reference, depth=depth + 1)
        if len(items) > 24:
            projected["_remaining"] = {"reference": reference, "keys": len(items) - 24}
        return projected
    if isinstance(value, list):
        if depth >= 4:
            return {"reference": reference, "items": len(value)}
        projected = [_compact_json(item, reference, depth=depth + 1) for item in value[:16]]
        if len(value) > 16:
            projected.append({"reference": reference, "remaining_items": len(value) - 16})
        return projected
    return value


def project_action_history(actions, *, can_read_history: bool = True) -> list[dict]:
    """Project useful action/result links without breaking historical grants."""
    history = []
    for entry in actions:
        action = entry.action.model_dump(mode="json")
        if not can_read_history:
            projected = {"action": action, "state": entry.state,
                         "effect_state": entry.effect_state, "reason": entry.reason}
            if entry.result is not None:
                projected["result"] = deepcopy(entry.result)
            history.append(projected)
            continue
        references = {}
        if entry.action.capability_id == "code.file.write":
            for field in ("expected_content", "content"):
                if field not in action["inputs"]:
                    continue
                value = action["inputs"].pop(field)
                reference = action_input_reference(entry.action.action_id, field)
                references[field] = {"reference": reference,
                                     "characters": len(value) if isinstance(value, str) else 0,
                                     "is_null": value is None}
        projected = {"action": action, "state": entry.state,
                     "effect_state": entry.effect_state, "reason": entry.reason}
        if references:
            projected["input_references"] = references
        if entry.result is not None:
            reference = action_result_reference(entry.action.action_id)
            projected["result_reference"] = reference
            projected["result_summary"] = _compact_json(entry.result, reference)
        history.append(projected)
    return history


def project_observations(task, *, can_read_history: bool) -> dict:
    """Keep the latest exact tool result and reference superseded large results."""
    observations = deepcopy(task.observations)
    if not can_read_history:
        return observations
    diagnostics = project_game_diagnostics(task)
    for key in ("browser_interaction", "browser_observation"):
        if key in observations:
            observations[key] = {
                "diagnostic_context": diagnostics,
                "notice": "浏览器正文保留在原动作结果中；按 result_reference 读取，不在每轮模型请求中重发。",
            }
    sources = {}
    for index, entry in enumerate(task.actions):
        evidence = entry.result.get("evidence") if isinstance(entry.result, dict) else None
        tool = evidence.get("tool") if isinstance(evidence, dict) else None
        if isinstance(tool, str):
            sources[tool] = (index, entry)
    latest_index = len(task.actions) - 1
    for key, value in list(observations.items()):
        source = sources.get(key)
        if source is None or source[0] == latest_index:
            continue
        if len(json.dumps(value, ensure_ascii=False, default=str)) <= 2000:
            continue
        reference = action_result_reference(source[1].action.action_id)
        observations[key] = {
            "result_reference": reference,
            "summary": _compact_json(value, reference),
            "notice": "该旧工具结果已由后续动作取代；需要精确正文时读取 result_reference。",
        }
    return observations


def _state_summary(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    result = {}
    for key in ("state_id", "player", "score"):
        if key in value:
            result[key] = deepcopy(value[key])
    simulation = value.get("simulation")
    if isinstance(simulation, dict):
        result["simulation"] = {key: simulation[key] for key in ("steps", "elapsed_seconds")
                                if key in simulation}
    collectibles = value.get("collectibles")
    if isinstance(collectibles, list):
        result["collectibles"] = [{key: item[key] for key in ("id", "collected", "visible")
                                   if key in item}
                                  for item in collectibles[:16] if isinstance(item, dict)]
    return result or None


def _browser_diagnostic(task, index: int, entry) -> dict:
    reference = action_result_reference(entry.action.action_id)
    evidence = entry.result.get("evidence") if isinstance(entry.result, dict) else None
    run = evidence.get("run") if isinstance(evidence, dict) else None
    if not isinstance(run, dict):
        return {
            "evidence_status": "unknown",
            "issue_types": ["result_unavailable"],
            "capability_id": entry.action.capability_id,
            "result_reference": reference,
        }
    observation = run.get("observation") if isinstance(run.get("observation"), dict) else {}
    request = observation.get("request") if isinstance(observation.get("request"), dict) else {}
    assertions = observation.get("assertions") if isinstance(observation.get("assertions"), list) else []
    passed = [item.get("id") for item in assertions
              if isinstance(item, dict) and item.get("passed") is True and isinstance(item.get("id"), str)]
    failed = [item.get("id") for item in assertions
              if isinstance(item, dict) and item.get("passed") is False and isinstance(item.get("id"), str)]
    later_write = any(item.state == "succeeded" and item.action.capability_id == "code.file.write"
                      for item in task.actions[index + 1:])
    stale = bool(run.get("source_stale") or later_write)
    browser_errors = {
        key: [str(value)[:500] for value in observation.get(key, [])[:8]]
        for key in ("console_errors", "page_errors", "network_errors")
        if isinstance(observation.get(key), list) and observation.get(key)
    }
    failure_code = run.get("failure_code") or observation.get("failure_code")
    issue_types = []
    if stale:
        status = "stale"
    else:
        if failed or failure_code == "BROWSER_BEHAVIOR_CHECK_FAILED":
            issue_types.append("behavior_issue")
        if browser_errors:
            issue_types.append("browser_errors")
        if run.get("status") in ("failed", "interrupted") and not issue_types:
            issue_types.append("tool_failure")
        status = ("fail" if issue_types else "pass" if run.get("status") == "succeeded"
                  and run.get("passed") is True else "unknown")
    trace = observation.get("input_trace") if isinstance(observation.get("input_trace"), list) else []
    first_input = next((item.get("actual") for item in trace if isinstance(item, dict)
                        and isinstance(item.get("actual"), dict)), None)
    screenshot = observation.get("screenshot_artifact")
    screenshot_reference = None
    if isinstance(screenshot, dict) and isinstance(screenshot.get("id"), str) \
            and isinstance(screenshot.get("version"), int):
        screenshot_reference = {"artifact_id": screenshot["id"], "version": screenshot["version"]}
    return {
        "evidence_status": status,
        "issue_types": issue_types,
        "capability_id": entry.action.capability_id,
        "scope": {
            "build_kind": run.get("build_kind"),
            "check": observation.get("check_scope") or request.get("check"),
            "state_id": request.get("state_id"),
            "build_run_id": run.get("build_run_id"),
            "preview_run_id": run.get("preview_run_id"),
            "browser_run_id": run.get("id"),
        },
        "assertions": {"failed": failed, "passed": passed},
        "states": {
            key: summary for key, summary in (
                ("initial", _state_summary(observation.get("initial_state"))),
                ("first_input", _state_summary(first_input)),
                ("final", _state_summary(observation.get("final_state"))),
            ) if summary is not None
        },
        "browser_errors": browser_errors,
        "failure": ({"code": failure_code,
                     "reason": str(observation.get("reason") or run.get("log") or "")[:500]}
                    if failure_code else None),
        "result_reference": reference,
        "screenshot_reference": screenshot_reference,
    }


def project_game_diagnostics(task) -> dict:
    """Summarize current browser evidence without treating logs as verdicts."""
    checks = {}
    latest = None
    for index, entry in enumerate(task.actions):
        if entry.action.capability_id not in BROWSER_CAPABILITIES:
            continue
        diagnostic = _browser_diagnostic(task, index, entry)
        latest = diagnostic
        scope = diagnostic.get("scope", {})
        name = scope.get("check") if isinstance(scope, dict) else None
        checks[name or "current-view"] = diagnostic
    if latest is None:
        latest = {"evidence_status": "not_run", "issue_types": [],
                  "result_reference": None, "screenshot_reference": None}
    return {"latest": latest, "checks": checks}


def task_context_summary(task, *, can_read_history: bool = True) -> dict:
    """Short handoff facts; current authority and capabilities remain runtime-owned."""
    latest = task.actions[-1] if task.actions else None
    latest_non_success = next((entry for entry in reversed(task.actions)
        if entry.state in ("running", "failed", "uncertain", "blocked")), None)
    current_issue = None
    if task.status in ("blocked", "failed", "needs_approval", "interrupted", "cancel_pending"):
        current_issue = {"task_status": task.status, "reason": task.reason,
                         "evidence_basis": "任务当前终态或阻塞状态"}
    elif latest and latest.state in ("running", "uncertain", "blocked"):
        current_issue = {"action_id": latest.action.action_id,
                         "capability_id": latest.action.capability_id,
                         "state": latest.state, "reason": latest.reason,
                         "evidence_basis": "最近动作的当前状态"}
    result = {
        "task_id": task.id,
        "project_id": task.project_id,
        "workspace_id": (task.grant.workspace_id if task.grant else
                         task.authorization_card.workspace_id),
        "task_profile": task.authorization_card.task_profile,
        "execution_mode": task.grant.execution_mode,
        "completed_action_count": sum(entry.state == "succeeded" for entry in task.actions),
        "latest_action": ({"action_id": latest.action.action_id,
                           "capability_id": latest.action.capability_id,
                           "state": latest.state} if latest else None),
        "latest_non_success_action": ({"action_id": latest_non_success.action.action_id,
                                       "capability_id": latest_non_success.action.capability_id,
                                       "state": latest_non_success.state,
                                       "reason": latest_non_success.reason} if latest_non_success else None),
        "current_issue": current_issue,
        "history_policy": ("完整记录仍在任务存储中；正文和长结果通过 task-action 引用按需读取。"
                           if can_read_history else
                           "当前授权没有历史读取能力；必要的历史输入和结果以内联兼容模式提供。"),
    }
    if task.authorization_card.allow_browser_observation or task.authorization_card.allow_browser_interaction:
        result["game_diagnostics"] = project_game_diagnostics(task)
    if task.authorization_card.task_profile in ('project-demo', 'project-demo-agent'):
        context = task.observations.get('project_demo_context')
        if isinstance(context, dict):
            result['confirmed_direction'] = deepcopy(context)
        requests = task.observations.get('demo_goals')
        if isinstance(requests, list) and requests:
            result['active_demo_request'] = deepcopy(requests[-1])
    return result


def read_history_reference(task, reference: str):
    """Resolve an exact reference inside the current task only."""
    prefix = "task-action://"
    if not reference.startswith(prefix):
        raise HarnessError("HISTORY_REFERENCE_INVALID", "历史引用格式无效。")
    action_id, separator, locator = reference[len(prefix):].partition("/")
    if not separator:
        raise HarnessError("HISTORY_REFERENCE_INVALID", "历史引用格式无效。")
    entry = next((item for item in task.actions if item.action.action_id == action_id), None)
    if entry is None:
        raise HarnessError("HISTORY_REFERENCE_NOT_FOUND", "当前任务中没有对应的历史动作。")
    if locator == "result":
        if entry.result is None:
            raise HarnessError("HISTORY_RESULT_UNAVAILABLE", "该动作还没有可读取的历史结果。")
        return deepcopy(entry.result)
    if locator not in ("input/expected_content", "input/content"):
        raise HarnessError("HISTORY_REFERENCE_INVALID", "历史引用不属于允许读取的字段。")
    field = locator.rsplit("/", 1)[-1]
    if entry.action.capability_id != "code.file.write" or field not in entry.action.inputs:
        raise HarnessError("HISTORY_REFERENCE_NOT_FOUND", "当前动作没有对应的历史正文。")
    return deepcopy(entry.action.inputs[field])
