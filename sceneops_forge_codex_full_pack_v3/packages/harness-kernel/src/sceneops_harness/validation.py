"""Deterministic DAG, authority, schema, condition and execution checks."""
from pydantic import ValidationError
from sceneops_core_contracts import ExecutionMode

from .contracts import Authority, Condition, PipelineDefinition, PipelineStep, ValidationIssue, ValidationReport
from .registry import CapabilityRegistry


def condition_matches(condition: Condition, inputs: dict, outputs: dict) -> bool:
    values = inputs if condition.source == "inputs" else outputs
    if condition.operator == "exists":
        return condition.field in values
    return condition.field in values and values[condition.field] == condition.value


def requires_approval(step: PipelineStep, registry: CapabilityRegistry) -> bool:
    capability = registry.get(step.capability_id or "")
    return step.kind == "approval" or bool(capability and not step.dry_run and (
        capability.mode in ("mutate", "build") or capability.cross_system
    ))


def validate_step(step: PipelineStep, definition: PipelineDefinition, authority: Authority,
                  registry: CapabilityRegistry) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def issue(code: str, message: str) -> None:
        issues.append(ValidationIssue(code=code, message=message, step_id=step.id))

    if step.kind not in ("tool", "agent", "evaluator", "approval"):
        issue("UNSUPPORTED_STEP_KIND", f"Step kind {step.kind} has no runtime implementation")
    if step.kind == "approval":
        if (step.capability_id or step.agent_task or step.model_routing or step.conditions
                or step.acceptance_criteria or step.input_schema or step.output_schema
                or step.evidence_requirements or step.inputs or step.change_set
                or step.snapshot_ref or step.dry_run):
            issue("INVALID_APPROVAL_STEP", "Approval steps cannot contain executable work or predicates")
        return issues
    binding = registry.binding(step.capability_id or "")
    if not binding:
        issue("UNKNOWN_CAPABILITY", f"Capability {step.capability_id} is not registered")
        return issues
    cap = binding.definition
    if binding.handler is None or cap.execution_mode not in (ExecutionMode.LIVE, ExecutionMode.MOCK):
        issue("CAPABILITY_UNAVAILABLE", cap.availability_reason or f"{cap.id} is {cap.execution_mode.value}")
    if cap.id not in authority.allowed_capabilities:
        issue("CAPABILITY_DENIED", f"Authority does not allow {cap.id}")
    missing = set(cap.required_permissions) - set(authority.permissions)
    if missing:
        issue("PERMISSION_DENIED", f"Missing permissions: {', '.join(sorted(missing))}")
    for connector_id in cap.required_integrations:
        connector = registry.connectors.get(connector_id)
        if connector is None or connector.status != "available":
            issue("CONNECTOR_UNAVAILABLE", f"Connector {connector_id} is unavailable")
    for ref in cap.required_context:
        if ref not in definition.context_refs:
            issue("MISSING_CONTEXT", f"Required canonical context reference: {ref}")
    if step.dry_run and not cap.supports_dry_run:
        issue("DRY_RUN_UNSUPPORTED", f"{cap.id} has no dry-run handler contract")
    if cap.mode in ("mutate", "build"):
        if not cap.supports_dry_run or step.change_set is None:
            issue("CHANGESET_REQUIRED", "Mutation/build requires a typed ChangeSet and dry-run support")
        elif step.change_set.target.module_id != cap.provider_module_id:
            issue("CHANGESET_TARGET_MISMATCH", "ChangeSet target must match the capability provider")
        if cap.risk != "low" and not step.snapshot_ref:
            issue("SNAPSHOT_REQUIRED", "Medium/high/critical mutation requires a pre-change snapshot reference")
    for condition in (*step.conditions, *cap.preconditions):
        if condition.source != "inputs":
            issue("INVALID_PRECONDITION", "Preconditions can only refer to current inputs")
        elif not condition_matches(condition, step.inputs, {}):
            issue("PRECONDITION_FAILED", f"Input condition failed: {condition.field}")
    if binding.input_model:
        try:
            binding.input_model.model_validate(step.inputs)
        except ValidationError as exc:
            issue("INVALID_CAPABILITY_INPUT", str(exc))
    for field in ("input_schema", "output_schema"):
        declared = getattr(step, field)
        if declared and declared != getattr(cap, field):
            issue("STEP_SCHEMA_MISMATCH", f"{field} must match capability contract")
    if step.kind == "agent":
        task, routing = step.agent_task, step.model_routing
        if task is None or routing is None:
            issue("AGENT_CONTEXT_REQUIRED", "Agent step requires typed task and visible routing decision")
        elif task.agent_role not in cap.allowed_agent_roles or routing.agent_role != task.agent_role:
            issue("AGENT_ROLE_DENIED", "Agent role must match handler allowlist and routing decision")
        elif not set(task.allowed_capabilities).issubset(authority.allowed_capabilities):
            issue("AGENT_CAPABILITY_DENIED", "Agent task cannot broaden invocation authority")
    elif step.agent_task or step.model_routing:
        issue("INVALID_AGENT_CONTEXT", "Only agent steps can carry agent task or model routing")
    return issues


