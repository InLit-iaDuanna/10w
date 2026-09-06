"""Observe, choose one structured action, run through Harness, then read back."""
from datetime import timezone
from pydantic import ValidationError
from sceneops_harness import ChangeSet, HarnessError, PipelineDefinition, PipelineStage, PipelineStep
from .task_models import (ActionRecord, AgentAction, CreateCubeInput, VerificationRecord,
                          identifier, now)
from .task_tools import INPUT_MODELS, MUTATIONS, TaskTools, contained
from .production_models import ProductionStep
from .production_catalog import module_for


def project_action(service, task, entry, *, run_id=None):
    """Project actual Harness action state, never the model's proposed outcome."""
    full_access = entry.action.capability_id == "codex.task.execute"
    state = {"running": "running", "succeeded": "review_required" if full_access else "completed",
             "failed": "failed", "uncertain": "blocked", "blocked": "blocked"}.get(entry.state, "planned")
    prior = next((step for step in service.production.snapshot(task.project_id).steps
                  if step.id == f"{task.id}:{entry.action.action_id}"), None)
    index = next(index for index, item in enumerate(task.actions) if item.action.action_id == entry.action.action_id)
    if entry.verification_result:
        projected_verification = {'PASS': 'passed', 'FAIL': 'failed', 'INCONCLUSIVE': 'inconclusive'}[entry.verification_result.verdict]
    elif entry.action.capability_id == "codex.task.execute":
        projected_verification = "reported"
    elif entry.action.capability_id in ("unity.prototype.inspect", "unity.prototype.verify") and state == "completed":
        projected_verification = "inconclusive"
    else:
        projected_verification = "unverified"
    service.production.upsert_step(ProductionStep(
        id=f"{task.id}:{entry.action.action_id}", project_id=task.project_id, task_id=task.id,
        module_id=module_for(entry.action.capability_id), title=entry.action.rationale[:160],
        capability_id=entry.action.capability_id, state=state,
        mode="planned" if state == "planned" else "blocked" if state == "blocked" else "live",
        dependencies=[f"{task.id}:{task.actions[index - 1].action.action_id}"] if index else [],
        verification=projected_verification, verification_result=entry.verification_result,
        effect_state=entry.effect_state,
        run_id=run_id or (entry.run_ids[-1] if entry.run_ids else None),
        artifact_ids=prior.artifact_ids if prior else [], reason=entry.reason,
        started_at=(prior.started_at if prior else None) or (now().isoformat() if state == "running" else None),
        updated_at=now().isoformat()))


def definition(task, step):
    remaining = max(0.01, (task.grant.expires_at - now()).total_seconds())
    budget = task.grant.budget.model_copy(update={"max_duration_seconds": remaining,
        "max_metered_calls": max(0, task.grant.budget.max_metered_calls - task.model_calls_used)})
    # A model slot has already been reserved in the task aggregate, including this call.
    if step.capability_id == "agent.next_action":
        budget.max_metered_calls += 1
    return PipelineDefinition(project_id=task.project_id, intent_id=task.id, title=step.title,
        stages=[PipelineStage(id="action", title="单动作执行", steps=[step])], budget=budget, execution_mode="live")


