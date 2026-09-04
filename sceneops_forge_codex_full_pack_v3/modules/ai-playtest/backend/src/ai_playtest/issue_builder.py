from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence, Set

from .backpin import BackpinResolver
from .issue_identity import IssueKey, signal_run_dedupe_key
from .ports import PlaytestRunnerAdapter, RuntimeSession
from .schemas import (
    Backpin,
    BackpinStatus,
    EvidenceBundle,
    FailureSignal,
    Issue,
    PlaytestRun,
    PlaytestStep,
    RestorationContext,
)


def create_issues(
    run: PlaytestRun,
    session: RuntimeSession,
    step: PlaytestStep,
    adapter: PlaytestRunnerAdapter,
    resolver: BackpinResolver,
) -> None:
    origin = run.steps[0].observation.observed_at
    _append_issues(
        run,
        session,
        step.failure_signals,
        step.evidence,
        step.scene_id,
        step.completed_at,
        step.step_index,
        max(0, (step.evidence.captured_at - origin).total_seconds()),
        adapter,
        resolver,
    )


def create_terminal_issues(
    run: PlaytestRun,
    session: RuntimeSession,
    signals: Sequence[FailureSignal],
    evidence: EvidenceBundle,
    observed_at: datetime,
    adapter: PlaytestRunnerAdapter,
    resolver: BackpinResolver,
) -> None:
    timeline_time_seconds = (
        max(
            0,
            (
                evidence.captured_at
                - run.steps[0].observation.observed_at
            ).total_seconds(),
        )
        if run.steps
        else 0
    )
    _append_issues(
        run,
        session,
        signals,
        evidence,
        evidence.scene_id,
        observed_at,
        None,
        timeline_time_seconds,
        adapter,
        resolver,
    )


def _append_issues(
    run: PlaytestRun,
    session: RuntimeSession,
    signals: Sequence[FailureSignal],
    evidence: EvidenceBundle,
    scene_id: str,
    created_at: datetime,
    step_index: Optional[int],
    timeline_time_seconds: float,
    adapter: PlaytestRunnerAdapter,
    resolver: BackpinResolver,
) -> None:
    existing: Set[IssueKey] = {
        signal_run_dedupe_key(issue.failure_signal) for issue in run.issues
    }
    for signal in signals:
        key = signal_run_dedupe_key(signal)
        if key in existing:
            continue
        candidates = adapter.source_candidates(session, signal.target_sceneops_id)
        issue_id = f"{run.run_id}:issue:{len(run.issues)}"
        backpin = resolver.resolve(
            f"{issue_id}:backpin", signal, evidence, candidates
        )
        run.issues.append(
            _make_issue(
                run,
                signal,
                evidence,
                issue_id,
                backpin,
                scene_id,
                created_at,
                step_index,
                timeline_time_seconds,
            )
        )
        existing.add(key)


def _make_issue(
    run: PlaytestRun,
    signal: FailureSignal,
    evidence: EvidenceBundle,
    issue_id: str,
    backpin: Backpin,
    scene_id: str,
    created_at: datetime,
    step_index: Optional[int],
    timeline_time_seconds: float,
) -> Issue:
    selected = list(
        dict.fromkeys(
            identifier
            for identifier in [backpin.sceneops_id, signal.target_sceneops_id]
            if identifier
        )
    )
    restoration = RestorationContext(
        scene_id=scene_id,
        selected_sceneops_ids=selected,
        camera=evidence.camera,
        trajectory=evidence.trajectory,
        timeline_time_seconds=timeline_time_seconds,
        step_index=step_index,
    )
    status_label = (
        "回钉需要人工确认。"
        if backpin.status == BackpinStatus.RESOLVED
        else "回钉未唯一解析，禁止自动修复。"
    )
    return Issue(
        issue_id=issue_id,
        run_id=run.run_id,
        test_case_id=run.test_case.test_case_id,
        title=f"AI 预筛：{signal.kind.value}",
        created_at=created_at,
        execution_mode=run.execution_mode,
        failure_signal=signal,
        evidence=evidence,
        backpin=backpin,
        restoration=restoration,
        limitation_labels=[
            status_label,
            "AI Playtest 不能替代真人体验、可用性或偏好测试。",
        ],
    )
