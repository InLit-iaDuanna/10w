"""Internal publication-boundary validation for VFX adapters and ChangeSets."""

from __future__ import annotations

from dataclasses import asdict
import re
from typing import Optional

from .adapters import AdapterCommand, AdapterResult
from .models import ExecutionMode, PublicationRequest


def validate_integration_contract(health_id: str, capability_id: str, adapter_version: str,
                                  expected_id: str) -> Optional[str]:
    if health_id != expected_id or capability_id != expected_id or not adapter_version:
        return f"适配器必须声明一致的 {expected_id} integration_id 与版本"
    return None


def validate_changeset_scope(request: PublicationRequest, required_targets: tuple[str, ...],
                             *, exact: bool) -> Optional[str]:
    change_set = request.change_set
    targets, required = set(change_set.target_object_ids), set(required_targets)
    if (exact and (targets != required or len(change_set.target_object_ids) != len(required_targets))) or not required <= targets:
        return "ChangeSet 目标对象与 Recipe 影响对象不一致"
    if change_set.base_version != request.recipe.provenance.source_version:
        return "ChangeSet base_version 与 Recipe 来源版本不一致"
    if change_set.proposed_values.get("recipe_version") != request.recipe.version:
        return "ChangeSet proposed recipe_version 与 Recipe 版本不一致"
    return None


def validate_publication_content(request: PublicationRequest) -> Optional[str]:
    recipe = request.recipe
    expected = {
        "operation": "publish_recipe", "recipe_version": recipe.version,
        "template_id": recipe.template_id, "shader_family": recipe.shader_family,
        "quality_tier": recipe.quality_tier.value, "parameters": dict(recipe.parameters),
        "particle_count": recipe.particle_count,
        "estimated_overdraw_layers": recipe.estimated_overdraw_layers,
        "estimated_screen_coverage_percent": recipe.estimated_screen_coverage_percent,
        "bindings": [asdict(binding) for binding in recipe.bindings],
    }
    if dict(request.change_set.proposed_values) != expected:
        return "ChangeSet 未精确批准当前 Shader、质量档、参数、预算与绑定"
    return None


def validate_adapter_success(result: AdapterResult, command: AdapterCommand) -> Optional[str]:
    if result.execution_mode in {ExecutionMode.PLANNED, ExecutionMode.BLOCKED}:
        return "适配器成功结果不能是 planned/blocked"
    if result.project_id != command.project_id or result.target_sceneops_ids != command.target_sceneops_ids:
        return "适配器返回项目或目标对象不匹配"
    if result.recipe_id != command.recipe_id or result.recipe_version != command.recipe_version:
        return "适配器返回 Recipe 身份不匹配"
    if not all((result.result_id, result.artifact_id, result.checksum_sha256, result.occurred_at)):
        return "适配器结果缺少 provenance 字段"
    checksum = result.checksum_sha256 or ""
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum.lower()):
        return "适配器结果 checksum_sha256 格式无效"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result.occurred_at or ""):
        return "适配器结果 occurred_at 必须是 UTC ISO-8601"
    return None