async def choose(service, task_id):
    task = service.check_grant(task_id, "agent.next_action")
    settings = service.provider.settings()
    if (settings.provider, settings.model) != (task.provider_id, task.provider_model):
        raise HarnessError("TASK_SCOPE_DENIED", "模型配置已改变，需要重新审阅任务授权。")
    def reserve(current):
        if current.model_calls_used >= current.grant.budget.max_metered_calls:
            raise HarnessError("CALL_BUDGET_EXCEEDED", "已达到包含规划的模型请求次数上限。")
        current.model_calls_used += 1
    task = service.records.update(task_id, reserve, "agent.model.reserved")
    runtime = service.runtimes[task_id]
    inputs = {"goal": task.goal, "observations": task.observations,
        "expected_provider": task.provider_id, "expected_model": task.provider_model,
        "history": [{"action": entry.action.model_dump(mode="json"), "state": entry.state,
                     "reason": entry.reason} for entry in task.actions],
        "capabilities": [cap.model_dump(mode="json") for cap in runtime.registry.list() if cap.id != "agent.next_action"]}
    inputs['input_schemas'] = {cap.id: INPUT_MODELS[cap.id].model_json_schema() for cap in runtime.registry.list() if cap.id in INPUT_MODELS}
    step = PipelineStep(id="decide", title="观察并选择下一动作", capability_id="agent.next_action", inputs=inputs)
    run = runtime.submit(definition(task, step), service.authority(task), f"{task.id}_model_{task.model_calls_used}")
    def link(current):
        current.model_run_ids.append(run.id)
        current.current_run_id = run.id
    service.records.update(task_id, link, "agent.model.started", {"run_id": run.id, "call": task.model_calls_used})
    run = await runtime.start(task.project_id, run.id, service.authority(task))
    def observed(current):
        current.current_run_id = None
        current.model_tokens_known += run.tokens_used
        current.observations["model_last_state"] = {"state": run.state, "reason": run.reason}
    service.records.update(task_id, observed, "agent.model.observed", {"run_id": run.id, "state": run.state, "reason": run.reason})
    if run.state != "completed":
        if run.state == "cancelled":
            import asyncio
            raise asyncio.CancelledError()
        raise HarnessError("MODEL_ACTION_FAILED", run.reason or "模型未返回有效结构化动作。")
    return AgentAction.model_validate(run.step_runs[0].result.outputs)


def record_action(service, task_id, action):
    def record(task):
        prior = next((entry for entry in task.actions if entry.action.action_id == action.action_id), None)
        if prior and prior.action != action:
            raise HarnessError("REQUEST_ID_CONFLICT", "动作 ID 已对应其他内容，不能替换已审阅请求。")
        if prior:
            if prior.state in ("running", "uncertain"):
                raise HarnessError("ACTION_UNCERTAIN", "此动作外部结果不确定，不能自动重放。")
            if prior.attempts >= task.grant.budget.max_attempts_per_step and prior.state != "succeeded":
                raise HarnessError("ACTION_LIMIT", "此动作已达到尝试上限。")
        else:
            if len(task.actions) >= task.grant.budget.max_steps:
                raise HarnessError("ACTION_LIMIT", "已达到任务步骤上限。")
            role = ("blender-specialist" if action.capability_id.startswith("blender.") else
                    "unity-engineer" if action.capability_id.startswith(("unity.", "code.")) else
                    "reviewer" if action.capability_id == "agent.finish" else "producer")
            task.actions.append(ActionRecord(action=action, assigned_role=role))
    task = service.records.update(task_id, record, "agent.action.proposed", {"action": action.model_dump(mode="json")})
    project_action(service, task, next(item for item in task.actions if item.action.action_id == action.action_id))
    return action.action_id


def validate_action(task, entry):
    cap = entry.action.capability_id
    if cap not in INPUT_MODELS or cap not in task.grant.capability_ids:
        raise HarnessError("TASK_SCOPE_DENIED", "所需动作未知或超出授权范围，需要新授权。")
    if set(entry.action.inputs) - set(INPUT_MODELS[cap].model_fields):
        raise HarnessError("TASK_SCOPE_DENIED", "动作包含未授权参数；路径和权限不能由模型指定，需要重新审阅。")
    INPUT_MODELS[cap].model_validate(entry.action.inputs)
    if cap == 'unity.prototype.compose':
        prior = next((item for item in task.actions if item.action.capability_id == cap and item.state == 'succeeded'), None)
        if prior:
            original = INPUT_MODELS[cap].model_validate(prior.action.inputs)
            proposed = INPUT_MODELS[cap].model_validate(entry.action.inputs)
            for field in ('prototype_id', 'arena_size', 'enemy_count', 'goal_kills', 'seed'):
                if getattr(original, field) != getattr(proposed, field):
                    raise HarnessError('TASK_SCOPE_DENIED', '修复不能改变既定场地、敌人数量、击杀目标、身份或种子。')
    if cap == "blender.asset.create":
        others = [item for item in task.actions if item is not entry and item.action.capability_id == cap
                  and item.state in ("running", "succeeded", "uncertain")]
        if others:
            raise HarnessError("TASK_SCOPE_DENIED", "授权只允许一个新资产，不允许覆盖已有对象或扩大资产数量。")
    elif cap in ("blender.asset.export", "unity.asset.import"):
        TaskTools.spec_for(task, entry.action.inputs["asset_id"])
        if cap == "unity.asset.import":
            TaskTools.export_for(task, entry.action.inputs["asset_id"])


