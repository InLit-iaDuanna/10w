"""Deterministic observations are facts, never model guesses."""
from sceneops_harness import FailureAnalysis, StepEvaluation


def observe_run(run):
    evaluations = []
    failures = []
    for step in run.step_runs:
        facts = [f"步骤状态：{step.state}", f"已记录尝试：{len(step.attempts)}", f"执行模式：{step.execution_mode.value}"]
        if step.reason:
            facts.append(step.reason)
        if step.attempts and step.attempts[-1].error_code:
            facts.append(f"错误码：{step.attempts[-1].error_code}")
        evidence = step.result.evidence_refs if step.result else []
        disposition = "recover" if step.state in {"failed", "blocked"} else "await_human" if step.state == "waiting_approval" else "continue"
        evaluations.append(StepEvaluation(step_run_id=step.id, deterministic_facts=facts,
            evidence_refs=evidence, next_disposition=disposition))
        if disposition == "recover":
            failures.append(FailureAnalysis(run_id=run.id, step_id=step.step_id,
                deterministic_facts=facts, evidence_refs=evidence))
    return evaluations, failures


__all__ = ["observe_run"]
