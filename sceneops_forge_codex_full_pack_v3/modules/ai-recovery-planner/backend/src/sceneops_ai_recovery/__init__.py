"""Model diagnosis is a proposal; it cannot grant permissions or retry by itself."""
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sceneops_harness import CauseCandidate, RecoveryPlan


class RecoverySuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    causes: list[str] = Field(default_factory=list)
    action: Literal["retry", "add_context", "upgrade_model", "switch_capability", "rollback", "ask_human", "abort"]
    reason: str


async def propose_recovery(provider, failure, attempts: int, max_attempts: int):
    prompt = ("基于以下运行事实诊断失败。原因只能列为候选推断，不声称已验证。"
        "不扩大权限、不执行、不循环重试。连续两次失败后应要求人工检查。返回schema JSON：\n"
        + json.dumps({"failure": failure.model_dump(mode="json"), "attempts": attempts,
            "max_attempts": max_attempts}, ensure_ascii=False))
    suggestion = RecoverySuggestion.model_validate(await provider.structured(
        prompt, RecoverySuggestion.model_json_schema(), purpose="recovery"))
    action = suggestion.action
    if action == "retry" and (attempts >= max_attempts or attempts >= 2):
        action = "ask_human"
    return RecoveryPlan(run_id=failure.run_id, step_id=failure.step_id,
        cause_candidates=[CauseCandidate(description=text, evidence_refs=failure.evidence_refs)
            for text in suggestion.causes], selected_action=action,
        reason=suggestion.reason, maximum_additional_attempts=1 if action == "retry" else 0,
        requires_approval=True)


__all__ = ["propose_recovery"]