def changeset(task, entry):
    tool = entry.action.capability_id.split(".")[0]
    full_access = entry.action.capability_id == "codex.task.execute"
    code_write = entry.action.capability_id == 'code.file.write'
    return ChangeSet(change_set_id=identifier("chg"), base_version=f"agent-task:{task.id}",
        target={"module_id": "ai-agent-runtime", "integration_id": tool,
                "object_ids": [task.project_id] if code_write or full_access or entry.action.capability_id.startswith('unity.prototype.') else [entry.action.inputs["asset_id"]]},
        previous_values={"path": entry.action.inputs['path'], "content": entry.action.inputs['expected_content']} if code_write else {"task_owned_readback": task.observations.get("codex_prechange" if full_access else tool, {})},
        proposed_values=entry.action.inputs, rationale=entry.action.rationale,
        expected_result="源码写入后回读实际内容；不运行或编译，待用户审阅。" if code_write else "Codex 完成目标后返回待审阅结果；不声称独立验收。" if full_access else "仅授权独立工作区内的类型化动作，并由工具即时读回核验。",
        impact_scope="project" if full_access else "object", risk="high" if full_access else "low", validation_plan=["比对精确前文并回读当前源码；人工审阅差异"] if code_write else ["人工核对任务产物及 CLI 执行摘要"] if full_access else ["读回当前对象身份、尺寸、路径及 console"],
        rollback_plan=["停止任务专有会话，保留独立工程和产物供审阅；不自动删除或覆盖"],
        approval_requirements=[{"permission": "harness:approve", "minimum_decisions": 1, "allowed_actor_types": ["user"]}],
        created_by={"type": "agent", "id": "agt_" + entry.assigned_role.replace("-", "_")}, created_at=now())


