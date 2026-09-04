from __future__ import annotations

from typing import Tuple

from .schemas import FailureKind, FailureSignal


IssueKey = Tuple[str, str, str]


def signal_issue_key(signal: FailureSignal) -> IssueKey:
    """Return a stable diagnostic identity without conflating unrelated failures."""

    target = signal.target_sceneops_id or "none"
    discriminator = _diagnostic_discriminator(signal, include_phase=True)
    return signal.kind.value, target, discriminator


def signal_run_dedupe_key(signal: FailureSignal) -> IssueKey:
    target = signal.target_sceneops_id or "none"
    return (
        signal.kind.value,
        target,
        _diagnostic_discriminator(signal, include_phase=False),
    )


def _diagnostic_discriminator(
    signal: FailureSignal, include_phase: bool
) -> str:
    if signal.kind == FailureKind.RUNTIME_ERROR:
        return str(signal.details.get("error_id", signal.details.get("code", "")))
    if signal.kind in {FailureKind.NAVIGATION_ERROR, FailureKind.COLLIDER_ERROR}:
        return ":".join(
            str(signal.details.get(name, "")) for name in ("code", "action_id")
        )
    if signal.kind == FailureKind.UNREACHABLE_GOAL:
        blocked = signal.details.get("blocked_goal_ids")
        if blocked is not None:
            return str(blocked)
        return f"max_steps:{signal.details.get('max_steps', '')}"
    if signal.kind == FailureKind.PERFORMANCE_REGRESSION:
        identity = ",".join(sorted(signal.details))
    elif "action_id" in signal.details:
        identity = str(signal.details["action_id"])
    else:
        identity = ""
    if not include_phase:
        return identity
    if signal.step_indices:
        phase = f"steps:{signal.step_indices[0]}-{signal.step_indices[-1]}"
    else:
        phase = "initial"
    return f"{identity}:{phase}"
