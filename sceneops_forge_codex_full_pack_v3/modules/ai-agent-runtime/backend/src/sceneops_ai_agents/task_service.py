"""Server-owned task grants and lifecycle, composed around existing Harness runs."""
import asyncio
import json
import os
import sqlite3
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Literal
from sceneops_ai_provider import ProviderService
from sceneops_harness import Authority, CapabilityRegistry, HarnessError, HarnessRuntime, RuntimeBudget
from .task_models import (AgentTaskRecord, AuthorizationCard, AuthorizeAgentTask, PrepareAgentTask,
                          TaskGrant, now, PROTOTYPE_CAPABILITIES, TASK_CAPABILITIES,
                          ENVIRONMENT_SCENE_CAPABILITIES, card_code_capabilities,
                          project_demo_capabilities, project_demo_agent_capabilities,
                          GameOperationRequest, ContinueProjectDemoRequest)
from .task_models import BrowserObservationAuthorization
from .task_repository import AgentTaskRepository
from .task_tools import TaskTools, contained
from .production_store import ProductionStore
from .workspace_changes import git_workspace_changes


TERMINAL_TASK_STATES = {
    'needs_approval', 'completed', 'review_required', 'failed', 'cancelled', 'interrupted',
}


class AgentTaskService:
    def __init__(self, database_path, workspace_repository, data_dir, *, provider=None,
                 blender_factory=None, unity_factory=None, card_context=None, game_runtime=None,
                 pnpm_executable=None, project_assets=None, environment_scenes=None,
                 builtin_asset_install=None, builtin_asset_install_selected=None,
                 builtin_project_install_selected=None,
                 project_asset_install_selected=None,
                 project_demo_context=None, experience=None, export_context=None,
                 production_preparation=None, lookdev=None, production_card_context=None):
        from . import AgentRuntime
        self.database_path = Path(database_path)
        self.export_context = export_context
        self.experience = experience
        self.workspace = workspace_repository
        self.card_context = card_context
        self.project_demo_context = project_demo_context
        self.production_card_context = production_card_context
        self.lookdev = lookdev
        self.project_assets = project_assets
        self.environment_scenes = environment_scenes
        self.builtin_asset_install = builtin_asset_install
        self.builtin_asset_install_selected = builtin_asset_install_selected
        self.builtin_project_install_selected = builtin_project_install_selected
        self.project_asset_install_selected = project_asset_install_selected
        self.production_preparation = production_preparation
        self.data_dir = Path(data_dir).resolve()
        self.workspace_base = self.data_dir / "agent-workspaces"
        self.state_base = self.data_dir / "agent-tool-state"
        self.provider = provider or ProviderService(database_path)
        self.agents = AgentRuntime(self.provider)
        self.records = AgentTaskRepository(database_path)
        if game_runtime is None:
            from .game_runtime import GameProjectRuntime
            game_runtime = GameProjectRuntime(self.records, self.data_dir, pnpm_executable=pnpm_executable)
        self.game = game_runtime
        from .code_workspace import CodeWorkspace
        self.code = CodeWorkspace(self)
        self.records.recover_workspace_ownership(self.workspace_base)
        self.production = ProductionStore(database_path, self.data_dir, self.records)
        self.agents.image_resolver = self.resolve_model_image
        self.blender_factory, self.unity_factory = blender_factory, unity_factory
        self.jobs, self.tools, self.runtimes = {}, {}, {}
        self.cleanups = {}
        self.connection_checks = set()
        self.browser_jobs = {}
        self.recover_interrupted()

    def is_project_busy(self, project_id):
        return any(task.owner_pid is not None for task in self.records.list(project_id)
                   if task.project_id == project_id)

    def experience_context(self, task, *, call_key):
        """Take a fresh immutable memory snapshot for each actual model request."""
        if self.experience is None:
            return None
        use_key = f'task:{task.id}:call:{call_key}'
        preparation = task.observations.get('production_preparation_context') or {}
        snapshot = preparation.get('memory_context') or {}
        staged = [item['content'] for item in preparation.get('selected_details', [])
                  if item.get('identity', {}).get('kind') == 'experience' and item.get('status') == 'provided']
        if snapshot or staged or preparation:
            selected = []
            for item in (staged or snapshot.get('items', [])):
                try:
                    entry = self.experience.get_entry(item['id'], task.project_id)
                except (ValueError, sqlite3.Error) as error:
                    return self.experience.unavailable_context(task.project_id, use_key,
                        f'所选经验暂不可读取：{type(error).__name__}', origin_key=f'task:{task.id}')
                if entry.enabled and entry.status != 'superseded':
                    selected.append(entry.model_dump(mode='json'))
            return self.experience.record_provided(task.project_id, use_key, selected,
                                                  origin_key=f'task:{task.id}')
        return self.experience.context(task.project_id, task.goal, use_key=use_key,
                                       origin_key=f'task:{task.id}')

    @staticmethod
    def preparation_without_memory(preparation):
        """Experience content is provided only by the current bounded snapshot."""
        result = {key: value for key, value in preparation.items() if key != 'memory_context'}
        if 'selected_details' in result:
            result['selected_details'] = [item for item in result['selected_details']
                if item.get('identity', {}).get('kind') != 'experience']
        if isinstance(result.get('recommendation'), dict):
            result['recommendation'] = {key: value for key, value in result['recommendation'].items()
                                        if key != 'experiences'}
        if isinstance(result.get('candidate_directory'), dict):
            result['candidate_directory'] = {**result['candidate_directory'], 'candidates': [item
                for item in result['candidate_directory'].get('candidates', []) if item.get('kind') != 'experience']}
        return result

    async def ensure_production_preparation(self, task_id):
        task = self.get(task_id)
        existing = task.observations.get('production_preparation')
        if isinstance(existing, dict):
            return existing
        if self.production_preparation is None:
            return None
        from sceneops_ai_context import ProductionPreparationRequest
        profile = task.authorization_card.task_profile
        if profile == 'project-export-agent':
            kind = 'export'
        elif profile == 'environment-scene':
            kind = 'scene'
        elif profile == 'unity-asset-edit' or any(
                capability.startswith('blender.asset.') for capability in task.authorization_card.capability_ids):
            kind = 'modeling'
        elif profile == 'project-demo-agent' and len(task.observations.get('demo_goals', [])) <= 1:
            kind = 'game_create'
        else:
            kind = 'game_modify'
        remaining_calls = max(0, task.grant.budget.max_metered_calls - task.model_calls_used)
        remaining_time = (None if task.grant.expires_at is None else
                          max(0.01, (task.grant.expires_at - now()).total_seconds()))
        context = (task.observations.get('project_demo_context') or
                   task.observations.get('card_context') or {})
        target_platform = 'web'
        if kind == 'export':
            platforms = task.observations.get('export_context', {}).get('platforms', [])
            target_platform = platforms[0].get('platform') if len(platforms) == 1 else None
        preparation_capabilities = list(task.authorization_card.capability_ids)
        if (profile == 'project-demo-agent' and task.grant.include_demo_assets
                and self.builtin_project_install_selected is not None):
            preparation_capabilities.append('code.demo_assets.install')
        if (profile in ('project-demo-agent', 'card-development') and task.grant.include_demo_assets
                and self.project_asset_install_selected is not None):
            preparation_capabilities.append('project.asset.provide')
        goals = task.observations.get('demo_goals')
        active_request_id = (goals[-1].get('request_id')
                             if isinstance(goals, list) and goals and isinstance(goals[-1], dict)
                             else None)
        request_key = (f'task-request:{task.id[-48:]}:{active_request_id}'
                       if active_request_id else f'task:{task.id}')
        request = ProductionPreparationRequest(
            project_id=task.project_id, request_key=request_key, production_kind=kind,
            requirement=task.goal[:20000], confirmed_direction=json.dumps(context, ensure_ascii=False)[:10000],
            target_platform=target_platform,
            current_state={'task_profile': profile, 'workspace_id': task.grant.workspace_id},
            available_capability_ids=list(dict.fromkeys(preparation_capabilities)),
            # Keep one metered call for the primary production agent. The selector
            # is skipped when the request cannot afford both calls.
            model_call_allowed=remaining_calls > 1, remaining_model_calls=remaining_calls,
            remaining_time_seconds=remaining_time)
        try:
            result = await self.production_preparation.prepare(request)
            selected_context = await self.production_preparation.selected_context(request, result, record_memory=False)
            # Task skills are loaded through the runtime's controlled skill loader.
            # Keep their identities here without injecting the same full text twice.
            if task.grant.execution_mode not in ('codex-full-access', 'agent-full-access'):
                for detail in selected_context.get('selected_details', []):
                    identity = detail.get('identity') if isinstance(detail, dict) else None
                    if isinstance(identity, dict) and identity.get('kind') == 'skill':
                        detail['content'] = {'loaded_by': 'task_skill_loader'}
        except asyncio.CancelledError:
            raise
        except Exception as error:
            payload = {'status': 'failed', 'recommendation': None,
                'failure_code': getattr(error, 'code', type(error).__name__),
                'failure_message': f'制作推荐不可用：{error}；主 Agent 继续读取当前工程和目录自行选择。'}
            self.records.update(task_id,
                lambda current: current.observations.update({
                    'production_preparation': payload,
                    'production_preparation_context': payload,
                }),
                'agent.production_preparation.failed', {'code': payload['failure_code']})
            return payload
        payload = result.model_dump(mode='json')
        attempted = result.call.status in ('succeeded', 'failed', 'cancelled')
        tokens = (result.call.usage or {}).get('total_tokens') if attempted else None
        def record(current):
            current.observations['production_preparation'] = payload
            current.observations['production_preparation_context'] = selected_context
            if attempted:
                current.model_calls_used += 1
                if isinstance(tokens, int):
                    current.model_tokens_known += tokens
                else:
                    current.budget_accounting_complete = False
                if result.call.cost_usd is not None:
                    current.cost_usd = (current.cost_usd or 0) + result.call.cost_usd
        self.records.update(task_id, record, 'agent.production_preparation.completed',
            {'status': result.status, 'preparation_id': result.preparation_id})
        return payload

    async def install_prepared_project_assets(self, task_id):
        task = self.get(task_id)
        profile = task.authorization_card.task_profile
        if (profile not in ('project-demo-agent', 'card-development')
                or not task.grant.include_demo_assets):
            return None
        preparation = task.observations.get('production_preparation')
        recommendation = preparation.get('recommendation') if isinstance(preparation, dict) else None
        builtin_selections = []
        project_selections = []
        if isinstance(recommendation, dict) and isinstance(recommendation.get('assets'), list):
            for item in recommendation['assets']:
                candidate_id = item.get('candidate_id') if isinstance(item, dict) else None
                if (profile == 'project-demo-agent' and isinstance(candidate_id, str)
                        and candidate_id.startswith('builtin:')):
                    builtin_selections.append({'asset_id': candidate_id.removeprefix('builtin:'),
                        'purpose': item.get('purpose'), 'reason': item.get('reason')})
                elif isinstance(candidate_id, str) and candidate_id.startswith('project:'):
                    project_selections.append({
                        'project_asset_id': candidate_id.removeprefix('project:'),
                        'version': item.get('version'), 'purpose': item.get('purpose'),
                        'reason': item.get('reason')})
        reports = {}
        failures = []
        if builtin_selections and self.builtin_project_install_selected is not None:
            try:
                reports['builtin'] = await asyncio.to_thread(
                    self.builtin_project_install_selected, task.project_id, builtin_selections)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                failures.extend({'candidate_id': f'builtin:{item["asset_id"]}',
                    'state': 'not_provided', 'reason': str(error)} for item in builtin_selections)
        if project_selections and self.project_asset_install_selected is not None:
            try:
                if profile == 'card-development':
                    reports['project'] = await asyncio.to_thread(
                        self.project_asset_install_selected, task.project_id,
                        project_selections, task.grant.card_id)
                else:
                    reports['project'] = await asyncio.to_thread(
                        self.project_asset_install_selected, task.project_id, project_selections)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                failures.extend({'candidate_id': f'project:{item["project_asset_id"]}',
                    'state': 'not_provided', 'reason': str(error)} for item in project_selections)
        if not reports and not failures:
            return None
        entries = [entry for report in reports.values()
                   for entry in report.get('catalog', {}).get('entries', [])]
        materialization = ([item for report in reports.values()
                            for item in report.get('materialization', [])] + failures)
        report = {'sources': reports, 'entries': entries,
                  'materialization': materialization,
                  'installed_files': [path for source in reports.values()
                                      for path in source.get('installed_files', [])],
                  'preserved_files': [path for source in reports.values()
                                      for path in source.get('preserved_files', [])],
                  'catalog_paths': [source.get('catalog_path') for source in reports.values()
                                    if source.get('catalog_path')],
                  'provision_failures': failures}
        def record(current):
            current.observations['selected_prepared_assets'] = report
            if 'builtin' in reports:
                current.observations['selected_builtin_assets'] = reports['builtin']
            if 'project' in reports:
                current.observations['selected_project_assets'] = reports['project']
            preparation = current.observations.get('production_preparation')
            if isinstance(preparation, dict):
                preparation['materialization'] = materialization
            context = current.observations.get('production_preparation_context')
            if isinstance(context, dict):
                context['materialization'] = materialization
        self.records.update(task_id, record,
            'agent.production_assets.provided',
            {'catalog_paths': report['catalog_paths'],
             'installed_count': len(report['installed_files']),
             'selected_count': len(builtin_selections) + len(project_selections),
             'failure_count': len(failures)})
        return report

    def inspect_prepared_asset_usage(self, task_id, workspace_root):
        """Record source-level references to selected assets without claiming runtime proof."""
        task = self.get(task_id)
        report = (task.observations.get('selected_prepared_assets') or
                  task.observations.get('selected_builtin_assets'))
        entries = report.get('entries') if isinstance(report, dict) else None
        if entries is None and isinstance(report, dict):
            catalog = report.get('catalog')
            entries = catalog.get('entries') if isinstance(catalog, dict) else None
        if not isinstance(entries, list) or not entries:
            return None
        root = Path(workspace_root).resolve(strict=True)
        ignored = {'.git', 'node_modules', 'dist', '.sceneops', '.vite', 'coverage'}
        readable_suffixes = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json',
                             '.html', '.css', '.scss', '.vue', '.svelte'}
        source_files = []
        catalog_paths = set(report.get('catalog_paths', [])) if isinstance(report, dict) else set()
        if isinstance(report, dict) and report.get('catalog_path'):
            catalog_paths.add(report['catalog_path'])
        for directory, names, filenames in os.walk(root):
            relative_directory = Path(directory).relative_to(root)
            if relative_directory.parts[:2] == ('public', 'sceneops-assets'):
                names[:] = []
                continue
            names[:] = [name for name in names if name not in ignored]
            base = Path(directory)
            for filename in filenames:
                path = base / filename
                if path.relative_to(root).as_posix() in catalog_paths:
                    continue
                if path.suffix.lower() not in readable_suffixes:
                    continue
                try:
                    if path.is_symlink() or path.stat().st_size > 1_048_576:
                        continue
                    source_files.append((path, path.read_text(encoding='utf-8')))
                except (OSError, UnicodeError):
                    continue
        references = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            asset_id = entry.get('source_asset_id') or entry.get('asset_id')
            candidate_id = (f'project:{entry["project_asset_id"]}'
                            if entry.get('project_asset_id') else f'builtin:{asset_id}')
            url = entry.get('url')
            needles = {str(asset_id) + '.glb'} if asset_id else set()
            if isinstance(url, str):
                needles.update({url, url.lstrip('/')})
                if not entry.get('project_asset_id'):
                    needles.add(Path(url).name)
            paths = sorted({path.relative_to(root).as_posix()
                            for path, text in source_files if any(needle in text for needle in needles)})
            references.append({'candidate_id': candidate_id,
                'actual_reference': 'referenced' if paths else 'not_observed',
                'reference_paths': paths})

        adjustments = [{'candidate_id': item.get('candidate_id'),
            'state': 'provision_failed',
            'reason': item.get('reason') or '所选资产未能提供，主制作不能假定该文件存在。',
            'evidence_source': 'materialization'}
            for item in report.get('materialization', [])
            if isinstance(item, dict) and item.get('state') in ('not_provided', 'not_adopted')]
        adjustments.extend({'candidate_id': item['candidate_id'],
            'state': 'selected_reference_not_observed',
            'reason': '源码扫描未观察到所选资产的真实 URL；这可能是未采用或需要进一步运行核查。',
            'evidence_source': 'source-scan'}
            for item in references if item['actual_reference'] == 'not_observed')

        def record(current):
            current.observations['selected_asset_usage'] = references
            current.observations['production_preparation_adjustments'] = adjustments
            preparation = current.observations.get('production_preparation')
            if isinstance(preparation, dict):
                preparation['actual_usage'] = references
                preparation['adjustments'] = adjustments
            context = current.observations.get('production_preparation_context')
            if isinstance(context, dict):
                context['actual_usage'] = references
                context['adjustments'] = adjustments
        self.records.update(task_id, record, 'agent.production_assets.inspected',
                            {'referenced_count': sum(item['actual_reference'] == 'referenced'
                                                     for item in references),
                             'adjustment_count': len(adjustments)})
        return references

    def record_prepared_asset_runtime_status(self, task_id, delivery):
        task = self.get(task_id)
        if not isinstance(task.observations.get('selected_prepared_assets'), dict):
            return None
        run = delivery.get('run') if isinstance(delivery, dict) else None
        status = {
            'project_pipeline': ('passed' if isinstance(run, dict) and run.get('passed') is True
                                 else 'failed' if isinstance(run, dict) else 'not_run'),
            'asset_visual_validation': 'not_verified',
            'reason': '工程检查或预览启动不能单独证明所选资产已在画面中正确加载。',
        }
        def record(current):
            current.observations['selected_asset_runtime_validation'] = status
            preparation = current.observations.get('production_preparation')
            if isinstance(preparation, dict):
                preparation['runtime_validation'] = status
        self.records.update(task_id, record, 'agent.production_assets.runtime_status', status)
        return status

    def _memory_sources(self, task_id):
        task = self.get(task_id)
        goals = task.observations.get('demo_goals', [])
        initial_goal = goals[0]['goal'] if goals else task.goal
        sources = [dict(id=f'task:{task.id}:goal', kind='message', role='user',
            text=initial_goal, created_at=task.created_at.isoformat(), evidence_status='user_statement')]
        sources.extend(dict(id=f"task:{task.id}:request:{goal['request_id']}", kind='message',
            role='user', text=goal['goal'], created_at=goal['accepted_at'], evidence_status='user_statement')
            for goal in goals)
        observed = {}
        cursor = 0
        while True:
            page = self.events(task_id, cursor)
            for event in page.events:
                if event.event_type == 'agent.action.observed':
                    observed[event.payload['action_id']] = event.occurred_at.isoformat()
                if event.event_type == 'agent.codex.activity':
                    activity = event.payload.get('activity', {})
                    if activity.get('type') in ('message_completed', 'assistant_message') and activity.get('text'):
                        sources.append(dict(id=f'task:{task.id}:event:{event.sequence}', kind='message',
                            role='assistant', text=activity['text'], created_at=event.occurred_at.isoformat(),
                            evidence_status='reported'))
            if not page.events:
                break
            cursor = page.next_cursor
        for entry in task.actions:
            action_id = entry.action.action_id
            if action_id not in observed:
                continue
            native = entry.action.capability_id in ('codex.task.execute', 'agent.task.execute')
            status = 'unknown' if entry.state == 'uncertain' or entry.effect_state == 'UNKNOWN' else 'reported' if native else 'observed'
            sources.append(dict(id=f'task:{task.id}:action:{action_id}:{observed[action_id]}', kind='action', role='tool',
                text=json.dumps(dict(capability=entry.action.capability_id, state=entry.state,
                    reason=entry.reason, result=entry.result, run_ids=entry.run_ids,
                    source_ref=f'task-action://{action_id}/result'), ensure_ascii=False),
                created_at=observed[action_id], evidence_status=status))
            verification = entry.verification_result
            if verification is not None:
                verified = (verification.execution_status == 'COMPLETED'
                    and verification.verdict in ('PASS', 'FAIL') and entry.effect_state != 'UNKNOWN')
                sources.append(dict(id=f'task:{task.id}:verification:{action_id}:{observed[action_id]}', kind='verification',
                    role='tool', text=verification.model_dump_json(), created_at=observed[action_id],
                    evidence_status='verified' if verified else 'unknown'))
        # Worker status is a runtime observation, never proof that the business goal passed.
        sources.append(dict(id=f'task:{task.id}:settled:{task.updated_at.isoformat()}', kind='action',
            role='tool', text=json.dumps(dict(task_id=task.id, status=task.status, reason=task.reason)),
            created_at=task.updated_at.isoformat(), evidence_status='observed'))
        for source in sources:
            source['origin_key'] = f'task:{task.id}'
        return sources

    def memory_source(self, project_id, source_id):
        # The task service owns source resolution, including project ownership.
        task = next((item for item in self.list(project_id)
                     if source_id.startswith(f'task:{item.id}:')), None)
        if task is None:
            return None
        return next((source for source in self._memory_sources(task.id)
                     if source['id'] == source_id), None)

    def record_experience(self, task_id):
        if self.experience is not None:
            task = self.get(task_id)
            self.experience.record_sources(task.project_id, self._memory_sources(task_id))

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

    def project_demo_workspace(self, project_id, workspace_id=None, *, expected_root=None):
        try:
            record = self.workspace.get_project_demo_workspace(project_id, workspace_id)
        except (ValueError, KeyError) as error:
            raise HarnessError('PROJECT_DEMO_WORKSPACE_INVALID', str(error)) from error
        root = Path(record['workspace_root'])
        if (not root.is_absolute() or root.resolve() != root or not root.is_dir()
                or record.get('project_id') != project_id
                or (workspace_id is not None and record.get('workspace_id') != workspace_id)
                or (expected_root is not None and str(root) != expected_root)):
            raise HarnessError('TASK_SCOPE_DENIED', '项目 Demo 工作区登记已改变，需要重新审阅。')
        return record

    async def run_export_task(self, task_id, *, on_event=None, cancel_event=None):
        from .native_export import run_export_task
        return await run_export_task(self, task_id, on_event=on_event, cancel_event=cancel_event)

    def prepare_export_task(self, project_id, export_id, goal):
        from .native_export import prepare_export_task
        return prepare_export_task(self, project_id, export_id, goal)

    def prepare(self, request: PrepareAgentTask):
        if request.task_profile == "project-export-agent":
            return self.prepare_export_task(request.project_id, request.export_id, request.goal)
        if request.task_profile=='unity-asset-edit':
            raise HarnessError('TASK_SCOPE_DENIED','请从实际资产入口准备独立 Unity 目标。')
        if not request.goal.strip():
            raise HarnessError("TASK_GOAL_REQUIRED", "请输入任务目标。")
        settings = self.provider.settings()
        if request.native_production and (request.task_profile != 'project-demo-agent'
                or request.execution_mode != 'agent-full-access'
                or settings.provider not in ('codexcli', 'codebuddycli', 'openai-compatible')):
            raise HarnessError('CLI_PROVIDER_REQUIRED', '原生制作需要 Codex harness 或 CodeBuddy harness 和登记的游戏工作区。')
        if request.execution_mode == "codex-full-access" and settings.provider != "codexcli":
            raise HarnessError("CODEX_PROVIDER_REQUIRED", "完全权限任务需要先明确选择 Codex CLI 提供方。")
        if request.execution_mode == "agent-full-access" and settings.provider not in ('codexcli', 'codebuddycli', 'openai-compatible'):
            raise HarnessError('CLI_PROVIDER_REQUIRED', '当前提供方不支持 Agent 原生执行。')
        if request.execution_mode == "agent-full-access" and request.task_profile not in ('card-development', 'project-demo-agent'):
            raise HarnessError('TASK_SCOPE_DENIED', '原生会话需要已登记的卡片或项目工程。')
        if request.allow_image_generation and request.execution_mode not in ("codex-full-access", "agent-full-access"):
            raise HarnessError("IMAGE_PROVIDER_REQUIRED", "登录态 GPT 图片目前需要明确选择 Codex CLI 完全权限；不会自动改用付费 API。")
        project = (self.workspace.get_project(request.project_id) if request.project_id
                   else self.workspace.create_project("Agent · " + request.goal.strip()[:60]))
        card_work = (self.card_workspace(project.project_id, request.card_id)
                     if request.task_profile == 'card-development' else None)
        scene_work = request.task_profile == 'environment-scene'
        project_work = request.task_profile in ('project-demo', 'project-demo-agent')
        demo_work = self.workspace.open_project_demo_workspace(project.project_id) if project_work else None
        root = (Path(card_work['worktree_path']) if card_work else Path(demo_work['workspace_root'])
                if demo_work else contained(self.workspace_base / project.project_id, self.workspace_base))
        if not card_work and not scene_work and not project_work and root.exists() and any(root.iterdir()) and not self.records.owns_workspace(project.project_id, root):
            raise HarnessError("TASK_REQUIRES_EMPTY_WORKSPACE", "Agent 任务只能使用独立空目录，不能接管已有项目文件。")
        if not card_work and not scene_work and not project_work and request.execution_mode == "typed-tools" and root.exists() and any(root.iterdir()):
            raise HarnessError("TYPED_CONTINUATION_NOT_CONNECTED", "此应用工程已有内容，受控 Blender/Unity 跨任务会话重绑定尚未接入。不会重放或覆盖；可在主对话明确选择 Codex 完全权限继续，或创建新项目。")
        card = AuthorizationCard(workspace_root=str(root), execution_mode=request.execution_mode,
            source_write_paths=request.source_write_paths,
            allow_image_generation=request.allow_image_generation, allow_playtest=request.allow_playtest,
            allow_game_execution=request.allow_game_execution,
            include_demo_assets=request.include_demo_assets, alignment_id=request.alignment_id,
            allow_dependency_install=request.allow_dependency_install,
            task_profile=request.task_profile, card_id=request.card_id,
            workspace_id=demo_work['workspace_id'] if demo_work else request.card_id if card_work else None,
            allow_blender_edit=request.allow_blender_edit,
            allow_browser_observation=request.allow_browser_observation,
            allow_browser_interaction=request.allow_browser_interaction,
            allow_model_image_input=request.allow_model_image_input,
            branch=card_work['branch'] if card_work else None,
            scene_write_object_ids=list(request.selected_scene_object_ids))
        if card_work:
            card.capability_ids = card_code_capabilities(card)
            card.scope = ('仅此项目的已登记卡片分支：读取有界 UTF-8 源码，按精确前文创建或修改代码文件；'
                '每文件最多 64 KiB、每任务最多 32 个文件写入动作与累计 512 KiB 新内容。'
                '可按精确前文修改用户已有改动；拒绝隐藏路径、链接、二进制与依赖锁文件。'
                '不执行源码、Shell、安装、Git 修改、构建或游测；完成后必须人工审阅。')
            if card.allow_game_execution:
                card.max_model_calls = 16
                card.scope = ('仅此项目的已登记卡片分支：读取和增量修改有界 UTF-8 源码；执行固定的 TypeScript 检查、'
                    'Vite 构建，并从该分支的 dist 在 127.0.0.1 随机端口启动应用自有预览。'
                    'Agent 不能提供 Shell 命令、工作目录、端口或环境变量；不合并分支、不发布。')
                card.cost_notice = ('最多 16 次模型请求（含读取、修复和验证），20 分钟；固定工程命令会真实运行，'
                    '本地预览只服务本卡片当前构建。模型费用可能未知。')
                if card.allow_dependency_install:
                    card.scope += (' 本次另授权在该游戏工程内执行一次或多次 pnpm 依赖准备；安装脚本禁用，'
                        '网络访问仅用于工程声明的依赖。')
                else:
                    card.scope += ' 本次未授权安装依赖；依赖缺失时 Agent 必须报告。'
            if card.include_demo_assets:
                card.scope += ' 本次另授权将内置角色、建筑和场景道具素材放入本卡片分支；已有素材文件保持不变。'
            if card.allow_browser_interaction:
                card.scope += ' 本次允许测试构建、独立浏览器状态重置、暂停/恢复、有限键盘输入、诊断回读与截图；不包含任意脚本或外部访问，期限与本次授权相同，取消时撤销。'
            if card.allow_browser_observation:
                card.scope += (' 本次允许用独立浏览器执行当前登记构建，采集 current-view 截图和浏览器错误；'
                    '只访问该构建预览，不使用用户会话、不自动操作角色、不做视觉模型评审。'
                    '此只观察授权在代码任务结束后保留至本次20分钟期限，单次最长35秒；取消时撤销。')
            if card.allow_model_image_input:
                card.scope += (' 本次另授权把当前任务浏览器检查登记的截图版本作为下一次决策模型的图片输入；'
                    '仅限应用自有产物副本，不接受模型或客户端路径。提供方或模型未确认支持时不发送。')
        elif project_work:
            if self.project_assets is None or self.environment_scenes is None or self.project_demo_context is None:
                raise HarnessError('PROJECT_DEMO_NOT_CONNECTED', '项目 Demo 的方向、资产或场景服务尚未连接。')
            if request.task_profile == 'project-demo':
                card.capability_ids = project_demo_capabilities(card)
                card.max_model_calls = 0
                card.max_attempts_per_action = 2
                card.scope = ('仅此项目登记的 Demo 工作区：通过公开服务保存门配方、两个共享实例和 KeyDoor 参数，'
                    '把所选场景与资产版本物化为派生运行输入，并执行固定 TypeScript 检查、Vite 构建与本地预览。'
                    '不调用制作模型，不提交、合并或发布；构建失败时保留上一可玩候选。')
                card.cost_notice = ('最多 32 个固定类型化步骤、20 分钟；修复与更新累计使用同一任务预算和期限。'
                    '依赖准备只运行工程声明的 pnpm 依赖，安装脚本禁用。')
            else:
                card.capability_ids = project_demo_agent_capabilities(card)
                card.max_model_calls = 28
                card.max_duration_seconds = 1800
                card.max_attempts_per_action = 2
                card.scope = ('仅此项目登记的 Demo 工作区：真实制作模型可读取现有源码、资产与场景，通过公开服务'
                    '创建或更新程序化门配方、实例与 KeyDoor 参数，并按精确前文修改普通游戏源码。'
                    'SceneOps 派生内容、测试适配器、依赖锁和构建输出不可作为编辑源。模型可执行固定检查、构建、'
                    '本地预览及本次授权的浏览器检查；不接受任意 Shell、目录、端口或环境变量，不提交、合并或发布。')
                card.cost_notice = ('整个任务累计最多 28 次模型请求、32 个类型化动作和 30 分钟；追加目标与修复'
                    '沿用相同计数和期限，不自动扩大能力。依赖准备禁用安装脚本；模型费用可能未知。')
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
        elif scene_work:
            if self.project_assets is None or self.environment_scenes is None:
                raise HarnessError('ENVIRONMENT_SCENE_NOT_CONNECTED', '项目资产或环境场景服务尚未连接。')
            scene = self.environment_scenes.get(project.project_id)
            selected = [item for item in scene.objects if item.id in request.selected_scene_object_ids]
            if len(selected) != len(request.selected_scene_object_ids):
                raise HarnessError('SCENE_OBJECT_NOT_FOUND', '当前场景中没有选中的对象；不会猜测其他 ID。')
            card.capability_ids = list(ENVIRONMENT_SCENE_CAPABILITIES)
            card.scope = ('仅修改当前项目环境场景中已列出的对象变换：'
                + '、'.join(request.selected_scene_object_ids)
                + '。本任务只允许一次成功变换；可读取本项目资产版本与最新场景，以当前场景版本进行冲突检查，'
                  '保存新场景版本并回读。不得新增、删除或跨项目读取对象；不修改运行游戏工程。')
            card.cost_notice = ('最多 8 次模型请求（含资产/场景读取、修改和回读），20 分钟；'
                '场景写入使用现有版本冲突保护，模型费用可能未知。')
        if not card_work and not scene_work and not project_work and self.records.owns_workspace(project.project_id, root):
            card.scope = ('继续本应用已登记的专用工程：仅执行本次确认的有界资产创建、检查、导出和 Unity 导入；'
                '沿用产物版本记录，不修改其他工程，不构建、渲染或游测。')
        if request.execution_mode in ("codex-full-access", "agent-full-access"):
            card.capability_ids = ["agent.task.execute" if request.execution_mode == 'agent-full-access' else "codex.task.execute"]
            if request.include_demo_assets and not project_work:
                card.capability_ids.append('code.demo_assets.install')
            card.max_model_calls, card.max_cli_invocations, card.max_attempts_per_action = None, 1, 1
            timeout_minutes = getattr(settings, 'agent_timeout_minutes', None)
            card.max_duration_seconds = None if timeout_minutes is None else timeout_minutes * 60
            duration_notice = '不设运行时限' if timeout_minutes is None else f'最长 {timeout_minutes} 分钟'
            card.scope = ("Agent 原生执行权限：可自行读写文件、运行 Shell 和访问网络。从此独立任务目录开始，"
                "但 danger-full-access 不是系统沙箱，技术上可以访问目录外。不得操作其他工程、安装系统软件、购买或发布。"
                "本次仅授权目标所需操作；不自动加载用户全局 MCP、插件或 hooks。以任务级 ChangeSet 记录，CLI 内部操作不逐项审批。")
            card.cost_notice = (f"最多一次 CLI 启动、{duration_notice}、不自动重试；使用当前选择的模型与思考强度。"
                "制作开始前最多另调用一次独立推荐模型。CLI 内部模型调用次数不可准确限制，"
                "不能承诺 8 次请求或美元上限。完成仅表示 CLI 结束，需审阅实际产物。")
        if project_work and request.execution_mode == 'agent-full-access':
            card.scope += (' 本次绑定已登记项目工作目录，CLI 返回后由应用自动运行固定工程检查、构建和本地预览；'
                '每步记录真实结果，失败停止后续步骤。')
            if card.include_demo_assets:
                card.scope += (' 本次另授权准备模型推荐的内置资产及其依赖；只复制所选条目，'
                               '已有用户文件保持不变。')
            card.scope += (' 本次允许工程声明的依赖准备，禁用安装脚本。'
                if card.allow_dependency_install else ' 本次未授权安装依赖，缺失时必须报告。')
        if request.allow_playtest:
            card.scope += ' 本次另授权进入 Play Mode，通过玩家输入执行自动玩法检查并采集证据。'
        elif not card_work:
            card.capability_ids = [capability for capability in card.capability_ids if capability not in
                ('unity.prototype.play', 'unity.prototype.capture', 'unity.prototype.verify')]
            card.scope += ' 本次不执行自动游测、不自动进入 Play Mode；制作与编译检查后交由用户手动试玩。'
        if card.allow_image_generation:
            card.scope += " 本任务另含原生 GPT 图片生成权限，复用 Codex 登录；仅登记真实图片文件，账户不支持时受阻，不改用付费 API。"
        if request.source_write_paths is not None:
            from .code_workspace import read_source
            for path in request.source_write_paths:
                if read_source(root, path) is None:
                    raise HarnessError('CODE_FILE_MISSING', '精修范围必须选择当前工程中已有的源码文件。')
            card.scope += ' 本次只允许修改以下文件：' + '、'.join(request.source_write_paths) + '。其他源码可读取作为上下文，不能修改；需要扩大范围时请结束并重新选择。'
        if card.allow_blender_edit:
            card.scope += ' 本次另允许 Blender 原生资产编辑，并按版本化三方合并升级登记工程的运行加载代码，保留不冲突的自定义修改。'
        if request.native_production:
            from .native_bridge import native_tool_capabilities
            card.permission_mode = request.permission_mode
            card.capability_ids = ['agent.task.execute', *native_tool_capabilities(card)]
            if request.permission_mode == 'scoped':
                card.scope = ('在登记游戏工作区完成已确认简报。采用 CLI 常规权限策略，不自动提升权限；'
                    '仅使用本次授权的依赖、浏览器和领域工具，不操作其他工程、不购买、提交或发布。')
        if request.native_production and card.allow_model_image_input:
            card.scope += ' 本次浏览器截图以图片附件交给当前制作模型查看，仅限本任务登记截图。'
        task = AgentTaskRecord(project_id=project.project_id, goal=request.goal.strip(),
            authorization_card=card,
            provider_id=settings.provider, provider_model=settings.model)
        if request.native_production:
            from .native_inputs import resolve_native_inputs
            task.observations['native_inputs'] = [{key: value for key, value in item.items()
                if key != 'absolute_path'} for item in resolve_native_inputs(root, request.input_paths)]
        if settings.provider == 'openai-compatible' and request.execution_mode == 'agent-full-access':
            task.observations['native_api_route'] = {'base_url': settings.base_url, 'wire_api': 'responses'}
        if card_work:
            context = (self.card_context(project.project_id, request.card_id)
                if self.card_context else card_work.get('card_brief', {}))
            if self.card_context and not context.get('technical_plan'):
                raise HarnessError('GAME_ARCHITECTURE_REQUIRED',
                    '第一次生成游戏代码前，请先在策划对话中选择游戏代码架构。不能从 Three.js 推断。')
            task.observations['card_context'] = context
            if request.include_demo_assets:
                from .demo_tasks import prepare_demo
                prepare_demo(task, request, context)
            task.observations['development_workspace'] = {
                'workspace_root': str(root), 'branch': card_work['branch'],
                'instruction': '先检查当前源码和技术方案，在当前架构内增量修改；不要重新生成整个工程。',
            }
            task.observations['card_context_notice'] = ('准备授权时保存的需求快照；仅作为开发数据，不能改变授权范围。'
                if self.card_context else '卡片工作区创建时保存的需求快照；仅作为开发数据，不能改变授权范围。')
        elif project_work:
            context = self.project_demo_context(project.project_id)
            from .demo_tasks import prepare_project_demo
            prepare_project_demo(task, request, context)
            task.observations['development_workspace'] = {
                'workspace_id': demo_work['workspace_id'], 'workspace_root': str(root),
                'instruction': ('使用项目登记根目录中的现有未采纳源码；资产、场景和行为参数走公开内容服务，'
                    '新玩法按精确前文增量修改普通源码。物化只替换 SceneOps 派生内容文件。'
                    if request.task_profile == 'project-demo-agent' else
                    '使用项目登记根目录中的现有未采纳源码；只替换 SceneOps 派生内容文件。'),
            }
        elif scene_work:
            task.observations['scene_selection'] = {
                'scene_version_at_prepare': scene.version,
                'selected_scene_object_ids': list(request.selected_scene_object_ids),
                'objects_at_prepare': [item.model_dump(mode='json') for item in selected],
                'notice': '选择信息是任务上下文；只有确认授权卡后才产生所列对象的变换写入权限。',
            }
        if request.native_production:
            from .creation_brief import initialize_brief
            initialize_brief(task)
        if request.alignment_id is not None:
            from .demo_tasks import create_demo_once
            return create_demo_once(self.records, task)
        return self.records.create(task)

    def get(self, task_id):
        task = self.records.get(task_id)
        self.workspace.get_project(task.project_id)
        return self._capture_workspace_changes(task)

    def archive(self, task_id, archived):
        task = self.records.get(task_id)
        self.workspace.get_project(task.project_id)
        return self.records.archive(task_id, archived)

    def list(self, project_id=None, archived=None):
        if project_id is not None:
            self.workspace.get_project(project_id)
        return [self._capture_workspace_changes(task) for task in self.records.list(project_id, archived)]

    def refresh_workspace_changes(self, project_id):
        """Persist missing review snapshots before production rows are projected."""
        self.workspace.get_project(project_id)
        for task in self.records.list(project_id):
            self._capture_workspace_changes(task)

    def _capture_workspace_changes(self, task):
        if ('native_workspace_changes' in task.observations
                or task.status not in TERMINAL_TASK_STATES
                or task.authorization_card.task_profile not in ('card-development', 'project-demo-agent')
                or task.authorization_card.execution_mode not in ('codex-full-access', 'agent-full-access')
                or task.grant is None):
            return task
        try:
            if task.authorization_card.task_profile == 'project-demo-agent':
                record = self.project_demo_workspace(task.project_id, task.grant.workspace_id,
                    expected_root=task.grant.workspace_root)
                root = record['workspace_root']
            else:
                record = self.card_workspace(task.project_id, task.grant.card_id,
                    expected_root=task.grant.workspace_root, expected_branch=task.grant.branch)
                root = record['worktree_path']
            snapshot = git_workspace_changes(Path(root))
        except (HarnessError, OSError, subprocess.SubprocessError):
            return task

        def capture(current):
            if ('native_workspace_changes' not in current.observations
                    and current.status in TERMINAL_TASK_STATES):
                current.observations['native_workspace_changes'] = snapshot
        return self.records.update(task.id, capture, 'agent.workspace_changes.captured', {
            'file_count': len(snapshot['files']), 'available': snapshot['available'],
        })

    def events(self, task_id, after=0):
        self.get(task_id)
        return self.records.events(task_id, after)

    def model_image_input(self, task):
        metadata = {"status": "not_authorized", "provider": task.provider_id,
                    "model": task.provider_model, "visual_reviewed": False}
        if not task.authorization_card.allow_model_image_input or not task.grant \
                or not task.grant.allow_model_image_input:
            return metadata
        support = (self.provider.image_input_support(task.provider_id, task.provider_model)
                   if hasattr(self.provider, 'image_input_support') else 'unknown')
        if support != 'supported':
            metadata["status"] = "provider_unsupported" if support == 'unsupported' else "provider_support_unknown"
            return metadata
        from .context_projection import project_game_diagnostics
        latest = project_game_diagnostics(task)["latest"]
        if latest.get("evidence_status") == "stale":
            metadata["status"] = "screenshot_stale"
            return metadata
        screenshot = latest.get("screenshot_reference")
        scope = latest.get("scope")
        if not isinstance(screenshot, dict) or not isinstance(scope, dict) \
                or not isinstance(scope.get("browser_run_id"), str):
            metadata["status"] = "no_current_screenshot"
            return metadata
        metadata.update({"status": "ready", **screenshot,
                         "browser_run_id": scope["browser_run_id"],
                         "build_run_id": scope.get("build_run_id"),
                         "check": scope.get("check") or "current-view"})
        return metadata

    def resolve_model_image(self, metadata):
        task_id = metadata.get("task_id")
        task = self.check_grant(task_id, "agent.next_action")
        if not task.authorization_card.allow_model_image_input or not task.grant.allow_model_image_input:
            raise HarnessError('MODEL_IMAGE_NOT_AUTHORIZED', '本任务没有授权向模型发送截图。')
        settings = self.provider.settings()
        if (settings.provider, settings.model) != (task.provider_id, task.provider_model):
            raise HarnessError('TASK_SCOPE_DENIED', '模型配置已改变，不能发送截图。')
        current = {**self.model_image_input(task), "task_id": task.id,
                   "project_id": task.project_id}
        if current != metadata or current.get("status") != "ready":
            raise HarnessError('MODEL_IMAGE_STALE', '登记截图已变化或不再代表当前源码。')
        return self.production.model_image_path(task, current["artifact_id"], current["version"],
                                                current["browser_run_id"])

    def check_grant(self, task_id, capability_id=None):
        task = self.get(task_id)
        grant = task.grant
        if capability_id and capability_id.startswith('blender.') and task.observations.get('native_production'):
            from datetime import datetime
            expires = task.observations.get('native_blender_expires_at')
            if not expires or datetime.fromisoformat(expires) <= now():
                raise HarnessError('TASK_GRANT_INVALID', 'Blender 编辑时段已到期，请重新打开编辑。')
        if (task.cancel_requested or grant is None or grant.revoked
                or (grant.expires_at is not None and grant.expires_at <= now())):
            raise HarnessError("TASK_GRANT_INVALID", "任务授权不存在、已撤销、已取消或已到期。")
        if grant.task_id != task.id or grant.project_id != task.project_id:
            raise HarnessError("TASK_SCOPE_DENIED", "任务授权与当前任务或项目不符。")
        if grant.source_write_paths != task.authorization_card.source_write_paths:
            raise HarnessError('TASK_SCOPE_DENIED', '授权文件范围已改变，不能继续执行。')
        if grant.source_write_paths is not None and grant.execution_mode != 'typed-tools':
            raise HarnessError('TASK_SCOPE_DENIED', '文件精修不能使用完全访问模式。')
        if grant.execution_mode != task.authorization_card.execution_mode:
            raise HarnessError("TASK_SCOPE_DENIED", "执行权限与已确认授权卡不一致。")
        if task.authorization_card.task_profile == 'card-development':
            expected_capabilities = (['agent.task.execute'] + (['code.demo_assets.install'] if grant.include_demo_assets else [])
                if grant.execution_mode == 'agent-full-access' else card_code_capabilities(task.authorization_card))
            legacy_capabilities = [item for item in expected_capabilities if item != 'agent.history.read']
            if (grant.card_id != task.authorization_card.card_id or grant.branch != task.authorization_card.branch
                    or grant.workspace_root != task.authorization_card.workspace_root
                    or grant.execution_mode not in ('typed-tools', 'agent-full-access')
                    or task.authorization_card.capability_ids not in (expected_capabilities, legacy_capabilities)
                    or grant.capability_ids != task.authorization_card.capability_ids
                    or grant.include_demo_assets != task.authorization_card.include_demo_assets
                    or grant.alignment_id != task.authorization_card.alignment_id
                    or grant.allow_game_execution != task.authorization_card.allow_game_execution
                    or grant.allow_blender_edit != task.authorization_card.allow_blender_edit
                    or grant.allow_browser_observation != task.authorization_card.allow_browser_observation
                    or grant.allow_browser_interaction != task.authorization_card.allow_browser_interaction
                    or grant.allow_model_image_input != task.authorization_card.allow_model_image_input
                    or grant.allow_dependency_install != task.authorization_card.allow_dependency_install):
                raise HarnessError('TASK_SCOPE_DENIED', '卡片授权范围与已确认授权卡不一致。')
            self.card_workspace(task.project_id, grant.card_id, expected_root=grant.workspace_root, expected_branch=grant.branch)
        elif task.authorization_card.task_profile in ('project-demo', 'project-demo-agent'):
            expected_capabilities = (['agent.task.execute']
                if grant.execution_mode == 'agent-full-access' and task.authorization_card.task_profile == 'project-demo-agent'
                else project_demo_agent_capabilities(task.authorization_card)
                if task.authorization_card.task_profile == 'project-demo-agent'
                else project_demo_capabilities(task.authorization_card))
            if task.observations.get('native_production'):
                from .native_bridge import native_tool_capabilities
                expected_capabilities = ['agent.task.execute', *native_tool_capabilities(task.authorization_card)]
            if (grant.permission_mode != task.authorization_card.permission_mode
                    or grant.workspace_id != task.authorization_card.workspace_id
                    or not grant.workspace_id or grant.card_id is not None or grant.branch is not None
                    or grant.workspace_root != task.authorization_card.workspace_root
                    or grant.execution_mode not in (('typed-tools', 'agent-full-access')
                        if task.authorization_card.task_profile == 'project-demo-agent' else ('typed-tools',))
                    or task.authorization_card.capability_ids not in (expected_capabilities,
                        [cap for cap in expected_capabilities if cap not in ('builtin.assets.list', 'code.demo_assets.install')],
                        [cap for cap in expected_capabilities if cap != 'environment.asset.rebind'],
                        [cap for cap in expected_capabilities if not cap.startswith('code.demo_runtime.')])
                    or grant.capability_ids != task.authorization_card.capability_ids
                    or grant.alignment_id != task.authorization_card.alignment_id
                    or grant.include_demo_assets != task.authorization_card.include_demo_assets
                    or grant.allow_game_execution != task.authorization_card.allow_game_execution
                    or grant.allow_blender_edit != task.authorization_card.allow_blender_edit
                    or grant.allow_browser_observation != task.authorization_card.allow_browser_observation
                    or grant.allow_browser_interaction != task.authorization_card.allow_browser_interaction
                    or grant.allow_model_image_input != task.authorization_card.allow_model_image_input
                    or grant.allow_dependency_install != task.authorization_card.allow_dependency_install):
                raise HarnessError('TASK_SCOPE_DENIED', '项目 Demo 授权与已确认方向或工作区不一致。')
            self.project_demo_workspace(task.project_id, grant.workspace_id,
                                        expected_root=grant.workspace_root)
        elif task.authorization_card.task_profile == 'project-export-agent':
            from .native_export import validate_export_grant
            validate_export_grant(self, task)
        elif task.authorization_card.task_profile == 'unity-asset-edit':
            from .unity_tasks import validate_unity_grant
            validate_unity_grant(self, task)
        elif task.authorization_card.task_profile == 'environment-scene':
            if (task.authorization_card.capability_ids != ENVIRONMENT_SCENE_CAPABILITIES
                    or grant.capability_ids != task.authorization_card.capability_ids
                    or grant.scene_write_object_ids != task.authorization_card.scene_write_object_ids
                    or not grant.scene_write_object_ids
                    or self.project_assets is None or self.environment_scenes is None):
                raise HarnessError('TASK_SCOPE_DENIED', '场景授权能力、对象范围或领域服务与确认卡不一致。')
            root = contained(grant.workspace_root, self.workspace_base)
            if root != self.workspace_base / task.project_id:
                raise HarnessError('TASK_SCOPE_DENIED', '任务授权目录与当前项目不一致。')
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
        prepared = self.get(task_id)
        # A same-conversation continuation can safely transfer only after the stopped
        # native task has a current Git-status snapshot. Capture it before claiming so
        # the first explicit retry does not depend on a prior UI refresh.
        self.refresh_workspace_changes(prepared.project_id)
        def grant(task):
            if request.authorization_card_id != task.authorization_card.id:
                raise HarnessError("AUTHORIZATION_CARD_CHANGED", "授权卡不匹配，请重新查看任务。")
            if task.authorization_card.execution_mode in ("codex-full-access", "agent-full-access") and task.authorization_card.permission_mode == "full" and not request.accept_full_access:
                raise HarnessError("FULL_ACCESS_CONSENT_REQUIRED", "完全权限可能访问任务目录外，需要明确确认风险。")
            from .creation_brief import confirm_brief
            confirm_brief(task, request.creation_brief_version)
            if task.grant is not None:
                if task.grant.revoked or task.status in ("cancelled", "interrupted", "needs_approval", "failed"):
                    raise HarnessError("TASK_REQUIRES_NEW_AUTHORIZATION", "此任务已停止，需要检查状态并创建新的任务授权。")
                return
            if task.authorization_card.alignment_id is not None:
                if task.authorization_card.task_profile in ('project-demo', 'project-demo-agent'):
                    from .demo_tasks import validate_project_demo_alignment
                    context = self.project_demo_context(task.project_id) if self.project_demo_context else {}
                    validate_project_demo_alignment(task.authorization_card.alignment_id, context)
                else:
                    from .demo_tasks import validate_demo_alignment
                    context = self.card_context(task.project_id, task.authorization_card.card_id) if self.card_context else {}
                    validate_demo_alignment(task.authorization_card.alignment_id, context)
            if task.status != "awaiting_authorization":
                raise HarnessError("TASK_STATE_CONFLICT", "任务当前不可授权。")
            export_work = task.authorization_card.task_profile == 'project-export-agent'
            card_work = task.authorization_card.task_profile == 'card-development'
            project_work = task.authorization_card.task_profile in ('project-demo', 'project-demo-agent')
            if card_work:
                record = self.card_workspace(task.project_id, task.authorization_card.card_id,
                    expected_root=task.authorization_card.workspace_root, expected_branch=task.authorization_card.branch)
                root = Path(record['worktree_path'])
            elif export_work:
                from .native_export import export_workspace
                root = export_workspace(self, task)
            elif project_work:
                record = self.project_demo_workspace(task.project_id,
                    task.authorization_card.workspace_id,
                    expected_root=task.authorization_card.workspace_root)
                root = Path(record['workspace_root'])
            else:
                root = contained(task.authorization_card.workspace_root, self.workspace_base)
            unity_work = task.authorization_card.task_profile == 'unity-asset-edit'
            if unity_work:
                from .unity_tasks import unity_target
                unity_target(self, task)
            scene_work = task.authorization_card.task_profile == 'environment-scene'
            if not card_work and not scene_work and not project_work and not unity_work and not export_work and root.exists() and any(root.iterdir()) and not self.records.owns_workspace(task.project_id, root):
                raise HarnessError("TASK_REQUIRES_EMPTY_WORKSPACE", "授权时工作区已非空，请创建新的独立项目。")
            if not card_work and not scene_work and not project_work and not unity_work and not export_work and task.authorization_card.execution_mode == "typed-tools" and root.exists() and any(root.iterdir()):
                raise HarnessError("TYPED_CONTINUATION_NOT_CONNECTED", "此工程已开始生产；受控 Blender/Unity 跨任务重绑定尚未接入，不会覆盖或重放。请回主对话审阅下一步。")
            duration_seconds = task.authorization_card.max_duration_seconds
            task.grant = TaskGrant(task_id=task.id, project_id=task.project_id, workspace_root=str(root),
                export_id=task.authorization_card.export_id,
                source_write_paths=task.authorization_card.source_write_paths,
                workspace_id=task.authorization_card.workspace_id,
                card_id=task.authorization_card.card_id, branch=task.authorization_card.branch,
                execution_mode=task.authorization_card.execution_mode,
                permission_mode=task.authorization_card.permission_mode,
                max_repair_rounds=task.authorization_card.max_repair_rounds,
                allow_image_generation=task.authorization_card.allow_image_generation,
                allow_game_execution=task.authorization_card.allow_game_execution,
                include_demo_assets=task.authorization_card.include_demo_assets,
                alignment_id=task.authorization_card.alignment_id,
                allow_blender_edit=task.authorization_card.allow_blender_edit,
                allow_browser_observation=task.authorization_card.allow_browser_observation,
                allow_browser_interaction=task.authorization_card.allow_browser_interaction,
                allow_model_image_input=task.authorization_card.allow_model_image_input,
                allow_dependency_install=task.authorization_card.allow_dependency_install,
                capability_ids=list(task.authorization_card.capability_ids),
                scene_write_object_ids=list(task.authorization_card.scene_write_object_ids),
                expires_at=(now() + timedelta(seconds=duration_seconds)
                            if duration_seconds is not None else None))
            if task.observations.get('native_production') and task.authorization_card.allow_blender_edit:
                task.observations['native_blender_expires_at'] = (now() + timedelta(minutes=30)).isoformat()
            if task.grant.execution_mode in ("codex-full-access", "agent-full-access"):
                task.grant.budget = RuntimeBudget(max_steps=2 if task.grant.include_demo_assets else 1, max_attempts_per_step=1,
                    max_duration_seconds=task.authorization_card.max_duration_seconds,
                    max_metered_calls=2, usage_policy="bounded_calls")
            elif task.authorization_card.max_model_calls is not None:
                task.grant.budget = RuntimeBudget(max_steps=64 if unity_work else 32,
                    max_attempts_per_step=task.authorization_card.max_attempts_per_action,
                    max_duration_seconds=task.authorization_card.max_duration_seconds,
                    max_metered_calls=task.authorization_card.max_model_calls, usage_policy='bounded_calls')
            renewing = bool(task.observations.get('demo_pending_authorization'))
            if renewing:
                task.grant.budget.max_steps = 32
            from .demo_continuation import apply_demo_continuation_window
            apply_demo_continuation_window(task)
            task.status, task.reason = ('review_required' if renewing else 'queued'), None
            if task.authorization_card.allow_browser_observation:
                task.browser_authorization = BrowserObservationAuthorization(
                    task_id=task.id, project_id=task.project_id, workspace_id=task.grant.workspace_id,
                    workspace_root=str(root),
                    card_id=task.grant.card_id, branch=task.grant.branch,
                    expires_at=task.grant.expires_at)
            if task.authorization_card.allow_browser_interaction:
                task.browser_interaction_authorization = BrowserObservationAuthorization(
                    task_id=task.id, project_id=task.project_id, workspace_id=task.grant.workspace_id,
                    workspace_root=str(root),
                    card_id=task.grant.card_id, branch=task.grant.branch,
                    expires_at=task.grant.expires_at)
        renewing = bool(self.get(task_id).observations.get('demo_pending_authorization'))
        task = self.records.update(task_id, grant, "agent.task.authorized")
        if renewing:
            previous_tools = self.tools.pop(task_id, None)
            if previous_tools:
                for session in previous_tools.sessions.values():
                    session.stop()
            self.runtimes.pop(task_id, None)
        if task.status == "queued" and task_id not in self.jobs:
            self.tools[task_id] = TaskTools(self, task_id)
            self.runtimes[task_id] = HarnessRuntime(self.database_path, self.tools[task_id].registry())
            job = asyncio.create_task(self._run(task_id, actions=actions, continue_with_agent=continue_with_agent))
            self.jobs[task_id] = job
            job.add_done_callback(lambda completed: self.jobs.pop(task_id, None))
        return task

    async def _run(self, task_id, *, actions=None, continue_with_agent=False,
                   project_demo_update=False):
        from .task_loop import execute_task
        def claim(task):
            if task.owner_pid is not None or task.status != "queued":
                raise HarnessError("TASK_BUSY", "任务已经有执行者。")
            task.owner_pid, task.status = os.getpid(), "running"
        self.records.update(task_id, claim, "agent.task.started")
        try:
            profile = self.get(task_id).authorization_card.task_profile
            if self.get(task_id).observations.get('native_delivery_only'):
                from .native_production import rebuild_production
                await rebuild_production(self, task_id)
                return
            await self.ensure_production_preparation(task_id)
            await self.install_prepared_project_assets(task_id)
            if profile == 'project-demo' or (profile == 'project-demo-agent' and project_demo_update):
                from .project_demo import run_project_demo
                await run_project_demo(self, task_id,
                    initialize_fixture=True if profile == 'project-demo' and not project_demo_update else False)
                return
            from .demo_tasks import install_authorized_demo
            if profile not in ('project-demo-agent', 'project-export-agent'):
                await install_authorized_demo(self, task_id)
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
            if (task.cancel_requested and task.authorization_card.task_profile in
                    ('card-development', 'project-demo', 'project-demo-agent')):
                try:
                    await self.game.stop_task_preview(task)
                except Exception as error:
                    self.records.update(task_id,
                        lambda current: current.observations.update({'cleanup_uncertain': True,
                            'preview_cleanup_error': str(error)}), 'agent.preview.stop_failed')
            keep_unity = (task.authorization_card.task_profile=='unity-asset-edit'
                          and task.status=='review_required' and not task.cancel_requested)
            if task.status != "blocked" and not keep_unity:
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
                        current.reason = ('本轮已停止；同一制作会话、当前工程和已有写入已保留，可继续下一轮。'
                            if current.observations.get('native_production') else
                            '任务专用会话停止已确认；不承诺回滚已完成写入。')
                    self.records.update(task_id, cancelled, 'agent.task.cancelled')
            def release(current):
                current.owner_pid = None
                if (current.grant and current.status != 'blocked'
                        and current.authorization_card.task_profile not in
                            ('project-demo', 'project-demo-agent', 'unity-asset-edit')):
                    current.grant.revoked = True
            self.records.update(task_id, release, "agent.task.worker_released")
            self.record_experience(task_id)

    def _stop_record(self, task_id, status, reason):
        observed = self.get(task_id)
        recovered = {}
        if observed.authorization_card.task_profile in ('card-development', 'project-demo-agent') and observed.grant:
            try:
                if observed.authorization_card.task_profile == 'card-development':
                    self.card_workspace(observed.project_id, observed.grant.card_id,
                        expected_root=observed.grant.workspace_root, expected_branch=observed.grant.branch)
                else:
                    self.project_demo_workspace(observed.project_id, observed.grant.workspace_id,
                        expected_root=observed.grant.workspace_root)
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
        self.cancel_browser_observation(task_id)
        def request(current):
            current.cancel_requested = True
            if current.browser_authorization:
                current.browser_authorization.revoked = True
            if current.browser_interaction_authorization:
                current.browser_interaction_authorization.revoked = True
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
        browser_job = self.browser_jobs.get(task_id)
        if browser_job:
            await asyncio.gather(browser_job, return_exceptions=True)
        results = await self.tools[task_id].stop()
        failures = [str(value) for value in results if isinstance(value, BaseException)]
        self.records.update(task_id, lambda current: current.observations.update({'cleanup_uncertain': bool(failures)}),
            "agent.sessions.stop_failed" if failures else "agent.sessions.stopped", {"errors": failures})
        task = self.get(task_id)
        if not failures and task.cancel_requested:
            def cancelled(current):
                current.status, current.finished_at = 'cancelled', now()
                current.reason = ('本轮已停止；同一制作会话、当前工程和已有写入已保留，可继续下一轮。'
                    if current.observations.get('native_production') else
                    '任务专用会话停止已确认；保留历史产物。')
            task = self.records.update(task_id, cancelled, 'agent.task.cancelled')
        if not failures and self.records.safe_to_release(task):
            self.records.update(task_id, lambda current: None, 'agent.task.worker_released')

    async def resume(self, task_id):
        task = self.get(task_id)
        if task.status != "blocked" or not task.pending_action_id:
            raise HarnessError("TASK_STATE_CONFLICT", "仅工具连接阻断的任务可继续；不确定写入不能重放。")
        if (task.grant is None
                or (task.grant.expires_at is not None and task.grant.expires_at <= now())):
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

    def update_project_demo(self, task_id):
        task = self.get(task_id)
        if task.observations.get('native_production'):
            from .native_production import continue_production
            from uuid import uuid4
            return continue_production(self, task, ContinueProjectDemoRequest(
                request_id=str(uuid4()), goal='物化工作台当前内容并更新试玩候选。'), build_only=True)
        if task.authorization_card.task_profile not in ('project-demo', 'project-demo-agent') or task.grant is None:
            raise HarnessError('PROJECT_DEMO_NOT_AUTHORIZED', '此任务不是已授权的项目 Demo。')
        if (task.grant.revoked or task.cancel_requested
                or (task.grant.expires_at is not None and task.grant.expires_at <= now())):
            raise HarnessError('TASK_GRANT_INVALID', '项目 Demo 更新仍使用原任务预算与期限；当前授权已失效。')
        if task.status not in ('completed', 'review_required') or task.owner_pid is not None:
            raise HarnessError('TASK_BUSY', '项目 Demo 正在更新，或当前状态不可再次更新。')
        from .demo_tasks import validate_project_demo_alignment
        context = self.project_demo_context(task.project_id) if self.project_demo_context else {}
        validate_project_demo_alignment(task.grant.alignment_id, context)
        self.project_demo_workspace(task.project_id, task.grant.workspace_id,
                                    expected_root=task.grant.workspace_root)
        def queue(current):
            current.status, current.reason, current.finished_at = 'queued', None, None
        task = self.records.update(task_id, queue, 'agent.task.authorized', {'update': True})
        if task_id not in self.tools:
            self.tools[task_id] = TaskTools(self, task_id)
            self.runtimes[task_id] = HarnessRuntime(self.database_path, self.tools[task_id].registry())
        job = asyncio.create_task(self._run(task_id, project_demo_update=True))
        self.jobs[task_id] = job
        job.add_done_callback(lambda completed: self.jobs.pop(task_id, None))
        return task

    def continue_project_demo(self, task_id, request: ContinueProjectDemoRequest):
        task = self.get(task_id)
        if task.observations.get('native_production'):
            from .native_production import continue_production
            return continue_production(self, task, request)
        if task.authorization_card.task_profile != 'project-demo-agent' or task.grant is None:
            raise HarnessError('PROJECT_DEMO_AGENT_REQUIRED', '此任务不是已授权的 D3 自主项目 Demo。')
        if (task.grant.revoked or task.cancel_requested
                or (task.grant.expires_at is not None and task.grant.expires_at <= now())):
            raise HarnessError('TASK_GRANT_INVALID', '追加目标沿用原任务预算与期限；当前授权已失效。')
        from .demo_tasks import validate_project_demo_alignment
        context = self.project_demo_context(task.project_id) if self.project_demo_context else {}
        validate_project_demo_alignment(task.grant.alignment_id, context)
        self.project_demo_workspace(task.project_id, task.grant.workspace_id,
                                    expected_root=task.grant.workspace_root)
        if any(v['owner'] == 'manual' and v['status'] in ('opening', 'editing')
               for v in task.observations.get('blender_candidates', {}).values()):
            raise HarnessError('BLENDER_SOURCE_BUSY', '请先完成手工 Blender 保存回流，再让 Agent 修改。')
        goals = task.observations.get('demo_goals', [])
        prior = next((item for item in goals if isinstance(item, dict)
                      and item.get('request_id') == request.request_id), None)
        if prior is not None:
            if (prior.get('goal') != request.goal.strip()
                    or prior.get('target') != (request.target.model_dump(mode='json') if request.target else None)):
                raise HarnessError('REQUEST_ID_CONFLICT', '同一追加请求 ID 不能更换目标。')
            return task
        resolved_target = None
        if request.target is not None:
            from .demo_workbench import resolve_target
            _, selected = resolve_target(self, task, request.target)
            resolved_target = request.target.model_dump(mode='json')
            if request.target.kind == 'source':
                resolved_target['resolved_path'] = selected.path
            elif request.target.kind == 'behavior':
                resolved_target['resolved_object_id'] = selected.id
        if task.status not in ('completed', 'review_required') or task.owner_pid is not None:
            raise HarnessError('TASK_BUSY', '项目 Demo 正在执行，或当前状态不可追加目标。')
        queued = False
        def queue(current):
            nonlocal queued
            history = current.observations.setdefault('demo_goals', [])
            prior = next((item for item in history if isinstance(item, dict)
                          and item.get('request_id') == request.request_id), None)
            if prior is not None:
                if (prior.get('goal') != request.goal.strip()
                    or prior.get('target') != (request.target.model_dump(mode='json') if request.target else None)):
                    raise HarnessError('REQUEST_ID_CONFLICT', '同一追加请求 ID 不能更换目标。')
                return
            if current.status not in ('completed', 'review_required') or current.owner_pid is not None:
                raise HarnessError('TASK_BUSY', '项目 Demo 已由另一个请求开始执行。')
            if (current.grant is None or current.grant.revoked or current.cancel_requested
                    or current.grant.expires_at <= now()):
                raise HarnessError('TASK_GRANT_INVALID', '追加目标的原授权已失效。')
            if not request.goal.strip():
                raise HarnessError('TASK_GOAL_REQUIRED', '请输入追加目标。')
            current.goal = request.goal.strip()
            current.observations['active_demo_target'] = resolved_target
            queued = True
            history.append({'request_id': request.request_id, 'goal': current.goal,
                'kind': 'follow-up', 'target': request.target.model_dump(mode='json') if request.target else None,
                'accepted_at': now().isoformat()})
            for key in ('production_preparation', 'production_preparation_context',
                        'selected_prepared_assets', 'selected_builtin_assets',
                        'selected_project_assets', 'selected_asset_usage',
                        'selected_asset_runtime_validation',
                        'production_preparation_adjustments'):
                current.observations.pop(key, None)
            current.observations['active_goal_action_start'] = len(current.actions)
            current.status, current.reason, current.finished_at = 'queued', None, None
        task = self.records.update(task_id, queue, 'agent.project_demo.goal_added',
            {'request_id': request.request_id})
        if not queued:
            return task
        if task_id not in self.tools:
            self.tools[task_id] = TaskTools(self, task_id)
            self.runtimes[task_id] = HarnessRuntime(self.database_path, self.tools[task_id].registry())
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
        for job in list(self.browser_jobs.values()):
            job.cancel()
        await asyncio.gather(*list(self.browser_jobs.values()), return_exceptions=True)
        for task_id in list(self.jobs):
            self.cancel(task_id)
        await asyncio.gather(*list(self.jobs.values()), return_exceptions=True)
        await asyncio.gather(*list(self.cleanups.values()), return_exceptions=True)
        await asyncio.gather(*(tools.stop() for tools in self.tools.values()), return_exceptions=True)
        await self.game.close()

    def _game_task(self, task_id, *, active_agent=False, manual_operation=False):
        task = self.get(task_id)
        card = task.authorization_card
        if card.task_profile not in ('card-development', 'project-demo', 'project-demo-agent') or not card.allow_game_execution or task.grant is None:
            raise HarnessError('GAME_EXECUTION_NOT_AUTHORIZED', '此任务没有游戏工程运行权限。')
        if active_agent:
            task = self.check_grant(task_id)
        elif manual_operation and task.cancel_requested:
            raise HarnessError('TASK_GRANT_INVALID', '已取消任务不能再运行工程。')
        if manual_operation and task.owner_pid is not None:
            raise HarnessError('TASK_BUSY', 'Agent 正在修改或运行此工程，请等待当前任务结束。')
        if card.task_profile == 'card-development':
            self.card_workspace(task.project_id, card.card_id,
                expected_root=card.workspace_root, expected_branch=card.branch)
        else:
            self.project_demo_workspace(task.project_id, card.workspace_id,
                                        expected_root=card.workspace_root)
        if manual_operation:
            with self.records.connect() as connection:
                claim = connection.execute('SELECT task_id FROM agent_project_claims WHERE project_id=?',
                                           (task.project_id,)).fetchone()
            if claim and claim[0] != task.id:
                raise HarnessError('PROJECT_EXECUTION_BUSY', '该项目正在由另一项任务修改，请等待其结束。')
        return task

    def game_status(self, task_id):
        task = self.get(task_id)
        if task.grant is None and task.observations.get('demo_pending_authorization'):
            from .demo_workbench import project_task
            project_task(self, task_id)
            historical = TaskGrant.model_validate(task.observations['demo_authorization_history'][-1]['grant'])
            return self.game.snapshot(task.model_copy(update={'grant': historical}))
        return self.game.snapshot(self._game_task(task_id))

    async def game_operation(self, task_id, request: GameOperationRequest):
        if request.operation == 'observe':
            await self.observe_game(task_id)
            return self.game_status(task_id)
        task = self._game_task(task_id, manual_operation=True)
        if request.operation == 'build_test':
            self.browser_task(task_id, interaction=True)
        if request.operation == 'prepare' and not task.authorization_card.allow_dependency_install:
            raise HarnessError('DEPENDENCY_INSTALL_NOT_AUTHORIZED', '此任务未授权准备工程依赖。')
        evidence = await self.game.execute(task, request.operation)
        def observed(current):
            current.observations['game_project'] = evidence
        self.records.update(task_id, observed, 'agent.game_project.manual_operation',
            {'operation': request.operation, 'run_id': evidence['run']['id']})
        return self.game.snapshot(task)

    def browser_task(self, task_id, *, interaction=False):
        task = self._game_task(task_id)
        grant, card = task.grant, task.authorization_card
        authorization = task.browser_interaction_authorization if interaction else task.browser_authorization
        allowed = (card.allow_browser_interaction and grant.allow_browser_interaction) if interaction else (card.allow_browser_observation and grant.allow_browser_observation)
        capability = 'code.browser.interact' if interaction else 'code.browser.observe'
        if authorization and (authorization.revoked or task.cancel_requested
                              or (authorization.expires_at is not None and authorization.expires_at <= now())):
            raise HarnessError('BROWSER_AUTHORIZATION_EXPIRED', '浏览器执行需要未过期、未撤销的当前任务授权。')
        if (not authorization or not allowed
                or capability not in grant.capability_ids
                or grant.capability_ids != card.capability_ids
                or (authorization.task_id, authorization.project_id, authorization.workspace_id,
                    authorization.workspace_root,
                    authorization.card_id, authorization.branch) != (task.id, task.project_id,
                    card.workspace_id, card.workspace_root, card.card_id, card.branch)
                or (grant.workspace_id, grant.workspace_root, grant.card_id, grant.branch) !=
                   (card.workspace_id, card.workspace_root, card.card_id, card.branch)):
            scope = '测试构建、状态控制与有限键盘输入' if interaction else '独立浏览器执行与截图'
            raise HarnessError('BROWSER_NOT_AUTHORIZED', f'此授权未包含{scope}；请准备明确包含该范围的新任务。')
        return task

    async def observe_game(self, task_id, *, active_agent=False, interaction=None):
        task = self.browser_task(task_id, interaction=interaction is not None)
        if not active_agent:
            self._game_task(task_id, manual_operation=True)
        if task_id in self.browser_jobs:
            raise HarnessError('BROWSER_BUSY', '本任务已有浏览器检查正在运行。')
        from .browser_observation import observe
        job = asyncio.create_task(observe(self, task, **({'interaction': interaction} if interaction is not None else {})))
        self.browser_jobs[task_id] = job
        try:
            evidence = await job
            self.records.update(task_id, lambda current: current.observations.update(
                {'browser_interaction' if interaction is not None else 'browser_observation': evidence}), 'agent.browser.observed', {'run_id': evidence['run']['id']})
            return evidence
        finally:
            self.browser_jobs.pop(task_id, None)

    def cancel_browser_observation(self, task_id):
        self.get(task_id)
        job = self.browser_jobs.get(task_id)
        if job and not job.cancelling():
            job.cancel()
        return {'cancel_requested': job is not None}

    def revoke_browser_authorization(self, task_id, *, interaction=False):
        def revoke(task):
            authorization = task.browser_interaction_authorization if interaction else task.browser_authorization
            if authorization:
                authorization.revoked = True
        task = self.records.update(task_id, revoke, 'agent.browser.authorization_revoked')
        self.cancel_browser_observation(task_id)
        return task

    def finish_game(self, task):
        from .context_projection import project_game_diagnostics
        snapshot = self.game.snapshot(task)
        if not snapshot.check or snapshot.check.status != 'succeeded' or not snapshot.check.passed:
            raise HarnessError('VERIFICATION_INCOMPLETE', '当前源码还没有通过 TypeScript 检查。')
        if not snapshot.build or snapshot.build.status != 'succeeded' or not snapshot.build.passed:
            raise HarnessError('VERIFICATION_INCOMPLETE', '当前源码还没有产生通过的 Vite 构建。')
        if (not snapshot.preview or snapshot.preview.status != 'running'
                or not snapshot.preview.passed or snapshot.preview.source_stale):
            raise HarnessError('VERIFICATION_INCOMPLETE', '当前构建还没有运行中的本地预览。')
        diagnostics = project_game_diagnostics(task)
        if task.authorization_card.allow_browser_interaction:
            checks = diagnostics['checks']
            verified_scopes = [name for name, value in checks.items()
                               if value.get('evidence_status') == 'pass']
            statuses = '、'.join(f"{name}={value.get('evidence_status', 'unknown')}"
                                for name, value in checks.items()) or '未执行'
            summary = ('类型检查、交付构建和当前预览通过；浏览器局部证据：' + statuses
                       + '。未执行完整玩法或视觉评审。')
        else:
            verified_scopes = []
            summary = ('源码已回读，类型检查和构建通过，本地预览正在运行；'
                       '未执行受控玩法检查或视觉评审。')
        return {'tool': 'game_project', 'mode': 'live', 'delivery_status': 'build_ready',
            'content_verified': True, 'compilation_verified': True, 'verified': False,
            'browser_errors_verified': bool(verified_scopes), 'gameplay_verified': False,
            'browser_checks': diagnostics, 'verified_scopes': verified_scopes,
            'preview_url': snapshot.preview.preview_url,
            'card_id': snapshot.card_id, 'branch': snapshot.branch,
            'workspace_root': snapshot.workspace_root,
            'summary': summary}

    def execution_status(self) -> Literal["running", "connected", "idle"]:
        """Local observed lifecycle only; never launch/probe DCCs for a health request."""
        if self.connection_checks or any(not job.done() for job in (*self.jobs.values(), *self.cleanups.values())):
            return "running"
        if any(tools.has_connected_sessions() for tools in self.tools.values()):
            return "connected"
        if self.game.has_active_previews():
            return "connected"
        return "idle"