async def execute_action(service, task_id, action_id):
    task = service.check_grant(task_id)
    entry = next(item for item in task.actions if item.action.action_id == action_id)
    if entry.state == "succeeded":
        service.records.update(task_id, lambda current: None, "agent.action.deduplicated", {"action_id": action_id})
        return False
    if entry.state in ("running", "uncertain") or entry.effect_state in ("APPLIED", "COMMITTED", "UNKNOWN"):
        raise HarnessError("ACTION_UNCERTAIN", "此动作可能正在执行或已经产生外部效果，不能自动重放。")
    validate_action(task, entry)
    def reserve(current):
        action = next(item for item in current.actions if item.action.action_id == action_id)
        transport_resend = action.state == "blocked" and action.effect_state in ("NONE", "STAGED")
        new_business_attempt = not transport_resend
        if new_business_attempt and action.attempts >= current.grant.budget.max_attempts_per_step:
            raise HarnessError("ACTION_LIMIT", "此动作已达到尝试上限。")
        if new_business_attempt:
            if action.state == "failed":
                if action.effect_state != "NONE":
                    raise HarnessError("ACTION_UNCERTAIN", "失败动作的外部效果未确认，不能建立新请求。")
                action.request_id = identifier("request")
            if action.action.capability_id == "unity.prototype.compose" and action.attempts == 0:
                prior_compose = any(item is not action and item.action.capability_id == "unity.prototype.compose"
                                    and item.state == "succeeded" for item in current.actions)
                if prior_compose:
                    if current.repair_rounds_used >= current.grant.max_repair_rounds:
                        raise HarnessError("REPAIR_LIMIT", "已达到任务自动修复轮次上限。")
                    current.repair_rounds_used += 1
            action.attempts += 1
        if action.action.capability_id == "codex.task.execute" and new_business_attempt:
            if current.cli_invocations_used:
                raise HarnessError("ACTION_UNCERTAIN", "完全权限 CLI 已启动过，不自动重放。")
            root = contained(current.grant.workspace_root, service.workspace_base)
            if root.exists() and any(root.iterdir()) and not service.records.owns_workspace(current.project_id, root):
                raise HarnessError("TASK_SCOPE_DENIED", "完全权限执行前目录已非空，不能接管。")
            current.observations["codex_prechange"] = {"workspace_root": str(root),
                "existed": root.exists(), "entries": sorted(path.name for path in root.iterdir()) if root.exists() else [], "observed_at": now().isoformat(),
                "scope": "仅记录应用已登记工程的顶层目录，不是整机快照，也不保证外部修改可回滚。"}
            current.cli_invocations_used += 1
        action.state, action.reason = "running", None
        action.effect_state = "STAGED" if action.action.capability_id in MUTATIONS else "NONE"
        if action.action.capability_id in MUTATIONS:
            action.change_set = action.change_set or changeset(current, action)
            action.approval_id = action.approval_id or identifier("approval")
    task = service.records.update(task_id, reserve, "agent.action.reserved", {"action_id": action_id})
    entry = next(item for item in task.actions if item.action.action_id == action_id)
    step = PipelineStep(id=action_id, title=entry.action.rationale[:160], capability_id=entry.action.capability_id,
        inputs=entry.action.inputs, change_set=entry.change_set,
        snapshot_ref=f"agent-task:{task.id}:codex_prechange" if entry.action.capability_id == "codex.task.execute" else None)
    runtime = service.runtimes[task_id]
    delivery_no = len(entry.run_ids) + 1
    run = runtime.submit(definition(task, step), service.authority(task),
                         f"{entry.request_id}_delivery_{delivery_no}")
    def link(current):
        next(item for item in current.actions if item.action.action_id == action_id).run_ids.append(run.id)
        current.current_run_id = run.id
    service.records.update(task_id, link, "agent.action.started", {"action_id": action_id, "run_id": run.id})
    project_action(service, service.get(task_id), entry, run_id=run.id)
    if run.state == "queued":
        run = await runtime.start(task.project_id, run.id, service.authority(task))
    if run.state == "awaiting_approval":
        authorized = service.check_grant(task_id, entry.action.capability_id)
        validate_action(authorized, next(item for item in authorized.actions if item.action.action_id == action_id))
        runtime.approve(task.project_id, run.id, action_id, service.authority(authorized))
        service.records.update(task_id, lambda current: None, "agent.action.grant_applied",
            {"action_id": action_id, "grant_id": task.grant.id, "approved_by": task.grant.actor_id,
             "approval_id": entry.approval_id, "change_set_id": entry.change_set.change_set_id if entry.change_set else None})
        run = await runtime.start(task.project_id, run.id, service.authority(authorized))
    result = run.step_runs[0].result
    pending = service.tools[task_id].blocked_tool is not None
    evidence = result.outputs.get("evidence") if result and isinstance(result.outputs, dict) else None
    code_recovered = False
    if entry.action.capability_id == 'code.file.write' and run.state != 'completed':
        effect, recovered = service.code.reconcile(service.get(task_id), entry)
        evidence = recovered or {'tool': 'code', 'effect_state': effect, 'reason': run.reason}
        code_recovered = effect == 'COMMITTED'
    reported_effect = evidence.get("effect_state") if isinstance(evidence, dict) else None
    if reported_effect not in ("NONE", "STAGED", "APPLIED", "COMMITTED", "UNKNOWN"):
        reported_effect = None
    def observed(current):
        action = next(item for item in current.actions if item.action.action_id == action_id)
        completed_mutation_without_commit = (run.state == "completed"
            and entry.action.capability_id in MUTATIONS
            and reported_effect in ("STAGED", "APPLIED", "UNKNOWN"))
        completed_mutation_without_effect = (run.state == "completed"
            and entry.action.capability_id in MUTATIONS and reported_effect == "NONE")
        action.state = ("uncertain" if completed_mutation_without_commit else
                        "failed" if completed_mutation_without_effect else
                        "succeeded" if run.state == "completed" or code_recovered else
                        "failed" if entry.action.capability_id == 'code.file.write' and reported_effect == 'NONE' else
                        "blocked" if pending else
                        "uncertain" if entry.action.capability_id in MUTATIONS else "failed")
        action.reason, action.result = run.reason, result.outputs if result else None
        if entry.action.capability_id == 'code.file.write' and evidence is not None:
            action.result = {'evidence': evidence}
        if reported_effect is not None:
            action.effect_state = reported_effect
        elif run.state == "completed":
            action.effect_state = "COMMITTED" if action.action.capability_id in MUTATIONS else "NONE"
        elif pending:
            action.effect_state = "NONE"
        elif action.action.capability_id in MUTATIONS:
            action.effect_state = "UNKNOWN"
        else:
            action.effect_state = "NONE"
        current.current_run_id = None
        if evidence is not None:
            current.observations[evidence.get("tool", "verification")] = evidence
            verification = evidence.get("verification") if isinstance(evidence, dict) else None
            if isinstance(verification, dict):
                try:
                    action.verification_result = VerificationRecord.model_validate(verification)
                except ValidationError:
                    # Legacy or incomplete evidence remains historical evidence, never a current PASS.
                    action.verification_result = None
        if pending:
            current.pending_action_id, current.status, current.reason = action_id, "blocked", run.reason
            current.observations["blocked_tool"] = service.tools[task_id].blocked_tool
        elif entry.action.capability_id == 'agent.report_blocked' and run.state == 'completed':
            current.status, current.reason = 'needs_approval', 'BLOCKED_CAPABILITY_GAP: ' + entry.action.inputs['reason']
            current.grant.revoked = True
        elif entry.action.capability_id == "agent.finish" and run.state == "completed":
            production_ready = (action.result or {}).get('evidence', {}).get('delivery_status') == 'production_ready'
            code_written = (action.result or {}).get('evidence', {}).get('delivery_status') == 'code_written'
            current.status = 'review_required' if production_ready or code_written else 'completed'
            current.reason = ('源码已写入并回读，待检查；未运行或编译。' if code_written else
                '制作与编译检查完成，待用户手动试玩；未执行自动游测。' if production_ready else None)
            current.finished_at = now()
        elif entry.action.capability_id == "codex.task.execute" and run.state == "completed":
            current.status, current.reason, current.finished_at = "review_required", "Codex 已结束，请检查实际产物；未独立验收。", now()
            current.grant.revoked = True
    task = service.records.update(task_id, observed, "agent.action.observed", {"action_id": action_id, "state": run.state, "reason": run.reason})
    final_entry = next(item for item in task.actions if item.action.action_id == action_id)
    project_action(service, task, final_entry)
    if pending:
        return True
    if run.state == "cancelled":
        import asyncio
        raise asyncio.CancelledError()
    if entry.action.capability_id == 'code.file.write' and final_entry.effect_state in ('NONE', 'COMMITTED'):
        return False
    if run.state != "completed" and entry.action.capability_id in MUTATIONS:
        raise HarnessError("ACTION_UNCERTAIN", run.reason or "外部写入结果不确定，需要检查。")
    if final_entry.state == "uncertain":
        raise HarnessError("ACTION_UNCERTAIN", final_entry.reason or "外部写入尚未确认提交，需要检查。")
    return entry.action.capability_id in ("agent.finish", "codex.task.execute", 'agent.report_blocked') and run.state == "completed"


