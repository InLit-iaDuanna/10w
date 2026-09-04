"""Integration Center read models and Judge Mode fallback explanation."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Tuple

from observability import CorrelationContext, ExecutionMode, LogQuery, ObservabilityQueryPort, Redactor

from .adapters import IntegrationGateway
from .schemas import (
    CachedEvidence,
    IntegrationDetails,
    IntegrationHealthSnapshot,
    JudgeFallback,
    JudgeModeHealthSummary,
    RestartGuidance,
    WorkerSnapshot,
)


class WorkerQueryPort(Protocol):
    def list_workers(self, project_id: str) -> List[WorkerSnapshot]:
        ...


class IntegrationCenterService:
    def __init__(
        self,
        gateway: IntegrationGateway,
        observability: ObservabilityQueryPort,
        workers: WorkerQueryPort,
        cached_evidence: Optional[List[CachedEvidence]] = None,
        redactor: Optional[Redactor] = None,
    ) -> None:
        self._gateway = gateway
        self._observability = observability
        self._workers = workers
        self._redactor = redactor or Redactor()
        evidence_items = cached_evidence or []
        evidence_keys = [(item.project_id, item.integration_id) for item in evidence_items]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("cached evidence must be unique per project and integration")
        self._cached_evidence: Dict[Tuple[str, str], CachedEvidence] = {
            key: item for key, item in zip(evidence_keys, evidence_items)
        }

    def list_health(
        self,
        context: CorrelationContext,
        now: Optional[datetime] = None,
    ) -> List[IntegrationHealthSnapshot]:
        observed_now = now or datetime.now(timezone.utc)
        return [
            self._gateway.query_health(integration_id, context, observed_now)
            for integration_id in self._gateway.integration_ids
        ]

    def details(
        self,
        integration_id: str,
        context: CorrelationContext,
        now: Optional[datetime] = None,
    ) -> IntegrationDetails:
        health = self._gateway.query_health(integration_id, context, now)
        logs = self._observability.query_logs(
            LogQuery(
                project_id=context.project_id,
                correlation_id=context.correlation_id,
                source_tool=integration_id,
                limit=100,
            )
        ).items
        return IntegrationDetails(health=health, recent_logs=logs)

    def list_workers(
        self,
        project_id: str,
        now: Optional[datetime] = None,
    ) -> List[WorkerSnapshot]:
        observed_now = now or datetime.now(timezone.utc)
        return [
            self._sanitize_worker(item, observed_now)
            for item in self._workers.list_workers(project_id)
        ]

    def restart_guidance(self, worker_id: str) -> RestartGuidance:
        return RestartGuidance(
            worker_id=worker_id,
            available=False,
            reason="尚未连接经过批准的 worker-control typed adapter；当前仅提供安全操作指导。",
            steps=[
                "确认当前任务已暂停或完成取消对账。",
                "在受管 Worker 主机上检查服务状态与关联日志。",
                "由有权限的操作者通过批准的部署流程重启 Worker。",
                "返回 Integration Center 重新执行健康探测。",
            ],
            command_id=None,
            requires_approval=True,
        )

    def judge_summary(
        self,
        context: CorrelationContext,
        now: Optional[datetime] = None,
    ) -> JudgeModeHealthSummary:
        observed_now = now or datetime.now(timezone.utc)
        integrations = self.list_health(context, observed_now)
        fallbacks = [
            self._fallback(snapshot, context.project_id, observed_now)
            for snapshot in integrations
        ]
        live_step_available = any(item.live_actions_enabled for item in integrations)
        mode = self._summary_mode(fallbacks)
        if mode == ExecutionMode.LIVE:
            headline = "Judge Mode 的集成健康探测均为当前 Live 结果。"
        elif mode == ExecutionMode.CACHED:
            headline = "部分工具不可用；Judge Mode 将使用明确标记的真实缓存证据。"
        elif mode == ExecutionMode.MOCK:
            headline = "部分工具仅有确定性 Mock；Judge Mode 不会把它们显示为 Live。"
        else:
            headline = "部分关键工具无可用证据；Judge Mode 已标记为 Blocked。"
        return JudgeModeHealthSummary(
            mode=mode,
            headline=headline,
            live_step_available=live_step_available,
            integrations=integrations,
            fallbacks=fallbacks,
        )

    def _fallback(
        self,
        health: IntegrationHealthSnapshot,
        project_id: str,
        now: datetime,
    ) -> JudgeFallback:
        if health.live_actions_enabled:
            return JudgeFallback(
                integration_id=health.integration_id,
                active=False,
                reason="当前 Live 健康探测可用。",
                evidence_mode=ExecutionMode.LIVE,
                live_step_available=True,
            )
        cached = self._cached_evidence.get((project_id, health.integration_id))
        if cached and cached.observed_at <= now < cached.expires_at:
            return JudgeFallback(
                integration_id=health.integration_id,
                active=True,
                reason="当前工具不可用，改用来源明确的历史真实运行证据。",
                evidence_mode=ExecutionMode.CACHED,
                source_run_id=cached.source_run_id,
                live_step_available=False,
            )
        if health.evidence.mode == ExecutionMode.MOCK:
            return JudgeFallback(
                integration_id=health.integration_id,
                active=True,
                reason="仅可展示确定性 Mock，用于解释界面而非证明真实执行。",
                evidence_mode=ExecutionMode.MOCK,
                live_step_available=False,
            )
        return JudgeFallback(
            integration_id=health.integration_id,
            active=True,
            reason=health.safe_reason or "当前没有 Live 或 Cached 证据。",
            evidence_mode=ExecutionMode.BLOCKED,
            live_step_available=False,
        )

    def _sanitize_worker(self, worker: WorkerSnapshot, now: datetime) -> WorkerSnapshot:
        is_current = worker.observed_at <= now < worker.expires_at
        current_job = worker.current_job
        if current_job is not None:
            current_job = current_job.model_copy(
                update={"title": self._redactor.redact_text(current_job.title)}
            )
        actions = [
            action.model_copy(
                update={
                    "label": self._redactor.redact_text(action.label),
                    "available": (
                        False
                        if action.command_id in {"job.cancel", "job.retry", "job.resume"}
                        and (worker.evidence.mode != ExecutionMode.LIVE or not is_current)
                        else action.available
                    ),
                    "unavailable_reason": (
                        "Worker 证据已过期或不是 Live；恢复控制命令不可用。"
                        if action.command_id in {"job.cancel", "job.retry", "job.resume"}
                        and (worker.evidence.mode != ExecutionMode.LIVE or not is_current)
                        else (
                            self._redactor.redact_text(action.unavailable_reason)
                            if action.unavailable_reason is not None
                            else None
                        )
                    ),
                }
            )
            for action in worker.recommended_actions
        ]
        return worker.model_copy(
            update={
                "display_name": self._redactor.redact_text(worker.display_name),
                "current_job": current_job,
                "is_current": is_current,
                "recommended_actions": actions,
            }
        )

    @staticmethod
    def _summary_mode(fallbacks: List[JudgeFallback]) -> ExecutionMode:
        modes = {item.evidence_mode for item in fallbacks}
        if ExecutionMode.BLOCKED in modes or ExecutionMode.PLANNED in modes:
            return ExecutionMode.BLOCKED
        if ExecutionMode.MOCK in modes:
            return ExecutionMode.MOCK
        if ExecutionMode.CACHED in modes:
            return ExecutionMode.CACHED
        return ExecutionMode.LIVE
