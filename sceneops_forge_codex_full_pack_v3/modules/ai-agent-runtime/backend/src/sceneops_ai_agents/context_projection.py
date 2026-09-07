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
    return {
        "task_id": task.id,
        "project_id": task.project_id,
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