async def execute_task(service, task_id):
    task = service.check_grant(task_id)
    if task.grant.execution_mode == "codex-full-access":
        action = AgentAction(action_id="codex_execution", capability_id="codex.task.execute",
            rationale="按用户确认的完整权限授权执行原任务；CLI 内部模型次数未知，不重试。", inputs={"goal": task.goal})
        action_id = record_action(service, task_id, action)
        await execute_action(service, task_id, action_id)
        return
    consecutive_model_failures = 0
    while True:
        task = service.check_grant(task_id)
        if task.pending_action_id:
            action_id = task.pending_action_id
            service.records.update(task_id, lambda current: setattr(current, "pending_action_id", None), "agent.action.resume_requested")
        else:
            try:
                action = await choose(service, task_id)
                consecutive_model_failures = 0
            except HarnessError as error:
                if error.code != "MODEL_ACTION_FAILED":
                    raise
                consecutive_model_failures += 1
                if consecutive_model_failures >= 2:
                    raise
                continue
            action_id = record_action(service, task_id, action)
        try:
            if await execute_action(service, task_id, action_id):
                return
        except (ValidationError, HarnessError) as error:
            if isinstance(error, HarnessError) and error.code in ("TASK_SCOPE_DENIED", "TASK_GRANT_INVALID", "ACTION_UNCERTAIN", "ACTION_LIMIT", "REPAIR_LIMIT", "REQUEST_ID_CONFLICT"):
                raise
            def failed(current):
                entry = next(item for item in current.actions if item.action.action_id == action_id)
                entry.state, entry.reason = "failed", str(error)
            task = service.records.update(task_id, failed, "agent.action.input_rejected", {"action_id": action_id, "reason": str(error)})
            project_action(service, task, next(item for item in task.actions if item.action.action_id == action_id))
