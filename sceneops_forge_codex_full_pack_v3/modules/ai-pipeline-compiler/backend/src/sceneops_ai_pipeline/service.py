"""Goal-to-plan composition. User submission is distinct from actual execution."""
import asyncio
import json
import logging
from sceneops_harness import (AgentTask, Authority, HarnessRuntime, PipelineDefinition,
    PipelineStage, PipelineStep, DistilledWorkflow)
from sceneops_ai_provider import ProviderService
from sceneops_ai_intent import IntentCompiler
from sceneops_ai_context import ContextEngine
from sceneops_ai_routing import ModelRouter
from sceneops_ai_agents import agent_catalog
from sceneops_ai_observer import observe_run
from sceneops_ai_recovery import propose_recovery
from sceneops_ai_distiller import distill_run
from .capabilities import create_registry
from .repository import ProposalRepository
from .schemas import PipelineProposal, PlanOutline, RunObservation


class PlanningService:
    def __init__(self, database_path, workspace):
        self.workspace = workspace
        self.provider = ProviderService(database_path)
        self.registry = create_registry(workspace, self.provider)
        self.runtime = HarnessRuntime(database_path, self.registry)
        self.records = ProposalRepository(database_path)
        self.tasks: dict[str, asyncio.Task] = {}

    def authority(self, project_id, actor_id="usr_local_workspace"):
        if not self.workspace.exists(project_id):
            raise KeyError("项目不存在，请先创建或选择本地项目。")
        return Authority(project_id=project_id, actor_id=actor_id,
            permissions=["harness:read", "harness:plan", "harness:approve"],
            allowed_capabilities=[item.id for item in self.registry.list()])

    def refresh_provider(self):
        from sceneops_harness import ConnectorDefinition
        self.registry.connectors.register(ConnectorDefinition(id="ai", title="当前 AI Provider",
            status="available" if self.provider.provider_available() else "blocked",
            reason="配置状态，不代表真实调用已验证。"))

    async def propose(self, request):
        authority = self.authority(request.project_id)
        self.refresh_provider()
        intent, missing = await IntentCompiler(self.provider).compile(request.project_id,
            request.goal, request.constraints, request.budget)
        context = ContextEngine(self.workspace).build(intent, request.module_ids, request.selection)
        catalog = [item.model_dump(mode="json") for item in self.registry.list()]
        prompt = ("你是 SceneOps Pipeline 规划器。按目标生成可审阅中文计划，不执行。"
            "仅可引用目录中的 capability_id；不要发明ID，不用任何shell/Python/C#脚本。"
            "inputs必须符合能力input_schema。依赖只引用返回的step id。"
            "只有 ai.agent.assess 使用 agent_role（专家目录中的role），objective描述分析目标。"
            "外部能力不可用时仍如实列出必需步骤和缺失条件，不用AI文字建议替代真实生产冒充完成。"
            "本次上下文由服务端绑定，agent inputs无需重复context。返回schema JSON：\n"
            + json.dumps({"intent": intent.model_dump(mode="json"), "context": context.model_dump(mode="json"),
                "capabilities": catalog, "agents": [a.model_dump(mode="json") for a in agent_catalog()]}, ensure_ascii=False))
        outline = PlanOutline.model_validate(await self.provider.structured(prompt,
            PlanOutline.model_json_schema(), purpose="pipeline"))
        routing = []
        stages = []
        for stage in outline.stages:
            steps = []
            for item in stage.steps:
                step = PipelineStep(id=item.id, title=item.title, capability_id=item.capability_id,
                    depends_on=item.depends_on, inputs=item.inputs, failure_strategy="ask_human")
                if item.capability_id == "ai.agent.assess":
                    role = item.agent_role or "producer"
                    decision = ModelRouter(self.provider).route(role)
                    routing.append(decision)
                    step.kind, step.model_routing = "agent", decision
                    step.inputs = {"objective": item.objective or item.title, "context": context.model_dump(mode="json")}
                    step.agent_task = AgentTask(agent_role=role, objective=item.objective or item.title,
                        context_refs=[ref.ref.id for ref in context.items], allowed_capabilities=[item.capability_id],
                        constraints=intent.constraints, budget=request.budget)
                steps.append(step)
            stages.append(PipelineStage(id=stage.id, title=stage.title, steps=steps))
        definition = PipelineDefinition(project_id=request.project_id, intent_id=intent.id,
            title=outline.title, stages=stages, budget=request.budget,
            context_refs=[item.ref.id for item in context.items])
        proposal = PipelineProposal(project_id=request.project_id, intent=intent, context=context,
            definition=definition, validation=self.runtime.validate(definition, authority), routing=routing,
            missing_facts=list(dict.fromkeys([*missing, *outline.missing_facts])))
        return self.records.save(request.project_id, "proposal", proposal)

    def launch(self, project_id, run_id, authority):
        if run_id in self.tasks:
            raise ValueError("此运行正在处理，请等待或取消。")
        task = asyncio.create_task(self.runtime.start(project_id, run_id, authority))
        self.tasks[run_id] = task
        def finished(value):
            self.tasks.pop(run_id, None)
            if not value.cancelled() and value.exception():
                logging.getLogger("sceneops.harness").error("Run worker failed: %s", type(value.exception()).__name__)
        task.add_done_callback(finished)

    def start_proposal(self, project_id, proposal_id, request_id):
        authority = self.authority(project_id)
        self.refresh_provider()
        proposal = self.records.proposal(project_id, proposal_id)
        run = self.runtime.submit(proposal.definition, authority, request_id)
        if run.state == "queued" and run.id not in self.tasks:
            self.launch(project_id, run.id, authority)
        return run

    def observation(self, project_id, run_id):
        self.authority(project_id)
        evaluations, failures = observe_run(self.runtime.get(project_id, run_id))
        return RunObservation(evaluations=evaluations, failures=failures)

    async def recovery(self, project_id, run_id):
        observation = self.observation(project_id, run_id)
        if not observation.failures:
            raise ValueError("运行中没有可供诊断的失败事实。")
        run = self.runtime.get(project_id, run_id)
        failure = observation.failures[0]
        step = next(item for item in run.step_runs if item.step_id == failure.step_id)
        proposal = await propose_recovery(self.provider, failure, len(step.attempts), run.definition.budget.max_attempts_per_step)
        return self.records.save(project_id, "recovery", proposal)

    def distill(self, project_id, run_id, title):
        self.authority(project_id)
        value = distill_run(self.runtime.get(project_id, run_id), title)
        return self.records.save(project_id, "workflow", value)

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
