"""Read-only operations workbench over public integration and log services."""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from observability import CorrelationContext, LogQuery, ObservabilityGateway, ProgressEvent, StructuredLogEvent

from .contract_validation import STABLE_ID_PATTERN
from .schemas import ContractModel, IntegrationHealthSnapshot, WorkerSnapshot, JudgeModeHealthSummary
from .service import IntegrationCenterService


class DemoProject(ContractModel):
    project_id: str
    title: str


class OperationsSnapshot(ContractModel):
    mode: Literal["mock"] = "mock"
    fixture_time: datetime
    projects: list[DemoProject]
    integrations: list[IntegrationHealthSnapshot]
    workers: list[WorkerSnapshot]
    progress: list[ProgressEvent]
    logs: list[StructuredLogEvent]
    total_logs: int
    job_ids: list[str]
    correlation_ids: list[str]
    summary: JudgeModeHealthSummary


class LocalEvidence(ContractModel):
    artifact_id: str
    mode: Literal["mock"] = "mock"
    title: str
    description: str
    records: list[StructuredLogEvent]


class OperationsWorkbench:
    def __init__(self, service: IntegrationCenterService, logs: ObservabilityGateway,
                 projects: list[DemoProject], fixture_time: datetime):
        self.service = service
        self.logs = logs
        self.projects = projects
        self.fixture_time = fixture_time

    def authorize_project(self, permission: str, project_id: str) -> None:
        if project_id not in {project.project_id for project in self.projects}:
            raise HTTPException(404, "未找到演示项目。")

    def context(self, project_id: str) -> CorrelationContext:
        self.authorize_project("integration:read", project_id)
        return CorrelationContext(project_id=project_id, correlation_id="corr_workbench",
                                  causation_id="cmd_workbench_read")

    def snapshot(self, project_id: str, job_id: Optional[str], correlation_id: Optional[str],
                 text: Optional[str]) -> OperationsSnapshot:
        context = self.context(project_id)
        all_logs = self.logs.query_logs(LogQuery(project_id=project_id, limit=2000))
        page = self.logs.query_logs(LogQuery(project_id=project_id, job_id=job_id,
            correlation_id=correlation_id, text=text, limit=200))
        events = self.logs.events_after(project_id, None).events
        progress = [event for event in events if isinstance(event, ProgressEvent)
                    and (not job_id or event.context.job_id == job_id)
                    and (not correlation_id or event.context.correlation_id == correlation_id)]
        workers = self.service.list_workers(project_id, self.fixture_time)
        if job_id or correlation_id:
            workers = [worker for worker in workers if worker.current_job
                       and (not job_id or worker.current_job.job_id == job_id)
                       and (not correlation_id or worker.current_job.correlation_id == correlation_id)]
        summary = self.service.judge_summary(context, self.fixture_time)
        return OperationsSnapshot(fixture_time=self.fixture_time, projects=self.projects,
            integrations=summary.integrations, workers=workers, summary=summary,
            progress=progress, logs=page.items, total_logs=page.total,
            job_ids=sorted({log.context.job_id for log in all_logs.items if log.context.job_id}),
            correlation_ids=sorted({log.context.correlation_id for log in all_logs.items}))

    def evidence(self, project_id: str, artifact_id: str) -> LocalEvidence:
        self.context(project_id)
        records = [log for log in self.logs.query_logs(LogQuery(project_id=project_id, limit=2000)).items
                   if any(link.artifact_id == artifact_id for link in log.artifact_links)]
        if not records:
            raise HTTPException(404, "该项目中没有此证据。")
        return LocalEvidence(artifact_id=artifact_id, title="本地演示证据",
            description="来自隔离 Mock 数据的已脱敏记录；未执行真实构建或渲染。", records=records)


def create_workbench_router(workbench: OperationsWorkbench, require_permission) -> APIRouter:
    router = APIRouter(prefix="/api/v1/integration-ops", tags=["integration-ops"],
                       dependencies=[Depends(require_permission("integration:read"))])

    @router.get("/snapshot", response_model=OperationsSnapshot)
    def snapshot(project_id: str = Query(pattern=STABLE_ID_PATTERN),
                 job_id: Optional[str] = Query(default=None, pattern=STABLE_ID_PATTERN),
                 correlation_id: Optional[str] = Query(default=None, pattern=STABLE_ID_PATTERN),
                 text: Optional[str] = Query(default=None, max_length=200)):
        return workbench.snapshot(project_id, job_id, correlation_id, text)

    @router.get("/evidence/{artifact_id}", response_model=LocalEvidence)
    def evidence(artifact_id: str, project_id: str = Query(pattern=STABLE_ID_PATTERN)):
        return workbench.evidence(project_id, artifact_id)

    return router
