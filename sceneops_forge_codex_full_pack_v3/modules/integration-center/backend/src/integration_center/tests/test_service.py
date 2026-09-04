import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from observability import (
    CorrelationContext,
    ExecutionMode,
    LogLevel,
    ObservabilityGateway,
    StructuredLogEvent,
)

from integration_center import (
    ActivityState,
    AuthorizationState,
    AvailabilityState,
    CachedEvidence,
    CapabilityReport,
    CompatibilityPolicy,
    ConnectionState,
    ExecutionEvidence,
    HealthProbe,
    HealthSummaryState,
    IntegrationCenterService,
    IntegrationDefinition,
    IntegrationGateway,
    JudgeModeHealthSummary,
    QueueSnapshot,
    RecommendedAction,
    WorkerLifecycle,
    WorkerSnapshot,
)


MODULE_ROOT = Path(__file__).resolve().parents[4]
NOW = datetime(2026, 9, 4, 0, 1, tzinfo=timezone.utc)
CONTEXT = CorrelationContext(
    project_id="prj_judge",
    run_id="run_judge",
    job_id="job_judge",
    correlation_id="corr_judge",
    causation_id="cmd_judge",
)


class FixtureAdapter:
    def __init__(self, health: HealthProbe, capabilities: CapabilityReport) -> None:
        self.integration_id = health.integration_id
        self.health = health
        self.capabilities = capabilities

    def health_check(self, context):
        return self.health

    def capability_report(self, context):
        return self.capabilities


class FixtureWorkers:
    def __init__(self, items):
        self.items = items

    def list_workers(self, project_id):
        return self.items


def live_adapter(integration_id: str, connection=ConnectionState.CONNECTED) -> FixtureAdapter:
    observed = NOW
    evidence = ExecutionEvidence(mode=ExecutionMode.LIVE, observed_at=observed)
    health = HealthProbe(
        integration_id=integration_id,
        display_name=integration_id.title(),
        connection=connection,
        authorization=AuthorizationState.AUTHORIZED,
        availability=AvailabilityState.AVAILABLE,
        activity=ActivityState.IDLE,
        observed_at=observed,
        expires_at=observed + timedelta(minutes=1),
        last_seen_at=observed,
        tool_version="1.0.0",
        adapter_version="0.1.0",
        queue=QueueSnapshot(depth=0, running=0),
        safe_reason="工具已断开。" if connection == ConnectionState.DISCONNECTED else None,
        evidence=evidence,
    )
    capabilities = CapabilityReport(
        integration_id=integration_id,
        tool_version="1.0.0",
        adapter_version="0.1.0",
        observed_at=observed,
        capability_ids=["health.read"],
        allowlisted_command_ids=["health.read"],
        evidence=evidence,
    )
    return FixtureAdapter(health, capabilities)