def validate_pipeline(definition: PipelineDefinition, authority: Authority,
                      registry: CapabilityRegistry) -> ValidationReport:
    issues: list[ValidationIssue] = []
    steps = [step for stage in definition.stages for step in stage.steps]
    ids = [step.id for step in steps]
    stage_ids = [stage.id for stage in definition.stages]
    if definition.project_id != authority.project_id:
        issues.append(ValidationIssue(code="PROJECT_DENIED", message="Authority belongs to a different project"))
    if len(ids) != len(set(ids)) or len(stage_ids) != len(set(stage_ids)):
        issues.append(ValidationIssue(code="DUPLICATE_ID", message="Stage and step IDs must be unique within a pipeline"))
    if len(steps) > definition.budget.max_steps:
        issues.append(ValidationIssue(code="STEP_BUDGET_EXCEEDED", message="Pipeline exceeds step budget"))
    if definition.policies:
        issues.append(ValidationIssue(code="UNSUPPORTED_POLICY", message="Named policy execution is not implemented; policies cannot be ignored"))
    if definition.execution_mode not in (ExecutionMode.PLANNED, ExecutionMode.LIVE, ExecutionMode.MOCK):
        issues.append(ValidationIssue(code="UNSUPPORTED_EXECUTION_MODE", message="Cached/blocked definitions cannot execute"))
    order: list[str] = []
    pending = {step.id: set(step.depends_on) for step in steps}
    for step in steps:
        issues.extend(validate_step(step, definition, authority, registry))
        if not set(step.depends_on).issubset(ids):
            issues.append(ValidationIssue(code="UNKNOWN_DEPENDENCY", message="Dependency references an unknown step", step_id=step.id))
        cap = registry.get(step.capability_id or "")
        if cap and definition.execution_mode != ExecutionMode.PLANNED and cap.execution_mode != definition.execution_mode:
            issues.append(ValidationIssue(code="MODE_MISMATCH", message="Explicit pipeline mode differs from capability", step_id=step.id))
    while pending:
        ready = [key for key, dependencies in pending.items() if dependencies.issubset(order)]
        if not ready:
            issues.append(ValidationIssue(code="DEPENDENCY_CYCLE", message="Dependencies cannot be scheduled"))
            break
        order.extend(ready)
        for key in ready:
            del pending[key]
    caps = [registry.get(step.capability_id or "") for step in steps]
    cost = sum(cap.estimated_cost_usd or 0 for cap in caps if cap)
    tokens = sum(cap.estimated_tokens for cap in caps if cap)
    if cost > definition.budget.max_cost_usd or tokens > definition.budget.max_tokens:
        issues.append(ValidationIssue(code="BUDGET_EXCEEDED", message="Capability estimates exceed the run budget"))
    metered_calls = sum(1 for cap in caps if cap and cap.metered)
    if metered_calls > definition.budget.max_metered_calls:
        issues.append(ValidationIssue(code="CALL_BUDGET_EXCEEDED", message="Pipeline requires more metered calls than the run allows"))
    return ValidationReport(valid=not issues, issues=issues, execution_order=order,
                            approval_steps=[step.id for step in steps if requires_approval(step, registry)])
