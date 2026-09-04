"""Canonical VFX recipe validation, preview planning, and publication behavior."""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Iterable, Mapping, Optional

from .adapters import AdapterCommand, RenderPreviewAdapter, UnityVfxAdapter
from .models import (
    ApprovalState,
    BudgetWarning,
    ExecutionMode,
    EventContext,
    OperationResult,
    PreviewPlan,
    PublicationRequest,
    QUALITY_BUDGETS,
    VfxShaderRecipe,
)
from .validation import (validate_adapter_success, validate_changeset_scope,
                         validate_integration_contract, validate_publication_content)


def validate_budget(recipe: VfxShaderRecipe) -> tuple[BudgetWarning, ...]:
    budget = QUALITY_BUDGETS[recipe.quality_tier]
    checks = (
        ("VFX_PARTICLE_BUDGET", "particle_count", recipe.particle_count, budget.max_particles, "粒子数量"),
        (
            "VFX_OVERDRAW_BUDGET",
            "estimated_overdraw_layers",
            recipe.estimated_overdraw_layers,
            budget.max_overdraw_layers,
            "估算 overdraw 层数",
        ),
        (
            "VFX_COVERAGE_BUDGET",
            "estimated_screen_coverage_percent",
            recipe.estimated_screen_coverage_percent,
            budget.max_screen_coverage_percent,
            "估算屏幕覆盖率",
        ),
    )
    return tuple(
        BudgetWarning(code, metric, float(actual), float(allowed), f"{label} {actual} 超过 {allowed}")
        for code, metric, actual, allowed, label in checks
        if actual > allowed
    )


def plan_preview(recipe: VfxShaderRecipe) -> PreviewPlan:
    errors = recipe.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return PreviewPlan(
        preview_id=f"preview_{recipe.recipe_id}_{recipe.version}_{recipe.quality_tier.value}",
        recipe_id=recipe.recipe_id,
        quality_tier=recipe.quality_tier,
        passes=("base-color", "highlight-mask", "overdraw-estimate", "composite"),
        seed=1701,
        frame_count=24,
        execution_mode=ExecutionMode.MOCK,
        warnings=validate_budget(recipe),
    )


def plan_publication(request: PublicationRequest) -> OperationResult:
    """Describe a mutation truthfully before any adapter execution."""
    errors = request.recipe.validate() + request.change_set.validate()
    if errors:
        return OperationResult(False, "PLAN_INVALID", "发布计划校验失败：" + "; ".join(errors), ExecutionMode.BLOCKED, False)
    if request.change_set.approval_state is not ApprovalState.APPROVED:
        return OperationResult(True, "WAITING_APPROVAL", "发布计划已创建，等待 ChangeSet 审批", ExecutionMode.PLANNED, False)
    return OperationResult(True, "READY_TO_EXECUTE", "发布计划已审批，尚未调用 Unity", ExecutionMode.PLANNED, False)


def build_event(
    event_type: str,
    payload: Mapping[str, Any],
    mode: ExecutionMode,
    context: EventContext,
) -> Mapping[str, Any]:
    return {
        "event_id": context.event_id,
        "event_type": event_type,
        "event_version": 1,
        "occurred_at": context.occurred_at,
        "project_id": context.project_id,
        "correlation_id": context.correlation_id,
        "causation_id": context.causation_id,
        "actor": asdict(context.actor),
        "mode": mode.value,
        "payload": dict(payload),
    }


def validate_recipe_operation(recipe: VfxShaderRecipe, context: EventContext) -> OperationResult:
    errors = recipe.validate()
    if errors:
        return OperationResult(False, "RECIPE_INVALID", "Recipe 校验失败：" + "; ".join(errors), ExecutionMode.BLOCKED, False)
    warnings = validate_budget(recipe)
    event = build_event(
        "vfx.recipe.validated",
        {"recipe_id": recipe.recipe_id, "recipe_version": recipe.version, "warning_codes": [item.code for item in warnings]},
        recipe.provenance.execution_mode,
        context,
    )
    return OperationResult(True, "VALIDATED", "Recipe 校验完成", recipe.provenance.execution_mode, False, (event,))


