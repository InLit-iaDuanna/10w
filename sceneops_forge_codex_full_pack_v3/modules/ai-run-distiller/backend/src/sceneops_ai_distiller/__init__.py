"""A completed run can be a reusable draft, not proof of another project succeeding."""
from sceneops_harness import DistilledWorkflow


def distill_run(run, title: str):
    if run.state != "completed" or not run.step_runs or any(step.state != "succeeded" for step in run.step_runs):
        raise ValueError("只有实际完成且每一步成功的运行才能沉淀；空、失败、跳过或未执行的运行不可。")
    roles = sorted({step.agent_task.agent_role for stage in run.definition.stages
        for step in stage.steps if step.agent_task})
    template = run.definition.model_copy(deep=True)
    # Runtime source payloads are not reusable parameters. Rebind context for a new project.
    template.inputs = {}
    template.context_refs = []
    for stage in template.stages:
        for step in stage.steps:
            step.inputs = {key: value for key, value in step.inputs.items() if key not in {"context", "project_id"}}
    return DistilledWorkflow(project_id=run.project_id, source_run_id=run.id, title=title,
        pipeline_template=template, agent_roles=roles, required_context=["重新选择目标项目与已保存草稿"],
        skill="从已完成运行提取步骤、依赖和验收要求。复用时重新绑定项目上下文、验证能力与权限，再手动运行。",
        recovery_strategy="保留步骤失败策略；恢复需重新审阅。",
        approval_policy=["不继承源运行的审批或执行权限"],
        limitations=["模板不证明另一个项目已通过", "源运行模式必须保留", "外部工具能力仍需独立验证"],
        execution_mode=run.execution_mode)


from .experience import ExperienceService
from .experience_router import create_experience_router
from .experience_repository import ExperienceError

__all__ = ["distill_run", "ExperienceService", "ExperienceError", "create_experience_router"]

from .experience_models import (ExperienceSettingsUpdate, ExperienceSource, MemoryProposal, MemoryWrite, MemoryEvent, MemoryUndo, ProjectMemoryReference, ProjectMemoryCollection)
__all__ += ["ExperienceSettingsUpdate", "ExperienceSource", "MemoryProposal", "MemoryWrite", "MemoryEvent", "MemoryUndo", "ProjectMemoryReference", "ProjectMemoryCollection"]
