import unittest
from datetime import datetime, timedelta, timezone

from observability import CorrelationContext, ExecutionMode

from integration_center import (
    ActivityState,
    AdapterError,
    AuthorizationState,
    AvailabilityState,
    CapabilityReport,
    CircuitState,
    CompatibilityPolicy,
    ConnectionState,
    ExecutionEvidence,
    EventActor,
    HealthProbe,
    HealthSummaryState,
    IntegrationDefinition,
    IntegrationGateway,
    QueueSnapshot,
    build_health_changed_event,
)


NOW = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
CONTEXT = CorrelationContext(
    project_id="prj_health",
    run_id="run_health",
    job_id="job_health",
    correlation_id="corr_health",
    causation_id="cmd_health",
)


class StaticAdapter:
    integration_id = "tool"

    def __init__(self, probe: HealthProbe, capabilities: CapabilityReport) -> None:
        self.probe = probe
        self.capabilities = capabilities
        self.health_calls = 0
        self.capability_calls = 0

    def health_check(self, context: CorrelationContext) -> HealthProbe:
        self.health_calls += 1
        return self.probe

    def capability_report(self, context: CorrelationContext) -> CapabilityReport:
        self.capability_calls += 1
        return self.capabilities


class FailingThenHealthyAdapter(StaticAdapter):
    def __init__(self, probe: HealthProbe, capabilities: CapabilityReport, failures: int) -> None:
        super().__init__(probe, capabilities)
        self.failures = failures

    def health_check(self, context: CorrelationContext) -> HealthProbe:
        self.health_calls += 1
        if self.health_calls <= self.failures:
            raise AdapterError("HOST_UNREACHABLE", "工具主机不可达。", HealthSummaryState.DEGRADED, True)
        return self.probe


def probe(
    connection: ConnectionState = ConnectionState.CONNECTED,
    authorization: AuthorizationState = AuthorizationState.AUTHORIZED,
    availability: AvailabilityState = AvailabilityState.AVAILABLE,
    activity: ActivityState = ActivityState.IDLE,
    mode: ExecutionMode = ExecutionMode.LIVE,
    expires_at: datetime = NOW + timedelta(minutes=1),
) -> HealthProbe:
    evidence = ExecutionEvidence(mode=mode, observed_at=NOW)
    return HealthProbe(
        integration_id="tool",
        display_name="Tool",
        connection=connection,
        authorization=authorization,
        availability=availability,
        activity=activity,
        observed_at=NOW,
        expires_at=expires_at,
        last_seen_at=NOW,
        tool_version="4.3.2",
        adapter_version="0.1.0",
        queue=QueueSnapshot(depth=0, running=0),
        evidence=evidence,
    )


def capabilities(version: str = "4.3.2", capability_ids=None) -> CapabilityReport:
    return CapabilityReport(
        integration_id="tool",
        tool_version=version,
        adapter_version="0.1.0",
        observed_at=NOW,
        capability_ids=capability_ids or ["scene.scan"],
        allowlisted_command_ids=["tool.scene.scan"],
        evidence=ExecutionEvidence(mode=ExecutionMode.LIVE, observed_at=NOW),
    )


def gateway(adapter, policy: CompatibilityPolicy = CompatibilityPolicy()) -> IntegrationGateway:
    target = IntegrationGateway([IntegrationDefinition("tool", "Tool", policy)], failure_threshold=2)
    target.register(adapter)
    return target


