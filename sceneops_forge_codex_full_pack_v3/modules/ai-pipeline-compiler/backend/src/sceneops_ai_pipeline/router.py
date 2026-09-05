"""Typed HTTP boundary. Requests never grant themselves execution capabilities."""
import asyncio
from fastapi import APIRouter, HTTPException, Query, Request
from sceneops_harness import PipelineRun, HarnessEvent, DistilledWorkflow
from sceneops_ai_agents import agent_catalog
from sceneops_ai_routing import ModelRouter, ModelProfile, ModelProfileUpdate, ModelTier
from .schemas import (HarnessCatalog, HarnessAPIError, PipelineProposal, PlanningRequest,
    StartRequest, RunAction, RunObservation, RecoveryResponse, TitleRequest)


async def connected_request(request, operation):
    task = asyncio.create_task(asyncio.wait_for(operation, timeout=120))
    try:
        while not task.done():
            if await request.is_disconnected():
                raise asyncio.CancelledError()
            await asyncio.wait({task}, timeout=0.15)
        return await task
    except TimeoutError as error:
        raise HTTPException(504, "计划请求超过 120 秒，已取消。可检查配置后手动重试。") from error
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def create_router(service):
    router = APIRouter(prefix="/api/harness", tags=["ai-harness"],
        responses={400: {"model": HarnessAPIError}, 404: {"model": HarnessAPIError},
            409: {"model": HarnessAPIError}, 503: {"model": HarnessAPIError}})

    @router.get("/catalog", response_model=HarnessCatalog)
    def catalog():
        service.refresh_provider()
        settings = service.provider.settings()
        return HarnessCatalog(capabilities=service.registry.list(), connectors=service.registry.connectors.list(), agents=agent_catalog(),
            model_profiles=ModelRouter(service.provider).profiles(), model_provider=settings.provider, default_model=settings.model)

    @router.put('/model-profiles/{tier}', response_model=ModelProfile)
    def profile(tier: ModelTier, body: ModelProfileUpdate):
        return ModelRouter(service.provider).save_profile(tier, body.model)

    @router.post("/proposals", response_model=PipelineProposal)
    async def propose(body: PlanningRequest, request: Request):
        return await connected_request(request, service.propose(body))

    @router.get("/projects/{project_id}/proposals", response_model=list[PipelineProposal])
    def proposals(project_id: str):
        service.authority(project_id)
        return service.records.list(project_id, "proposal", PipelineProposal)

    @router.get("/projects/{project_id}/proposals/{proposal_id}", response_model=PipelineProposal)
    def proposal(project_id: str, proposal_id: str):
        service.authority(project_id)
        return service.records.proposal(project_id, proposal_id)

    @router.post("/projects/{project_id}/proposals/{proposal_id}/runs", response_model=PipelineRun)
    async def start(project_id: str, proposal_id: str, body: StartRequest):
        return service.start_proposal(project_id, proposal_id, body.request_id)

    @router.get("/projects/{project_id}/runs", response_model=list[PipelineRun])
    def runs(project_id: str):
        service.authority(project_id)
        return service.runtime.list(project_id)

    @router.get("/projects/{project_id}/runs/{run_id}", response_model=PipelineRun)
    def run(project_id: str, run_id: str):
        service.authority(project_id)
        return service.runtime.get(project_id, run_id)

    @router.get("/projects/{project_id}/runs/{run_id}/events", response_model=list[HarnessEvent])
    def events(project_id: str, run_id: str, after: int = Query(default=0, ge=0)):
        service.authority(project_id)
        return service.runtime.events(project_id, run_id, after=after)

    @router.post("/projects/{project_id}/runs/{run_id}/actions", response_model=PipelineRun)
    async def action(project_id: str, run_id: str, body: RunAction):
        authority = service.authority(project_id)
        service.refresh_provider()
        if body.action == "cancel":
            return service.runtime.cancel(project_id, run_id, authority)
        if body.action == "retry":
            value = service.runtime.retry(project_id, run_id, authority)
            service.launch(project_id, run_id, authority)
            return value
        if body.action in {"approve", "approve_rollback"}:
            if not body.step_id:
                raise HTTPException(422, "请选择要审批的步骤。")
            value = service.runtime.approve(project_id, run_id, body.step_id, authority,
                action="rollback" if body.action == "approve_rollback" else "execute",
                inspection_confirmed=body.inspection_confirmed)
            if body.action == "approve":
                service.launch(project_id, run_id, authority)
            return value
        return await service.runtime.rollback(project_id, run_id, authority)

    @router.get("/projects/{project_id}/runs/{run_id}/observation", response_model=RunObservation)
    def observation(project_id: str, run_id: str):
        return service.observation(project_id, run_id)

    @router.post("/projects/{project_id}/runs/{run_id}/recovery", response_model=RecoveryResponse)
    async def recovery(project_id: str, run_id: str, request: Request):
        value = await connected_request(request, service.recovery(project_id, run_id))
        return RecoveryResponse(proposal=value, executable=value.selected_action in {"retry", "abort"})

    @router.post("/projects/{project_id}/runs/{run_id}/distill", response_model=DistilledWorkflow)
    def distill(project_id: str, run_id: str, body: TitleRequest):
        return service.distill(project_id, run_id, body.title)

    @router.get("/projects/{project_id}/templates", response_model=list[DistilledWorkflow])
    def templates(project_id: str):
        service.authority(project_id)
        return service.records.workflows(project_id)

    return router
