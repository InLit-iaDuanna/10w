"""Server-owned task grants and lifecycle, composed around existing Harness runs."""
import asyncio
import os
from datetime import timedelta
from pathlib import Path
from typing import Literal
from sceneops_ai_provider import ProviderService
from sceneops_harness import Authority, CapabilityRegistry, HarnessError, HarnessRuntime, RuntimeBudget
from .task_models import (AgentTaskRecord, AuthorizationCard, AuthorizeAgentTask, PrepareAgentTask,
                          TaskGrant, now, PROTOTYPE_CAPABILITIES, TASK_CAPABILITIES, CODE_CAPABILITIES)
from .task_repository import AgentTaskRepository
from .task_tools import TaskTools, contained
from .production_store import ProductionStore


class AgentTaskService:
    def __init__(self, database_path, workspace_repository, data_dir, *, provider=None,
                 blender_factory=None, unity_factory=None, card_context=None):
        from . import AgentRuntime
        self.database_path = Path(database_path)
        self.workspace = workspace_repository
        self.card_context = card_context
        self.data_dir = Path(data_dir).resolve()
        self.workspace_base = self.data_dir / "agent-workspaces"
        self.state_base = self.data_dir / "agent-tool-state"
        self.provider = provider or ProviderService(database_path)
        self.agents = AgentRuntime(self.provider)
        self.records = AgentTaskRepository(database_path)
        from .code_workspace import CodeWorkspace
        self.code = CodeWorkspace(self)
        self.records.recover_workspace_ownership(self.workspace_base)
        self.production = ProductionStore(database_path, self.data_dir, self.records)
        self.blender_factory, self.unity_factory = blender_factory, unity_factory
        self.jobs, self.tools, self.runtimes = {}, {}, {}
        self.cleanups = {}
        self.connection_checks = set()
        self.recover_interrupted()

    def card_workspace(self, project_id, card_id, *, expected_root=None, expected_branch=None):
        try:
            record = self.workspace.get_card_worktree(project_id, card_id)
        except (ValueError, KeyError) as error:
            raise HarnessError('CARD_WORKSPACE_INVALID', str(error)) from error
        root = Path(record['worktree_path'])
        if (not root.is_absolute() or root.resolve() != root or not root.is_dir()
                or record.get('project_id') != project_id or record.get('card_id') != card_id
                or (expected_root is not None and str(root) != expected_root)
                or (expected_branch is not None and record['branch'] != expected_branch)):
            raise HarnessError('TASK_SCOPE_DENIED', '卡片登记、分支或目录已改变，需要重新审阅。')
        return record

    def prepare(self, request: PrepareAgentTask):
        if not request.goal.strip():
            raise HarnessError("TASK_GOAL_REQUIRED", "请输入任务目标。")
        settings = self.provider.settings()
        if request.execution_mode == "codex-full-access" and settings.provider != "codexcli":
            raise HarnessError("CODEX_PROVIDER_REQUIRED", "完全权限任务需要先明确选择 Codex CLI 提供方。")
        if request.allow_image_generation and request.execution_mode != "codex-full-access":
            raise HarnessError("IMAGE_PROVIDER_REQUIRED", "登录态 GPT 图片目前需要明确选择 Codex CLI 完全权限；不会自动改用付费 API。")
        project = (self.workspace.get_project(request.project_id) if request.project_id
                   else self.workspace.create_project("Agent · " + request.goal.strip()[:60]))
        card_work = (self.card_workspace(project.project_id, request.card_id)
                     if request.task_profile == 'card-development' else None)
        root = Path(card_work['worktree_path']) if card_work else contained(self.workspace_base / project.project_id, self.workspace_base)
        if not card_work and root.exists() and any(root.iterdir()) and not self.records.owns_workspace(project.project_id, root):
            raise HarnessError("TASK_REQUIRES_EMPTY_WORKSPACE", "Agent 任务只能使用独立空目录，不能接管已有项目文件。")
        if not card_work and request.execution_mode == "typed-tools" and root.exists() and any(root.iterdir()):
            raise HarnessError("TYPED_CONTINUATION_NOT_CONNECTED", "此应用工程已有内容，受控 Blender/Unity 跨任务会话重绑定尚未接入。不会重放或覆盖；可在主对话明确选择 Codex 完全权限继续，或创建新项目。")
        card = AuthorizationCard(workspace_root=str(root), execution_mode=request.execution_mode,
            allow_image_generation=request.allow_image_generation, allow_playtest=request.allow_playtest,
            task_profile=request.task_profile, card_id=request.card_id,
            branch=card_work['branch'] if card_work else None)
        if card_work:
            card.capability_ids = list(CODE_CAPABILITIES)
            card.scope = ('仅此项目的已登记卡片分支：读取有界 UTF-8 源码，按精确前文创建或修改代码文件；'
                '每文件最多 64 KiB、每任务最多 32 个文件写入动作与累计 512 KiB 新内容。'
                '可按精确前文修改用户已有改动；拒绝隐藏路径、链接、二进制与依赖锁文件。'
                '不执行源码、Shell、安装、Git 修改、构建或游测；完成后必须人工审阅。')
        elif request.task_profile == 'survival-prototype':
            card.capability_ids = list(PROTOTYPE_CAPABILITIES)
            card.scope = ('本任务专用空 Unity 工程：以有界数据生成方块生存射击原型，'
                '保存场景和产物版本，回读场景、编译状态和控制台。'
                '只执行固定受控组件，不接受模型脚本；不修改其他工程，不生产构建、不发布、不购买服务。')
        elif request.task_profile == 'auto':
            card.capability_ids = list(dict.fromkeys(TASK_CAPABILITIES + PROTOTYPE_CAPABILITIES))
            card.scope = ('只执行你本次明确目标所需的受控操作。Agent 可在基础资产交换与固定生存射击配方之间选择，'
                '并在专用空工程进行制作、保存与编译检查。当前不支持任意玩法/C#生成；能力缺口必须报告阻塞。'
                '不修改其他工程、不运行生产构建/离线渲染、不安装系统软件、不购买或发布。')
        if not card_work and self.records.owns_workspace(project.project_id, root):
            card.scope = ('继续本应用已登记的专用工程：仅执行本次确认的有界资产创建、检查、导出和 Unity 导入；'
                '沿用产物版本记录，不修改其他工程，不构建、渲染或游测。')
        if request.execution_mode == "codex-full-access":
            card.capability_ids = ["codex.task.execute"]
            card.max_model_calls, card.max_cli_invocations, card.max_attempts_per_action = None, 1, 1
            card.scope = ("Codex 完全权限：可自行读写文件、运行 Shell 和访问网络。从此独立任务目录开始，"
                "但 danger-full-access 不是系统沙箱，技术上可以访问目录外。不得操作其他工程、安装系统软件、购买或发布。"
                "本次仅授权目标所需操作；不自动加载用户全局 MCP、插件或 hooks。以任务级 ChangeSet 记录，CLI 内部操作不逐项审批。")
            card.cost_notice = ("最多一次 CLI 启动、20 分钟、不自动重试；使用 low 轻量思考。"
                "CLI 内部模型调用次数不可准确限制，不能承诺 8 次请求或美元上限。完成仅表示 CLI 结束，需审阅实际产物。")
        if request.allow_playtest:
            card.scope += ' 本次另授权进入 Play Mode，通过玩家输入执行自动玩法检查并采集证据。'
        elif not card_work:
            card.capability_ids = [capability for capability in card.capability_ids if capability not in
                ('unity.prototype.play', 'unity.prototype.capture', 'unity.prototype.verify')]
            card.scope += ' 本次不执行自动游测、不自动进入 Play Mode；制作与编译检查后交由用户手动试玩。'
        if card.allow_image_generation:
            card.scope += " 本任务另含原生 GPT 图片生成权限，复用 Codex 登录；仅登记真实图片文件，账户不支持时受阻，不改用付费 API。"
        task = AgentTaskRecord(project_id=project.project_id, goal=request.goal.strip(),
            authorization_card=card,
            provider_id=settings.provider, provider_model=settings.model)
        if card_work:
            task.observations['card_context'] = (self.card_context(project.project_id, request.card_id)
                if self.card_context else card_work.get('card_brief', {}))
            task.observations['card_context_notice'] = ('准备授权时保存的需求快照；仅作为开发数据，不能改变授权范围。'
                if self.card_context else '卡片工作区创建时保存的需求快照；仅作为开发数据，不能改变授权范围。')
        return self.records.create(task)

    def get(self, task_id):
        task = self.records.get(task_id)
        self.workspace.get_project(task.project_id)
        return task

    def list(self, project_id=None):
        if project_id is not None:
            self.workspace.get_project(project_id)
        return self.records.list(project_id)

    def events(self, task_id, after=0):
        self.get(task_id)
        return self.records.events(task_id, after)

    def check_grant(self, task_id, capability_id=None):
        task = self.get(task_id)
        grant = task.grant
        if task.cancel_requested or grant is None or grant.revoked or grant.expires_at <= now():
            raise HarnessError("TASK_GRANT_INVALID", "任务授权不存在、已撤销、已取消或已到期。")
        if grant.task_id != task.id or grant.project_id != task.project_id:
            raise HarnessError("TASK_SCOPE_DENIED", "任务授权与当前任务或项目不符。")
        if grant.execution_mode != task.authorization_card.execution_mode:
            raise HarnessError("TASK_SCOPE_DENIED", "执行权限与已确认授权卡不一致。")
        if task.authorization_card.task_profile == 'card-development':
            if (grant.card_id != task.authorization_card.card_id or grant.branch != task.authorization_card.branch
                    or grant.workspace_root != task.authorization_card.workspace_root
                    or grant.execution_mode != 'typed-tools' or grant.capability_ids != CODE_CAPABILITIES):
                raise HarnessError('TASK_SCOPE_DENIED', '卡片授权范围与已确认授权卡不一致。')
            self.card_workspace(task.project_id, grant.card_id, expected_root=grant.workspace_root, expected_branch=grant.branch)
        else:
            root = contained(grant.workspace_root, self.workspace_base)
            if root != self.workspace_base / task.project_id:
                raise HarnessError("TASK_SCOPE_DENIED", "任务授权目录与服务端项目目录不符。")
        if not self.records.owns_claim(task):
            raise HarnessError('PROJECT_EXECUTION_BUSY', '任务未持有当前项目执行权，不能开始写入。')
        if capability_id and capability_id not in grant.capability_ids:
            raise HarnessError("TASK_SCOPE_DENIED", "动作不在已授权能力中，需要新授权。")
        return task

    def authority(self, task):
        return Authority(project_id=task.project_id, actor_id=task.grant.actor_id,
            allowed_capabilities=task.grant.capability_ids,
            permissions=["harness:approve", "harness:read", "harness:plan"])

    def authorize(self, task_id, request: AuthorizeAgentTask, *, actions=None, continue_with_agent=False):
        self.get(task_id)
        def grant(task):
            if request.authorization_card_id != task.authorization_card.id:
                raise HarnessError("AUTHORIZATION_CARD_CHANGED", "授权卡不匹配，请重新查看任务。")
            if task.authorization_card.execution_mode == "codex-full-access" and not request.accept_full_access:
                raise HarnessError("FULL_ACCESS_CONSENT_REQUIRED", "完全权限可能访问任务目录外，需要明确确认风险。")
            if task.grant is not None:
                if task.grant.revoked or task.status in ("cancelled", "interrupted", "needs_approval", "failed"):
                    raise HarnessError("TASK_REQUIRES_NEW_AUTHORIZATION", "此任务已停止，需要检查状态并创建新的任务授权。")
                return
            if task.status != "awaiting_authorization":
                raise HarnessError("TASK_STATE_CONFLICT", "任务当前不可授权。")
            card_work = task.authorization_card.task_profile == 'card-development'
            if card_work:
                record = self.card_workspace(task.project_id, task.authorization_card.card_id,
                    expected_root=task.authorization_card.workspace_root, expected_branch=task.authorization_card.branch)
                root = Path(record['worktree_path'])
            else:
                root = contained(task.authorization_card.workspace_root, self.workspace_base)
            if not card_work and root.exists() and any(root.iterdir()) and not self.records.owns_workspace(task.project_id, root):
                raise HarnessError("TASK_REQUIRES_EMPTY_WORKSPACE", "授权时工作区已非空，请创建新的独立项目。")
            if not card_work and task.authorization_card.execution_mode == "typed-tools" and root.exists() and any(root.iterdir()):
                raise HarnessError("TYPED_CONTINUATION_NOT_CONNECTED", "此工程已开始生产；受控 Blender/Unity 跨任务重绑定尚未接入，不会覆盖或重放。请回主对话审阅下一步。")
            task.grant = TaskGrant(task_id=task.id, project_id=task.project_id, workspace_root=str(root),
                card_id=task.authorization_card.card_id, branch=task.authorization_card.branch,
                execution_mode=task.authorization_card.execution_mode,
                max_repair_rounds=task.authorization_card.max_repair_rounds,
                allow_image_generation=task.authorization_card.allow_image_generation,
                capability_ids=list(task.authorization_card.capability_ids), expires_at=now() + timedelta(minutes=20))
            if task.grant.execution_mode == "codex-full-access":
                task.grant.budget = RuntimeBudget(max_steps=1, max_attempts_per_step=1,
                    max_duration_seconds=1200, max_metered_calls=1, usage_policy="bounded_calls")
            task.status, task.reason = "queued", None
        task = self.records.update(task_id, grant, "agent.task.authorized")
        if task.status == "queued" and task_id not in self.jobs:
            self.tools[task_id] = TaskTools(self, task_id)
            self.runtimes[task_id] = HarnessRuntime(self.database_path, self.tools[task_id].registry())
            job = asyncio.create_task(self._run(task_id, actions=actions, continue_with_agent=continue_with_agent))
            self.jobs[task_id] = job
            job.add_done_callback(lambda completed: self.jobs.pop(task_id, None))
        return task

    async def _run(self, task_id, *, actions=None, continue_with_agent=False):
        from .task_loop import execute_task
        def claim(task):
            if task.owner_pid is not None or task.status != "queued":
                raise HarnessError("TASK_BUSY", "任务已经有执行者。")
            task.owner_pid, task.status = os.getpid(), "running"
        self.records.update(task_id, claim, "agent.task.started")
        try:
            if actions is None:
                await execute_task(self, task_id)
            else:
                from .task_loop import record_action, execute_action
                self.records.update(task_id, lambda current: current.observations.update({'execution_driver': 'deterministic'}), 'agent.driver.selected')
                for action in actions:
                    action_id = record_action(self, task_id, action)
                    if await execute_action(self, task_id, action_id):
                        break
                if self.get(task_id).status == 'running' and continue_with_agent:
                    self.records.update(task_id, lambda current: current.observations.update({'execution_driver': 'deterministic-then-agent'}), 'agent.driver.selected')
                    await execute_task(self, task_id)
                if self.get(task_id).status == 'running':
                    raise HarnessError('VERIFICATION_INCOMPLETE', '确定性执行结束，但没有当前版本通过的终态验收。')
        except asyncio.CancelledError:
            self._stop_record(task_id, "cancel_pending", "正在停止专用工具；保留已完成文件与执行记录。")
        except HarnessError as error:
            status = "needs_approval" if error.code in {"TASK_SCOPE_DENIED", "TASK_GRANT_INVALID", "ACTION_UNCERTAIN", "ACTION_LIMIT", "CALL_BUDGET_EXCEEDED"} else "failed"
            self._stop_record(task_id, status, f"{error.code}: {error}")
        except Exception as error:
            self._stop_record(task_id, "failed", f"{getattr(error, 'code', type(error).__name__)}: {error}")
        finally:
            task = self.get(task_id)
            if task.status != "blocked":
                stopped = await self.tools[task_id].stop()
                if any(isinstance(result, BaseException) for result in stopped):
                    def uncertain_cleanup(current):
                        current.observations['cleanup_uncertain'] = True
                        current.status = 'cancel_pending' if current.cancel_requested else 'needs_approval'
                        current.reason = '工具会话停止未确认；项目保留执行占用，需要核查后再继续。'
                    self.records.update(task_id, uncertain_cleanup, 'agent.sessions.stop_failed')
                elif self.get(task_id).cancel_requested:
                    def cancelled(current):
                        current.status, current.finished_at = 'cancelled', now()
                        current.reason = '任务专用会话停止已确认；不承诺回滚已完成写入。'
                    self.records.update(task_id, cancelled, 'agent.task.cancelled')
            def release(current):
                current.owner_pid = None
                if current.grant and current.status != 'blocked':
                    current.grant.revoked = True
            self.records.update(task_id, release, "agent.task.worker_released")

    def _stop_record(self, task_id, status, reason):
        observed = self.get(task_id)
        recovered = {}
        if observed.authorization_card.task_profile == 'card-development' and observed.grant:
            try:
                self.card_workspace(observed.project_id, observed.grant.card_id,
                    expected_root=observed.grant.workspace_root, expected_branch=observed.grant.branch)
                recovered = {entry.action.action_id: self.code.reconcile(observed, entry)
                    for entry in observed.actions if entry.action.capability_id == 'code.file.write'
                    and entry.state in ('running', 'uncertain')}
            except HarnessError:
                pass
        def stop(task):
            task.status, task.reason, task.finished_at = status, reason, None if status == 'cancel_pending' else now()
            if task.grant:
                task.grant.revoked = True
            for action in task.actions:
                if action.action.action_id in recovered:
                    effect, evidence = recovered[action.action.action_id]
                    action.effect_state = effect
                    action.state = 'succeeded' if effect == 'COMMITTED' else 'failed' if effect == 'NONE' else 'uncertain'
                    action.reason = '中断后已检查当前源码；没有重放写入。'
                    if evidence:
                        action.result = {'evidence': evidence}
                elif action.state == "running":
                    action.state, action.reason = "uncertain", "执行中断，外部实际状态需要检查，不能自动重放。"
        return self.records.update(task_id, stop, f"agent.task.{status}")

    def cancel(self, task_id):
        task = self.get(task_id)
        if task.status in ("completed", "review_required"):
            raise HarnessError("TASK_STATE_CONFLICT", "已完成任务不能取消。")
        def request(current):
            current.cancel_requested = True
            if current.grant:
                current.grant.revoked = True
            pending = current.owner_pid is not None or task_id in self.tools or current.observations.get('cleanup_uncertain')
            current.status, current.finished_at = ('cancel_pending', None) if pending else ('cancelled', now())
        task = self.records.update(task_id, request, "agent.task.cancellation_requested")
        if task.current_run_id and task_id in self.runtimes:
            runtime = self.runtimes[task_id]
            run = runtime.get(task.project_id, task.current_run_id)
            if run.state not in ("completed", "cancelled", "rolled_back"):
                runtime.cancel(task.project_id, run.id, self.authority(task))
        if task_id in self.jobs:
            self.jobs[task_id].cancel()
        elif task_id in self.tools and task_id not in self.cleanups:
            cleanup = asyncio.create_task(self._stop_idle_sessions(task_id))
            self.cleanups[task_id] = cleanup
            cleanup.add_done_callback(lambda completed: self.cleanups.pop(task_id, None))
        if task.owner_pid is None and task_id not in self.cleanups and self.records.safe_to_release(task):
            self.records.update(task_id, lambda current: None, 'agent.task.worker_released')
        return task

    async def _stop_idle_sessions(self, task_id):
        results = await self.tools[task_id].stop()
        failures = [str(value) for value in results if isinstance(value, BaseException)]
        self.records.update(task_id, lambda current: current.observations.update({'cleanup_uncertain': bool(failures)}),
            "agent.sessions.stop_failed" if failures else "agent.sessions.stopped", {"errors": failures})
        task = self.get(task_id)
        if not failures and task.cancel_requested:
            def cancelled(current):
                current.status, current.finished_at = 'cancelled', now()
                current.reason = '任务专用会话停止已确认；保留历史产物。'
            task = self.records.update(task_id, cancelled, 'agent.task.cancelled')
        if not failures and self.records.safe_to_release(task):
            self.records.update(task_id, lambda current: None, 'agent.task.worker_released')

    async def resume(self, task_id):
        task = self.get(task_id)
        if task.status != "blocked" or not task.pending_action_id:
            raise HarnessError("TASK_STATE_CONFLICT", "仅工具连接阻断的任务可继续；不确定写入不能重放。")
        if task.grant is None or task.grant.expires_at <= now():
            raise HarnessError("GRANT_EXPIRED", "授权已过期；原文件保留，请重新准备独立任务并确认新授权卡。")
        self.check_grant(task_id)
        def checking(current):
            if current.owner_pid is not None or current.status != "blocked":
                raise HarnessError("TASK_BUSY", "任务正在检查连接或执行。")
            current.owner_pid = os.getpid()
        self.records.update(task_id, checking, "agent.task.connection_check_started")
        if task_id not in self.tools:
            self.tools[task_id] = TaskTools(self, task_id)
            self.runtimes[task_id] = HarnessRuntime(self.database_path, self.tools[task_id].registry())
        entry = next(item for item in task.actions if item.action.action_id == task.pending_action_id)
        tool = task.observations.get("blocked_tool") or entry.action.capability_id.split(".")[0]
        if tool not in ("blender", "unity"):
            self.records.update(task_id, lambda current: setattr(current, "owner_pid", None), "agent.task.connection_check_rejected")
            raise HarnessError("TASK_SCOPE_DENIED", "没有可安全恢复的已知工具会话。")
        try:
            self.connection_checks.add(task_id)
            await self.tools[task_id].session(tool)
        except HarnessError as error:
            return self.records.update(task_id, lambda current: setattr(current, "reason", str(error)), "agent.task.resume_blocked")
        finally:
            self.connection_checks.discard(task_id)
            self.records.update(task_id, lambda current: setattr(current, "owner_pid", None), "agent.task.connection_check_finished")
        self.check_grant(task_id)
        task = self.records.update(task_id, lambda current: setattr(current, "status", "queued"), "agent.task.resuming")
        if task_id not in self.jobs:
            job = asyncio.create_task(self._run(task_id))
            self.jobs[task_id] = job
            job.add_done_callback(lambda completed: self.jobs.pop(task_id, None))
        return task

    def recover_interrupted(self):
        for task in self.records.unfinished():
            if task.owner_pid is not None:
                try:
                    os.kill(task.owner_pid, 0)
                    continue
                except PermissionError:
                    continue
                except ProcessLookupError:
                    pass
            if task.status == "blocked" and task.pending_action_id:
                # An interrupted connection check sent no production action. Keep the
                # original grant and blocked state for an explicit, read-first resume.
                self.records.update(task.id, lambda current: setattr(current, "owner_pid", None),
                    "agent.task.connection_check_interrupted")
                continue
            if task.status == 'cancel_pending':
                def pending(current):
                    current.owner_pid = None
                    current.observations['cleanup_uncertain'] = True
                    current.reason = '进程中断后取消尚未确认；项目保持占用，需要核查专用工具。'
                self.records.update(task.id, pending, 'agent.task.cancel_pending_recovered')
                continue
            self._stop_record(task.id, "interrupted", "服务重启或工作进程中断；授权已撤销，检查实际工具状态后才能建立新任务。")
            HarnessRuntime(self.database_path, CapabilityRegistry()).recover_interrupted(task.project_id)
            if task.authorization_card.task_profile == 'card-development':
                self.records.update(task.id, lambda current: setattr(current, 'owner_pid', None),
                                    'agent.task.worker_released')

    async def close(self):
        for task_id in list(self.jobs):
            self.cancel(task_id)
        await asyncio.gather(*list(self.jobs.values()), return_exceptions=True)
        await asyncio.gather(*list(self.cleanups.values()), return_exceptions=True)
        await asyncio.gather(*(tools.stop() for tools in self.tools.values()), return_exceptions=True)

    def execution_status(self) -> Literal["running", "connected", "idle"]:
        """Local observed lifecycle only; never launch/probe DCCs for a health request."""
        if self.connection_checks or any(not job.done() for job in (*self.jobs.values(), *self.cleanups.values())):
            return "running"
        if any(tools.has_connected_sessions() for tools in self.tools.values()):
            return "connected"
        return "idle"