class IntegrationHealthTests(unittest.TestCase):
    def test_all_required_summary_states(self) -> None:
        cases = [
            (probe(), capabilities(), NOW, HealthSummaryState.CONNECTED),
            (probe(connection=ConnectionState.DISCONNECTED), capabilities(), NOW, HealthSummaryState.DISCONNECTED),
            (probe(availability=AvailabilityState.DEGRADED), capabilities(), NOW, HealthSummaryState.DEGRADED),
            (
                probe(),
                capabilities(capability_ids=["other"]),
                NOW,
                HealthSummaryState.INCOMPATIBLE,
            ),
            (probe(activity=ActivityState.BUSY), capabilities(), NOW, HealthSummaryState.BUSY),
            (probe(authorization=AuthorizationState.UNAUTHORIZED), capabilities(), NOW, HealthSummaryState.UNAUTHORIZED),
            (probe(expires_at=NOW + timedelta(seconds=1)), capabilities(), NOW + timedelta(seconds=2), HealthSummaryState.UNKNOWN),
        ]
        for health_probe, report, observed_now, expected in cases:
            with self.subTest(state=expected):
                policy = CompatibilityPolicy(required_capability_ids=("scene.scan",))
                result = gateway(StaticAdapter(health_probe, report), policy).query_health("tool", CONTEXT, observed_now)
                self.assertEqual(expected, result.summary_state)
                self.assertGreaterEqual(len(result.recommended_actions), 2)

    def test_version_and_capability_mismatch_explain_unavailability(self) -> None:
        policy = CompatibilityPolicy(minimum_version="4.4.0", required_capability_ids=("asset.export",))
        result = gateway(StaticAdapter(probe(), capabilities()), policy).query_health("tool", CONTEXT, NOW)

        self.assertEqual(HealthSummaryState.INCOMPATIBLE, result.summary_state)
        self.assertFalse(result.live_actions_enabled)
        self.assertEqual("CAPABILITY_OR_VERSION_MISMATCH", result.reason_code)
        self.assertIn("缺少能力", result.safe_reason)

    def test_mock_probe_never_enables_live_actions(self) -> None:
        mock_probe = probe(mode=ExecutionMode.MOCK)
        mock_report = capabilities().model_copy(
            update={"evidence": ExecutionEvidence(mode=ExecutionMode.MOCK, observed_at=NOW)}
        )
        result = gateway(StaticAdapter(mock_probe, mock_report)).query_health("tool", CONTEXT, NOW)

        self.assertEqual(HealthSummaryState.CONNECTED, result.summary_state)
        self.assertFalse(result.live_actions_enabled)
        self.assertEqual(ExecutionMode.MOCK, result.evidence.mode)

    def test_mixed_probe_and_capability_modes_are_unknown_not_live(self) -> None:
        cached_report = capabilities().model_copy(
            update={
                "evidence": ExecutionEvidence(
                    mode=ExecutionMode.CACHED,
                    observed_at=NOW,
                    source_run_id="run_cached_capabilities",
                )
            }
        )
        result = gateway(StaticAdapter(probe(), cached_report)).query_health("tool", CONTEXT, NOW)
        self.assertEqual(HealthSummaryState.UNKNOWN, result.summary_state)
        self.assertEqual("EVIDENCE_MODE_MISMATCH", result.reason_code)
        self.assertFalse(result.live_actions_enabled)

    def test_future_probe_is_not_current(self) -> None:
        future = NOW + timedelta(seconds=20)
        future_evidence = ExecutionEvidence(mode=ExecutionMode.LIVE, observed_at=future)
        future_probe = probe().model_copy(
            update={
                "observed_at": future,
                "expires_at": future + timedelta(minutes=1),
                "evidence": future_evidence,
            }
        )
        future_report = capabilities().model_copy(
            update={"observed_at": future, "evidence": future_evidence}
        )
        result = gateway(StaticAdapter(future_probe, future_report)).query_health("tool", CONTEXT, NOW)
        self.assertEqual(HealthSummaryState.UNKNOWN, result.summary_state)
        self.assertFalse(result.is_current)

    def test_stale_capability_report_never_enables_live_actions(self) -> None:
        long_probe = probe(expires_at=NOW + timedelta(minutes=10))
        result = gateway(StaticAdapter(long_probe, capabilities())).query_health(
            "tool",
            CONTEXT,
            NOW + timedelta(minutes=6),
        )
        self.assertEqual(HealthSummaryState.UNKNOWN, result.summary_state)
        self.assertEqual("CAPABILITY_EVIDENCE_STALE", result.reason_code)
        self.assertFalse(result.live_actions_enabled)

    def test_adapter_safe_reason_is_redacted_at_the_boundary(self) -> None:
        unsafe_probe = probe().model_copy(
            update={"safe_reason": "token=raw-secret at /Users/alice/project/file"}
        )
        result = gateway(StaticAdapter(unsafe_probe, capabilities())).query_health("tool", CONTEXT, NOW)
        self.assertNotIn("raw-secret", result.safe_reason)
        self.assertNotIn("/Users/alice", result.safe_reason)

    def test_each_query_executes_a_fresh_probe(self) -> None:
        adapter = StaticAdapter(probe(), capabilities())
        target = gateway(adapter)
        target.query_health("tool", CONTEXT, NOW)
        target.query_health("tool", CONTEXT, NOW)
        self.assertEqual(2, adapter.health_calls)
        self.assertEqual(2, adapter.capability_calls)

    def test_health_change_event_preserves_envelope_and_run_job_ids(self) -> None:
        health = gateway(StaticAdapter(probe(), capabilities())).query_health("tool", CONTEXT, NOW)
        event = build_health_changed_event(
            event_id="evt_health",
            occurred_at=NOW,
            actor=EventActor(type="system", id="integration-center"),
            current=health,
            project_id=CONTEXT.project_id,
            run_id=CONTEXT.run_id,
            job_id=CONTEXT.job_id,
            correlation_id=CONTEXT.correlation_id,
            causation_id=CONTEXT.causation_id,
        )
        self.assertEqual("integration.health.changed", event.event_type)
        self.assertEqual("run_health", event.payload.run_id)
        self.assertEqual("job_health", event.payload.job_id)
        self.assertEqual("corr_health", event.correlation_id)
        self.assertEqual(ExecutionMode.LIVE, event.mode)

    def test_missing_adapter_is_unknown_and_blocked(self) -> None:
        target = IntegrationGateway([IntegrationDefinition("tool", "Tool")])
        result = target.query_health("tool", CONTEXT, NOW)
        self.assertEqual(HealthSummaryState.UNKNOWN, result.summary_state)
        self.assertEqual(ExecutionMode.BLOCKED, result.evidence.mode)
        self.assertFalse(result.live_actions_enabled)

    def test_circuit_opens_blocks_and_recovers_through_half_open_probe(self) -> None:
        adapter = FailingThenHealthyAdapter(probe(), capabilities(), failures=2)
        target = IntegrationGateway(
            [IntegrationDefinition("tool", "Tool")],
            failure_threshold=2,
            cooldown=timedelta(seconds=10),
        )
        target.register(adapter)

        first = target.query_health("tool", CONTEXT, NOW)
        second = target.query_health("tool", CONTEXT, NOW + timedelta(seconds=1))
        blocked = target.query_health("tool", CONTEXT, NOW + timedelta(seconds=2))
        blocked_call_count = adapter.health_calls
        recovered = target.query_health("tool", CONTEXT, NOW + timedelta(seconds=12))

        self.assertEqual(CircuitState.CLOSED, first.circuit.state)
        self.assertEqual(CircuitState.OPEN, second.circuit.state)
        self.assertEqual("CIRCUIT_OPEN", blocked.reason_code)
        self.assertEqual(2, blocked_call_count)
        self.assertEqual(HealthSummaryState.CONNECTED, recovered.summary_state)
        self.assertEqual(CircuitState.CLOSED, recovered.circuit.state)
        self.assertEqual(3, adapter.health_calls)


if __name__ == "__main__":
    unittest.main()
