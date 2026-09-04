"""Vendor-neutral integration gateway and compatibility/circuit policy."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional, Protocol, Tuple

from observability import CorrelationContext, ExecutionMode, Redactor

from .circuit import CircuitBreaker, CircuitOpenError
from .contract_validation import STABLE_ID_PATTERN, require_unique_stable

from .schemas import (
    ActivityState,
    AuthorizationState,
    AvailabilityState,
    CapabilityReport,
    CircuitSnapshot,
    CircuitState,
    CompatibilityState,
    ConnectionState,
    ExecutionEvidence,
    HealthProbe,
    HealthSummaryState,
    IntegrationHealthSnapshot,
    QueueSnapshot,
    RecommendedAction,
)


class AdapterError(RuntimeError):
    def __init__(
        self,
        code: str,
        safe_message: str,
        state: HealthSummaryState,
        transient: bool,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.state = state
        self.transient = transient


class IntegrationAdapter(Protocol):
    integration_id: str

    def health_check(self, context: CorrelationContext) -> HealthProbe:
        ...

    def capability_report(self, context: CorrelationContext) -> CapabilityReport:
        ...


@dataclass(frozen=True)
class CompatibilityPolicy:
    minimum_version: Optional[str] = None
    maximum_version_exclusive: Optional[str] = None
    required_capability_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_unique_stable(list(self.required_capability_ids))


@dataclass(frozen=True)
class IntegrationDefinition:
    integration_id: str
    display_name: str
    compatibility: CompatibilityPolicy = field(default_factory=CompatibilityPolicy)

    def __post_init__(self) -> None:
        if re.fullmatch(STABLE_ID_PATTERN, self.integration_id) is None:
            raise ValueError("integration_id must be a stable identifier")
        if not self.display_name or len(self.display_name) > 120:
            raise ValueError("display_name must contain between 1 and 120 characters")


class IntegrationGateway:
    """Calls fresh typed probes; it never infers health from configuration alone."""

    def __init__(
        self,
        definitions: Iterable[IntegrationDefinition],
        failure_threshold: int = 3,
        cooldown: timedelta = timedelta(seconds=30),
        capability_ttl: timedelta = timedelta(minutes=5),
        redactor: Optional[Redactor] = None,
    ) -> None:
        definition_items = list(definitions)
        if len({item.integration_id for item in definition_items}) != len(definition_items):
            raise ValueError("integration definitions must have unique IDs")
        self._definitions = {item.integration_id: item for item in definition_items}
        if not self._definitions:
            raise ValueError("at least one integration definition is required")
        if capability_ttl.total_seconds() <= 0:
            raise ValueError("capability_ttl must be positive")
        self._capability_ttl = capability_ttl
        self._redactor = redactor or Redactor()
        self._adapters: Dict[str, IntegrationAdapter] = {}
        self._circuits = {
            integration_id: CircuitBreaker(failure_threshold, cooldown)
            for integration_id in self._definitions
        }

    @property
    def integration_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def register(self, adapter: IntegrationAdapter) -> None:
        if adapter.integration_id not in self._definitions:
            raise ValueError("adapter is not declared: %s" % adapter.integration_id)
        self._adapters[adapter.integration_id] = adapter

    def query_health(
        self,
        integration_id: str,
        context: CorrelationContext,
        now: Optional[datetime] = None,
    ) -> IntegrationHealthSnapshot:
        observed_now = now or datetime.now(timezone.utc)
        definition = self._definitions.get(integration_id)
        if definition is None:
            raise KeyError(integration_id)
        adapter = self._adapters.get(integration_id)
        if adapter is None:
            return self._unavailable(definition, observed_now, "ADAPTER_NOT_REGISTERED", "适配器尚未注册。")

        circuit = self._circuits[integration_id]
        try:
            circuit.before_call(observed_now)
        except CircuitOpenError as error:
            return self._circuit_open(definition, observed_now, circuit.snapshot(), error.retry_at)

        try:
            probe = adapter.health_check(context)
            capabilities = adapter.capability_report(context)
            self._validate_adapter_identity(integration_id, probe, capabilities)
            probe = self._sanitize_probe(probe)
        except AdapterError as error:
            circuit.record_failure(observed_now, error.transient)
            return self._adapter_error(definition, observed_now, circuit.snapshot(), error)
        except Exception:
            circuit.record_failure(observed_now, False)
            error = AdapterError("ADAPTER_CONTRACT_FAILED", "适配器健康探测未满足类型契约，请查看安全日志。", HealthSummaryState.DEGRADED, False)
            return self._adapter_error(definition, observed_now, circuit.snapshot(), error)

        circuit.record_success()
        compatibility, mismatch = self._compatibility(definition.compatibility, capabilities)
        capability_is_current = (
            capabilities.observed_at <= observed_now
            < capabilities.observed_at + self._capability_ttl
        )
        is_current = probe.observed_at <= observed_now < probe.expires_at and capability_is_current
        capability_mode_reason = None
        capability_freshness_reason = None
        if capabilities.evidence.mode != probe.evidence.mode:
            capability_mode_reason = "健康与能力报告的证据模式不一致。"
            compatibility = CompatibilityState.UNKNOWN
        elif not capability_is_current:
            capability_freshness_reason = "能力报告已过期或来自未来，必须重新探测。"
            compatibility = CompatibilityState.UNKNOWN
        summary = self._derive_summary(probe, compatibility, is_current)
        safe_reason = mismatch or capability_mode_reason or capability_freshness_reason or probe.safe_reason
        if mismatch:
            reason_code = "CAPABILITY_OR_VERSION_MISMATCH"
        elif capability_mode_reason:
            reason_code = "EVIDENCE_MODE_MISMATCH"
        elif capability_freshness_reason:
            reason_code = "CAPABILITY_EVIDENCE_STALE"
        else:
            reason_code = probe.reason_code
        live_actions_enabled = (
            probe.evidence.mode == ExecutionMode.LIVE
            and capabilities.evidence.mode == ExecutionMode.LIVE
            and is_current
            and summary in (HealthSummaryState.CONNECTED, HealthSummaryState.BUSY)
        )
        return IntegrationHealthSnapshot(
            integration_id=probe.integration_id,
            display_name=probe.display_name,
            summary_state=summary,
            connection=probe.connection,
            authorization=probe.authorization,
            compatibility=compatibility,
            availability=probe.availability,
            activity=probe.activity,
            observed_at=probe.observed_at,
            expires_at=probe.expires_at,
            last_seen_at=probe.last_seen_at,
            tool_version=capabilities.tool_version or probe.tool_version,
            adapter_version=capabilities.adapter_version,
            capability_ids=capabilities.capability_ids,
            allowlisted_command_ids=capabilities.allowlisted_command_ids,
            current_job=probe.current_job,
            queue=probe.queue,
            circuit=circuit.snapshot(),
            reason_code=reason_code,
            safe_reason=safe_reason,
            recommended_actions=self._actions(safe_reason),
            is_current=is_current,
            live_actions_enabled=live_actions_enabled,
            evidence=probe.evidence,
        )

    def _sanitize_probe(self, probe: HealthProbe) -> HealthProbe:
        current_job = probe.current_job
        if current_job is not None:
            current_job = current_job.model_copy(
                update={"title": self._redactor.redact_text(current_job.title)}
            )
        return probe.model_copy(
            update={
                "display_name": self._redactor.redact_text(probe.display_name),
                "safe_reason": (
                    self._redactor.redact_text(probe.safe_reason)
                    if probe.safe_reason is not None
                    else None
                ),
                "current_job": current_job,
            }
        )

    @staticmethod
    def _validate_adapter_identity(
        integration_id: str,
        probe: HealthProbe,
        capabilities: CapabilityReport,
    ) -> None:
        if probe.integration_id != integration_id or capabilities.integration_id != integration_id:
            raise AdapterError(
                "ADAPTER_IDENTITY_MISMATCH",
                "适配器返回了不匹配的集成标识。",
                HealthSummaryState.INCOMPATIBLE,
                False,
            )

    @classmethod
    def _compatibility(
        cls,
        policy: CompatibilityPolicy,
        report: CapabilityReport,
    ) -> Tuple[CompatibilityState, Optional[str]]:
        missing = sorted(set(policy.required_capability_ids) - set(report.capability_ids))
        if missing:
            return CompatibilityState.INCOMPATIBLE, "缺少能力：%s。" % "、".join(missing)
        if policy.minimum_version or policy.maximum_version_exclusive:
            if not report.tool_version:
                return CompatibilityState.UNKNOWN, "工具未报告可比较的版本。"
            try:
                current = cls._parse_version(report.tool_version)
                if policy.minimum_version and current < cls._parse_version(policy.minimum_version):
                    return CompatibilityState.INCOMPATIBLE, "工具版本低于最低支持版本 %s。" % policy.minimum_version
                if policy.maximum_version_exclusive and current >= cls._parse_version(policy.maximum_version_exclusive):
                    return CompatibilityState.INCOMPATIBLE, "工具版本不低于上限 %s。" % policy.maximum_version_exclusive
            except AdapterError as error:
                return CompatibilityState.INCOMPATIBLE, error.safe_message
        return CompatibilityState.COMPATIBLE, None

    @staticmethod
    def _parse_version(value: str) -> Tuple[int, int, int]:
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?", value)
        if not match:
            raise AdapterError(
                "VERSION_FORMAT_INVALID",
                "工具版本必须由适配器规范化为 major.minor.patch。",
                HealthSummaryState.INCOMPATIBLE,
                False,
            )
        return tuple(int(part) for part in match.groups())  # type: ignore[return-value]

    @staticmethod
    def _derive_summary(
        probe: HealthProbe,
        compatibility: CompatibilityState,
        is_current: bool,
    ) -> HealthSummaryState:
        if not is_current:
            return HealthSummaryState.UNKNOWN
        if probe.connection == ConnectionState.DISCONNECTED:
            return HealthSummaryState.DISCONNECTED
        if compatibility == CompatibilityState.INCOMPATIBLE:
            return HealthSummaryState.INCOMPATIBLE
        if probe.authorization == AuthorizationState.UNAUTHORIZED:
            return HealthSummaryState.UNAUTHORIZED
        if probe.availability == AvailabilityState.DEGRADED:
            return HealthSummaryState.DEGRADED
        if probe.activity == ActivityState.BUSY:
            return HealthSummaryState.BUSY
        if (
            probe.connection == ConnectionState.CONNECTED
            and probe.authorization == AuthorizationState.AUTHORIZED
            and compatibility == CompatibilityState.COMPATIBLE
            and probe.availability == AvailabilityState.AVAILABLE
        ):
            return HealthSummaryState.CONNECTED
        return HealthSummaryState.UNKNOWN

    @staticmethod
    def _actions(
        reason: Optional[str],
        circuit_open: bool = False,
    ) -> list:
        refresh_available = not circuit_open
        return [
            RecommendedAction(
                command_id="integration.health.refresh",
                label="重新探测",
                available=refresh_available,
                unavailable_reason=None if refresh_available else (reason or "等待熔断器允许下一次探测。"),
            ),
            RecommendedAction(command_id="integration.open_logs", label="查看关联日志", available=True),
            RecommendedAction(command_id="integration.open_setup", label="打开设置与恢复说明", available=True),
        ]

    def _unavailable(
        self,
        definition: IntegrationDefinition,
        now: datetime,
        code: str,
        reason: str,
    ) -> IntegrationHealthSnapshot:
        evidence = ExecutionEvidence(mode=ExecutionMode.BLOCKED, observed_at=now, reason=reason)
        return IntegrationHealthSnapshot(
            integration_id=definition.integration_id,
            display_name=self._redactor.redact_text(definition.display_name),
            summary_state=HealthSummaryState.UNKNOWN,
            connection=ConnectionState.UNKNOWN,
            authorization=AuthorizationState.UNKNOWN,
            compatibility=CompatibilityState.UNKNOWN,
            availability=AvailabilityState.UNKNOWN,
            activity=ActivityState.IDLE,
            observed_at=now,
            expires_at=now + timedelta(seconds=1),
            queue=QueueSnapshot(depth=0, running=0),
            circuit=self._circuits[definition.integration_id].snapshot(),
            reason_code=code,
            safe_reason=reason,
            recommended_actions=self._actions(reason),
            is_current=False,
            live_actions_enabled=False,
            evidence=evidence,
        )

    def _adapter_error(
        self,
        definition: IntegrationDefinition,
        now: datetime,
        circuit: CircuitSnapshot,
        error: AdapterError,
    ) -> IntegrationHealthSnapshot:
        safe_message = self._redactor.redact_text(error.safe_message)
        reason_code = error.code if re.fullmatch(r"[A-Z0-9_]{1,120}", error.code) else "ADAPTER_ERROR"
        connection = ConnectionState.DISCONNECTED if error.state == HealthSummaryState.DISCONNECTED else ConnectionState.UNKNOWN
        authorization = AuthorizationState.UNAUTHORIZED if error.state == HealthSummaryState.UNAUTHORIZED else AuthorizationState.UNKNOWN
        compatibility = CompatibilityState.INCOMPATIBLE if error.state == HealthSummaryState.INCOMPATIBLE else CompatibilityState.UNKNOWN
        availability = AvailabilityState.DEGRADED if error.state == HealthSummaryState.DEGRADED else AvailabilityState.UNKNOWN
        evidence = ExecutionEvidence(mode=ExecutionMode.BLOCKED, observed_at=now, reason=safe_message)
        return IntegrationHealthSnapshot(
            integration_id=definition.integration_id,
            display_name=self._redactor.redact_text(definition.display_name),
            summary_state=error.state,
            connection=connection,
            authorization=authorization,
            compatibility=compatibility,
            availability=availability,
            activity=ActivityState.IDLE,
            observed_at=now,
            expires_at=now + timedelta(seconds=1),
            queue=QueueSnapshot(depth=0, running=0),
            circuit=circuit,
            reason_code=reason_code,
            safe_reason=safe_message,
            recommended_actions=self._actions(
                safe_message,
                circuit_open=circuit.state == CircuitState.OPEN,
            ),
            is_current=False,
            live_actions_enabled=False,
            evidence=evidence,
        )

    def _circuit_open(
        self,
        definition: IntegrationDefinition,
        now: datetime,
        circuit: CircuitSnapshot,
        retry_at: datetime,
    ) -> IntegrationHealthSnapshot:
        reason = "连续探测失败，熔断器已打开；可在 %s 后重试。" % retry_at.isoformat().replace("+00:00", "Z")
        return self._adapter_error(
            definition,
            now,
            circuit,
            AdapterError("CIRCUIT_OPEN", reason, HealthSummaryState.DEGRADED, True),
        )
