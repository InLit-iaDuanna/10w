"""Public-module capabilities; unverified external paths are declarations, not jobs."""
from pydantic import BaseModel, ConfigDict
from sceneops_harness import (CapabilityDefinition, CapabilityRegistry, CapabilityResult,
    ConnectorDefinition, ConnectorRegistry, RetryPolicy)
from sceneops_project_workspace import ModuleDocument, Project
from sceneops_ai_agents import AgentRuntime, AgentAssessmentInput, AgentAssessment, agent_catalog
from .schemas import ModuleId


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftInput(EmptyInput):
    module_id: ModuleId


EXTERNAL_CAPABILITIES = (
    ("blender.scene.inspect", "asset-factory", "检查 Blender 场景", "read", "blender"),
    ("blender.asset.export", "asset-factory", "导出生产资产", "build", "blender"),
    ("character.prepare", "character-animation", "准备角色与动画", "mutate", "blender"),
    ("world.apply", "world-composer", "写入场景布局", "mutate", "unity"),
    ("logic.apply", "logic-studio", "写入玩法逻辑", "mutate", "unity"),
    ("ui.publish", "ui-studio", "发布界面资源", "mutate", "unity"),
    ("audio.publish", "audio-studio", "发布音频资源", "mutate", "unity"),
    ("vfx.publish", "vfx-shader", "发布特效配方", "mutate", "unity"),
    ("render.execute", "render-ops", "执行生产渲染", "build", "comfyui"),
    ("unity.asset.import", "engine-unity", "导入 Unity 资产", "mutate", "unity"),
    ("unity.build", "build-release", "构建可玩版本", "build", "unity"),
    ("playtest.run", "ai-playtest", "运行目标游测", "test", "player"),
    ("version.merge", "version-collaboration", "合并审阅变更", "mutate", "git"),
)


def create_registry(workspace, provider):
    connectors = ConnectorRegistry()
    connectors.register(ConnectorDefinition(id="ai", title="当前 AI Provider",
        status="available" if provider.provider_available() else "blocked",
        reason="仅检查本地配置；登录、额度和真实响应未经本轮验证。"))
    for name in ("blender", "unity", "comfyui", "player", "git"):
        connectors.register(ConnectorDefinition(id=name, title=name, status="blocked",
            reason="V5 生产执行适配器尚未接入并获得本地验证证据。不会调用旧 Mock 服务冒充生产。"))
    registry = CapabilityRegistry(connectors)

    async def read_project(invocation, cancellation):
        cancellation.raise_if_cancelled()
        value = workspace.get_project(invocation.project_id)
        return CapabilityResult(execution_mode="live", outputs=value.model_dump(mode="json"),
            evidence_refs=[f"project:{value.project_id}@{value.updated_at.isoformat()}"],
            evidence_types=["project_record"], tokens=0, cost_usd=0)

    async def read_draft(invocation, cancellation):
        cancellation.raise_if_cancelled()
        value = workspace.get_document(invocation.project_id, invocation.inputs["module_id"])
        return CapabilityResult(execution_mode="live", outputs=value.model_dump(mode="json"),
            evidence_refs=[f"draft:{value.project_id}:{value.module_id}@{value.revision}"],
            evidence_types=["saved_draft"], tokens=0, cost_usd=0,
            logs=["读取数据库记录，不证明草稿内容已执行或已验证；内部 sample_id 保留。"])

    for id, title, handler, input_model, output_model, evidence in (
        ("workspace.project.read", "读取当前项目", read_project, EmptyInput, Project, "project_record"),
        ("workspace.draft.read", "读取已保存模块草稿", read_draft, DraftInput, ModuleDocument, "saved_draft"),
    ):
        registry.register(CapabilityDefinition(id=id, provider_module_id="project-intake", title=title,
            execution_mode="live", required_permissions=["harness:read"], evidence_produced=[evidence],
            estimated_cost_usd=0, metered=False, retry_policy=RetryPolicy(max_attempts=2)),
            handler, input_model=input_model, output_model=output_model)
    agents = AgentRuntime(provider)
    registry.register(CapabilityDefinition(id="ai.agent.assess", provider_module_id="ai-agent-runtime",
        title="专家分析与建议", purpose="只输出建议，不实施外部修改", mode="plan", execution_mode="live",
        required_integrations=["ai"], required_permissions=["harness:plan"], timeout_seconds=125,
        allowed_agent_roles=[item.role for item in agent_catalog()], evidence_produced=["agent_assessment"],
        retry_policy=RetryPolicy(max_attempts=2)), agents.assess,
        input_model=AgentAssessmentInput, output_model=AgentAssessment)
    for id, module, title, mode, connector in EXTERNAL_CAPABILITIES:
        registry.register(CapabilityDefinition(id=id, provider_module_id=module, title=title, mode=mode,
            risk="high" if mode in {"mutate", "build"} else "medium", required_integrations=[connector],
            required_permissions=["production:execute"], execution_mode="planned", cross_system=True,
            availability_reason="尚未连接 V5 生产执行端；需后续明确授权的本地验证。",
            input_schema={"type": "object", "additionalProperties": False},
            output_schema={"type": "object", "additionalProperties": False}))
    return registry