class IntegrationCenterServiceTests(unittest.TestCase):
    def test_named_tool_and_worker_fixtures_are_valid_and_mock(self) -> None:
        health_payload = json.loads(
            (MODULE_ROOT / "contracts/examples/integration-health.mock.json").read_text(encoding="utf-8")
        )
        worker_payload = json.loads(
            (MODULE_ROOT / "contracts/examples/workers.mock.json").read_text(encoding="utf-8")
        )
        integrations = health_payload["integrations"]
        names = {item["probe"]["integration_id"] for item in integrations}
        self.assertEqual({"blender", "unity", "comfyui", "git", "artifact-store"}, names)
        for item in integrations:
            self.assertEqual(ExecutionMode.MOCK, HealthProbe.model_validate(item["probe"]).evidence.mode)
            self.assertEqual(ExecutionMode.MOCK, CapabilityReport.model_validate(item["capabilities"]).evidence.mode)
        workers = [WorkerSnapshot.model_validate(item) for item in worker_payload["workers"]]
        self.assertEqual(3, len(workers))
        self.assertTrue(all(item.evidence.mode == ExecutionMode.MOCK for item in workers))

    def test_details_include_only_correlated_tool_logs(self) -> None:
        integration_gateway = IntegrationGateway([IntegrationDefinition("blender", "Blender")])
        integration_gateway.register(live_adapter("blender"))
        logs = ObservabilityGateway()
        logs.publish_log(
            StructuredLogEvent(
                event_id="log_blender",
                emitted_at=NOW,
                level=LogLevel.INFO,
                source_module="asset-factory",
                source_tool="blender",
                message="export ready",
                context=CONTEXT,
                fields={"operation": "asset.export"},
                mode=ExecutionMode.MOCK,
            )
        )
        service = IntegrationCenterService(integration_gateway, logs, FixtureWorkers([]))

        details = service.details("blender", CONTEXT, NOW)

        self.assertEqual("blender", details.health.integration_id)
        self.assertEqual(["log_blender"], [item.event_id for item in details.recent_logs])

    def test_judge_mode_explains_cached_fallback_and_keeps_live_step(self) -> None:
        integration_gateway = IntegrationGateway(
            [IntegrationDefinition("blender", "Blender"), IntegrationDefinition("unity", "Unity")]
        )
        integration_gateway.register(live_adapter("blender"))
        integration_gateway.register(live_adapter("unity", ConnectionState.DISCONNECTED))
        service = IntegrationCenterService(
            integration_gateway,
            ObservabilityGateway(),
            FixtureWorkers([]),
            cached_evidence=[
                CachedEvidence(
                    project_id="prj_judge",
                    integration_id="unity",
                    source_run_id="run_unity_real_20260903",
                    observed_at=NOW - timedelta(days=1),
                    expires_at=NOW + timedelta(days=1),
                )
            ],
        )

        summary: JudgeModeHealthSummary = service.judge_summary(CONTEXT, NOW)

        self.assertEqual(ExecutionMode.CACHED, summary.mode)
        self.assertTrue(summary.live_step_available)
        unity = next(item for item in summary.fallbacks if item.integration_id == "unity")
        self.assertTrue(unity.active)
        self.assertEqual(ExecutionMode.CACHED, unity.evidence_mode)
        self.assertEqual("run_unity_real_20260903", unity.source_run_id)
        self.assertIn("缓存", summary.headline)

    def test_cached_fallback_is_project_scoped_and_freshness_bounded(self) -> None:
        integration_gateway = IntegrationGateway([IntegrationDefinition("unity", "Unity")])
        service = IntegrationCenterService(
            integration_gateway,
            ObservabilityGateway(),
            FixtureWorkers([]),
            cached_evidence=[
                CachedEvidence(
                    project_id="prj_other",
                    integration_id="unity",
                    source_run_id="run_other",
                    observed_at=NOW - timedelta(days=2),
                    expires_at=NOW - timedelta(days=1),
                )
            ],
        )
        summary = service.judge_summary(CONTEXT, NOW)
        self.assertEqual(ExecutionMode.BLOCKED, summary.mode)
        self.assertIsNone(summary.fallbacks[0].source_run_id)

    def test_judge_mode_is_blocked_without_live_cached_or_mock_evidence(self) -> None:
        integration_gateway = IntegrationGateway([IntegrationDefinition("unity", "Unity")])
        service = IntegrationCenterService(
            integration_gateway,
            ObservabilityGateway(),
            FixtureWorkers([]),
        )
        summary = service.judge_summary(CONTEXT, NOW)
        self.assertEqual(ExecutionMode.BLOCKED, summary.mode)
        self.assertFalse(summary.live_step_available)

    def test_restart_is_guidance_not_an_unapproved_tool_command(self) -> None:
        integration_gateway = IntegrationGateway([IntegrationDefinition("unity", "Unity")])
        service = IntegrationCenterService(integration_gateway, ObservabilityGateway(), FixtureWorkers([]))
        guidance = service.restart_guidance("worker_unity_01")
        self.assertFalse(guidance.available)
        self.assertTrue(guidance.requires_approval)
        self.assertIsNone(guidance.command_id)
        self.assertGreaterEqual(len(guidance.steps), 3)

    def test_worker_freshness_is_server_derived_and_stale_control_is_disabled(self) -> None:
        worker = WorkerSnapshot(
            worker_id="worker_stale",
            integration_id="unity",
            display_name="Unity Worker /Users/operator/private",
            lifecycle=WorkerLifecycle.ONLINE,
            health_state=HealthSummaryState.BUSY,
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=1),
            is_current=True,
            last_heartbeat_at=NOW,
            worker_version="1.0.0",
            capability_ids=["build.run"],
            queue=QueueSnapshot(depth=0, running=1),
            recommended_actions=[
                RecommendedAction(command_id="job.cancel", label="Cancel", available=True)
            ],
            evidence=ExecutionEvidence(mode=ExecutionMode.LIVE, observed_at=NOW),
        )
        service = IntegrationCenterService(
            IntegrationGateway([IntegrationDefinition("unity", "Unity")]),
            ObservabilityGateway(),
            FixtureWorkers([worker]),
        )

        result = service.list_workers("prj_judge", NOW + timedelta(minutes=2))[0]

        self.assertFalse(result.is_current)
        self.assertFalse(result.recommended_actions[0].available)
        self.assertIn("已过期", result.recommended_actions[0].unavailable_reason)
        self.assertNotIn("/Users/operator", result.display_name)


if __name__ == "__main__":
    unittest.main()
