"""Isolated deterministic data; never invokes an external tool or reads credentials."""

import json
from datetime import datetime, timezone
from pathlib import Path

from observability import (ArtifactLink, CorrelationContext, ExecutionMode, LogLevel,
    ObservabilityGateway, ProgressEvent, ProgressState, StructuredLogEvent)

from .adapters import IntegrationDefinition, IntegrationGateway
from .schemas import CapabilityReport, HealthProbe, WorkerSnapshot
from .service import IntegrationCenterService
from .workbench import DemoProject, OperationsWorkbench


FIXTURE_TIME = datetime(2026, 9, 4, 0, 1, tzinfo=timezone.utc)
EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples"


class MockIntegrationAdapter:
    def __init__(self, item):
        self.probe = HealthProbe.model_validate(item["probe"])
        self.capabilities = CapabilityReport.model_validate(item["capabilities"])
        self.integration_id = self.probe.integration_id

    def health_check(self, context):
        return self.probe

    def capability_report(self, context):
        return self.capabilities


class MockWorkers:
    def __init__(self, project_id="prj_home_mock"):
        self.project_id = project_id
        payload = json.loads((EXAMPLES / "workers.mock.json").read_text())
        self.items = [WorkerSnapshot.model_validate(item) for item in payload["workers"]]

    def list_workers(self, project_id):
        return self.items if project_id == self.project_id else []


def create_demo_workbench(project_id: str | None = None, sample_id: str | None = None) -> OperationsWorkbench:
    payload = json.loads((EXAMPLES / "integration-health.mock.json").read_text())
    adapters = [MockIntegrationAdapter(item) for item in payload["integrations"]]
    gateway = IntegrationGateway([IntegrationDefinition(item.integration_id, item.probe.display_name)
                                  for item in adapters])
    for adapter in adapters:
        gateway.register(adapter)
    logs = ObservabilityGateway(max_records=500)
    projects = [DemoProject(project_id="prj_home_mock", title="归家之路 · 演示项目"),
                DemoProject(project_id="prj_warehouse_mock", title="仓库逃脱 · 演示项目")]
    if project_id:
        title = "仓库逃生 · Mock" if sample_id == "warehouse-escape" else "归家之路 · Mock"
        projects = [DemoProject(project_id=project_id, title=title)]
    rows = [
        ("unity", "job_unity_build_mock_01", "corr_judge_mock_01", "info", "项目扫描完成，已保留稳定对象 ID。", "succeeded", 1.0),
        ("unity", "job_unity_build_mock_01", "corr_judge_mock_01", "info", "构建演示停留在资源准备阶段，进度固定为 45%。", "running", 0.45),
        ("comfyui", "job_render_mock", "corr_render_mock", "error", "队列中有 4 个任务，但没有活跃 Worker。请查看恢复说明。", "failed", 0.2),
        ("blender", "job_export_mock", "corr_export_mock", "info", "资产导出演示完成，可打开本地证据。", "succeeded", 1.0),
        ("git", "job_review_mock", "corr_review_mock", "warning", "凭据脱敏样例 token=demo-secret cwd:/Users/demo/private，远端未授权。", "failed", 0.0),
    ]
    for index, (tool, job, correlation, level, message, state, progress) in enumerate(rows):
        context = CorrelationContext(project_id=projects[0].project_id, run_id="run_" + job,
            job_id=job, correlation_id=correlation, causation_id="cmd_demo_" + str(index))
        logs.publish_log(StructuredLogEvent(event_id="log_demo_" + str(index), emitted_at=FIXTURE_TIME,
            level=LogLevel(level), source_module="integration-center", source_tool=tool,
            message=message, context=context, fields={"operation": tool + ".demo", "status": state},
            artifact_links=[ArtifactLink(artifact_id="evidence_" + job, label="查看本地证据", media_type="application/json")],
            mode=ExecutionMode.MOCK))
        logs.publish_progress(ProgressEvent(event_id="progress_demo_" + str(index), occurred_at=FIXTURE_TIME,
            source_module="integration-center", state=ProgressState(state), progress=progress,
            message=message, context=context, mode=ExecutionMode.MOCK))
    logs.publish_log(StructuredLogEvent(event_id="log_warehouse", emitted_at=FIXTURE_TIME,
        level=LogLevel.INFO, source_module="integration-center", source_tool="blender",
        message="仓库逃脱演示记录：与归家之路项目隔离。", mode=ExecutionMode.MOCK,
        context=CorrelationContext(project_id=projects[-1].project_id, job_id="job_warehouse",
            run_id="run_warehouse", correlation_id="corr_warehouse", causation_id="cmd_warehouse"),
        artifact_links=[ArtifactLink(artifact_id="evidence_warehouse", label="仓库演示记录")]))
    return OperationsWorkbench(IntegrationCenterService(gateway, logs, MockWorkers(project_id or "prj_home_mock")), logs, projects, FIXTURE_TIME)


def create_empty_workbench(project_id: str, title: str) -> OperationsWorkbench:
    logs = ObservabilityGateway(max_records=500)

    class EmptyWorkers:
        def list_workers(self, project_id):
            return []

    definitions = [IntegrationDefinition(identity, title) for identity, title in (
        ("blender", "Blender"), ("unity", "Unity"), ("comfyui", "ComfyUI"),
        ("git", "Git"), ("artifact-store", "Artifact Store"))]
    # Declared capabilities are not connected adapters. Reads report
    # ADAPTER_NOT_REGISTERED/blocked without executing a probe.
    service = IntegrationCenterService(IntegrationGateway(definitions), logs, EmptyWorkers())
    return OperationsWorkbench(service, logs, [DemoProject(project_id=project_id, title=title)],
        datetime.now(timezone.utc), mode="planned")