def plan_preview_operation(recipe: VfxShaderRecipe, context: EventContext) -> tuple[PreviewPlan, OperationResult]:
    plan = plan_preview(recipe)
    event = build_event(
        "vfx.preview.planned",
        {"preview_id": plan.preview_id, "recipe_id": plan.recipe_id, "quality_tier": plan.quality_tier.value, "seed": plan.seed},
        plan.execution_mode,
        context,
    )
    return plan, OperationResult(True, "PREVIEW_PLANNED", "确定性预览计划已创建", plan.execution_mode, False, (event,))


class VfxShaderService:
    def __init__(
        self,
        unity_adapter: Optional[UnityVfxAdapter] = None,
        render_adapter: Optional[RenderPreviewAdapter] = None,
    ) -> None:
        self.unity_adapter = unity_adapter
        self.render_adapter = render_adapter

    def publish(
        self,
        request: PublicationRequest,
        *,
        module_enabled: bool = True,
        permissions: Iterable[str] = (),
    ) -> OperationResult:
        if not module_enabled:
            return self._blocked("MODULE_DISABLED", "VFX/Shader 模块已停用")
        if "vfx:publish" not in set(permissions):
            return self._blocked("PERMISSION_DENIED", "缺少 vfx:publish 权限")
        errors = request.recipe.validate()
        if errors:
            return self._blocked("RECIPE_INVALID", "Recipe 校验失败：" + "; ".join(errors))
        warnings = validate_budget(request.recipe)
        if warnings:
            return self._blocked("BUDGET_EXCEEDED", "质量预算超限，请调整参数后重新提交")
        changeset_errors = request.change_set.validate()
        if changeset_errors:
            return self._blocked("CHANGESET_INVALID", "ChangeSet 校验失败：" + "; ".join(changeset_errors))
        if request.change_set.approval_state is not ApprovalState.APPROVED:
            return self._blocked("CHANGESET_APPROVAL_REQUIRED", "必须先审批关联 ChangeSet")
        scope_error = validate_changeset_scope(request, request.recipe.provenance.related_sceneops_ids, exact=True)
        if scope_error:
            return self._blocked("CHANGESET_SCOPE_MISMATCH", scope_error)
        content_error = validate_publication_content(request)
        if content_error:
            return self._blocked("CHANGESET_CONTENT_MISMATCH", content_error)
        if self.unity_adapter is None:
            return self._blocked("INTEGRATION_OFFLINE", "Unity 适配器未连接")
        health = self.unity_adapter.health_check()
        if not health.online:
            return self._blocked("INTEGRATION_OFFLINE", "Unity 适配器离线")
        capabilities = self.unity_adapter.capabilities()
        contract_error = validate_integration_contract(health.integration_id, capabilities.integration_id, capabilities.adapter_version, "unity")
        if contract_error:
            return self._blocked("ADAPTER_CONTRACT_INVALID", contract_error)
        capability = "publish_vfx_recipe"
        if capability not in capabilities.commands:
            return self._blocked("CAPABILITY_MISSING", "Unity 适配器不支持 VFX 发布")
        command = self._publication_command(request)
        dry_run = self.unity_adapter.dry_run(command)
        if not dry_run.ok:
            return self._adapter_failure(dry_run.code, "Unity dry-run 失败", dry_run.execution_mode)
        result = self.unity_adapter.publish(command)
        if not result.ok:
            return self._adapter_failure(result.code, "Unity 发布失败", result.execution_mode)
        result_error = validate_adapter_success(result, command)
        if result_error:
            return self._adapter_failure("ADAPTER_RESULT_INVALID", result_error, result.execution_mode)
        event = build_event(
            "vfx.recipe.published",
            {
                "recipe_id": request.recipe.recipe_id,
                "recipe_version": request.recipe.version,
                "change_set_id": request.change_set.change_set_id,
                "target_sceneops_ids": list(request.recipe.provenance.related_sceneops_ids),
                "adapter_result_id": result.result_id,
            },
            result.execution_mode,
            request.event_context,
        )
        published_provenance = replace(
            request.recipe.provenance,
            artifact_id=result.artifact_id,
            approval_state=ApprovalState.PUBLISHED,
            execution_mode=result.execution_mode,
            tool="unity-adapter",
            adapter_version=capabilities.adapter_version,
            timestamp=result.occurred_at,
            checksum_sha256=result.checksum_sha256,
        )
        return OperationResult(
            True,
            "PUBLISHED",
            "VFX Recipe 已通过适配器发布",
            result.execution_mode,
            False,
            (event,),
            result.result_id,
            published_provenance,
        )

    def set_binding_enabled(
        self,
        request: PublicationRequest,
        binding_id: str,
        enabled: bool,
        *,
        module_enabled: bool = True,
        permissions: Iterable[str] = (),
    ) -> OperationResult:
        if not module_enabled:
            return self._blocked("MODULE_DISABLED", "VFX/Shader 模块已停用")
        if "vfx:write" not in set(permissions):
            return self._blocked("PERMISSION_DENIED", "缺少 vfx:write 权限")
        changeset_errors = request.change_set.validate()
        if changeset_errors:
            return self._blocked("CHANGESET_INVALID", "ChangeSet 校验失败：" + "; ".join(changeset_errors))
        if request.change_set.approval_state is not ApprovalState.APPROVED:
            return self._blocked("CHANGESET_APPROVAL_REQUIRED", "启停变更必须先审批 ChangeSet")
        try:
            changed = request.recipe.with_binding_enabled(binding_id, enabled)
        except KeyError:
            return self._blocked("BINDING_NOT_FOUND", "未找到事件绑定")
        selected_binding = next(binding for binding in changed.bindings if binding.binding_id == binding_id)
        scope_error = validate_changeset_scope(request, (selected_binding.target_sceneops_id,), exact=False)
        if scope_error:
            return self._blocked("CHANGESET_SCOPE_MISMATCH", scope_error)
        expected_change = {
            "operation": "set_binding_enabled", "recipe_version": changed.version,
            "binding_id": binding_id, "enabled": enabled,
        }
        if dict(request.change_set.proposed_values) != expected_change:
            return self._blocked("CHANGESET_CONTENT_MISMATCH", "ChangeSet 未批准这项绑定启停值")
        if self.unity_adapter is None:
            return self._blocked("INTEGRATION_OFFLINE", "Unity 适配器离线")
        health = self.unity_adapter.health_check()
        if not health.online:
            return self._blocked("INTEGRATION_OFFLINE", "Unity 适配器离线")
        capabilities = self.unity_adapter.capabilities()
        contract_error = validate_integration_contract(health.integration_id, capabilities.integration_id, capabilities.adapter_version, "unity")
        if contract_error:
            return self._blocked("ADAPTER_CONTRACT_INVALID", contract_error)
        if "set_vfx_enabled" not in capabilities.commands:
            return self._blocked("CAPABILITY_MISSING", "Unity 适配器不支持启停 VFX")
        command = AdapterCommand(
            "set_vfx_enabled",
            changed.provenance.source_project_id,
            (selected_binding.target_sceneops_id,),
            changed.recipe_id,
            changed.version,
            request.change_set.change_set_id,
            {"binding_id": binding_id, "enabled": enabled},
        )
        dry_run = self.unity_adapter.dry_run(command)
        if not dry_run.ok:
            return self._adapter_failure(dry_run.code, "Unity dry-run 失败", dry_run.execution_mode)
        result = self.unity_adapter.publish(command)
        if not result.ok:
            return self._adapter_failure(result.code, "Unity 启停操作失败", result.execution_mode)
        result_error = validate_adapter_success(result, command)
        if result_error:
            return self._adapter_failure("ADAPTER_RESULT_INVALID", result_error, result.execution_mode)
        event = build_event(
            "vfx.binding.changed",
            {
                "recipe_id": changed.recipe_id,
                "binding_id": binding_id,
                "enabled": enabled,
                "change_set_id": request.change_set.change_set_id,
            },
            result.execution_mode,
            request.event_context,
        )
        return OperationResult(True, "BINDING_CHANGED", "VFX 启停状态已更新", result.execution_mode, False, (event,))

    def render_external_preview(
        self,
        recipe: VfxShaderRecipe,
        *,
        module_enabled: bool = True,
        permissions: Iterable[str] = (),
    ) -> OperationResult:
        if not module_enabled:
            return self._blocked("MODULE_DISABLED", "VFX/Shader 模块已停用")
        if "vfx:read" not in set(permissions):
            return self._blocked("PERMISSION_DENIED", "缺少 vfx:read 权限")
        errors = recipe.validate()
        if errors:
            return self._blocked("RECIPE_INVALID", "Recipe 校验失败：" + "; ".join(errors))
        if self.render_adapter is None:
            return self._blocked("INTEGRATION_OFFLINE", "Render 适配器未连接；可继续使用 Mock 预览")
        health = self.render_adapter.health_check()
        if not health.online:
            return self._blocked("INTEGRATION_OFFLINE", "Render 适配器离线；可继续使用 Mock 预览")
        capabilities = self.render_adapter.capabilities()
        contract_error = validate_integration_contract(health.integration_id, capabilities.integration_id, capabilities.adapter_version, "render")
        if contract_error:
            return self._blocked("ADAPTER_CONTRACT_INVALID", contract_error)
        if "render_vfx_preview" not in capabilities.commands:
            return self._blocked("CAPABILITY_MISSING", "Render 适配器不支持 VFX 预览")
        command = AdapterCommand(
            "render_vfx_preview",
            recipe.provenance.source_project_id,
            recipe.provenance.related_sceneops_ids,
            recipe.recipe_id,
            recipe.version,
            None,
            {"quality_tier": recipe.quality_tier.value, "parameters": dict(recipe.parameters)},
        )
        dry_run = self.render_adapter.dry_run(command)
        if not dry_run.ok:
            return self._adapter_failure(dry_run.code, "Render dry-run 失败", dry_run.execution_mode)
        result = self.render_adapter.render(command)
        if not result.ok:
            return self._adapter_failure(result.code, "Render 预览失败", result.execution_mode)
        result_error = validate_adapter_success(result, command)
        if result_error:
            return self._adapter_failure("ADAPTER_RESULT_INVALID", result_error, result.execution_mode)
        output_provenance = replace(
            recipe.provenance,
            artifact_id=result.artifact_id,
            artifact_type="vfx_preview",
            execution_mode=result.execution_mode,
            approval_state=ApprovalState.PROPOSED,
            tool="render-adapter",
            adapter_version=capabilities.adapter_version,
            timestamp=result.occurred_at,
            checksum_sha256=result.checksum_sha256,
        )
        return OperationResult(
            True,
            "RENDERED",
            "外部 VFX 预览已生成，仍为待审批提案",
            result.execution_mode,
            False,
            adapter_result_id=result.result_id,
            output_provenance=output_provenance,
        )

    @staticmethod
    def _publication_command(request: PublicationRequest) -> AdapterCommand:
        recipe = request.recipe
        return AdapterCommand(
            "publish_vfx_recipe",
            recipe.provenance.source_project_id,
            recipe.provenance.related_sceneops_ids,
            recipe.recipe_id,
            recipe.version,
            request.change_set.change_set_id,
            {
                "template_id": recipe.template_id,
                "shader_family": recipe.shader_family,
                "quality_tier": recipe.quality_tier.value,
                "parameters": dict(recipe.parameters),
                "particle_count": recipe.particle_count,
                "estimated_overdraw_layers": recipe.estimated_overdraw_layers,
                "estimated_screen_coverage_percent": recipe.estimated_screen_coverage_percent,
                "bindings": [asdict(binding) for binding in recipe.bindings],
            },
        )

    @staticmethod
    def _blocked(code: str, message_zh: str) -> OperationResult:
        return OperationResult(False, code, message_zh, ExecutionMode.BLOCKED, False)

    @staticmethod
    def _adapter_failure(code: str, message_zh: str, mode: ExecutionMode) -> OperationResult:
        truthful_mode = mode if mode in {ExecutionMode.LIVE, ExecutionMode.CACHED, ExecutionMode.MOCK} else ExecutionMode.BLOCKED
        return OperationResult(False, code, message_zh, truthful_mode, False)
