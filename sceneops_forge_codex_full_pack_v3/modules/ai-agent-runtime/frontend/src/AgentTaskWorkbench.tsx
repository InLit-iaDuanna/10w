import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentTasks, agentTaskKeys, type AgentTask, type GameProjectExecution } from './client';
import { useProduction, productionKeys } from './production-client';
import './agent-task.css';
import { BrowserObservationPanel } from './BrowserObservationPanel';
import { BrowserInteractionPanel } from './BrowserInteractionPanel';

const LABELS: Record<string, string> = {
  awaiting_authorization: '等待任务授权', queued: '排队中', running: 'Agent 执行中',
  needs_approval: '需要补充授权', blocked: '工具连接受阻', completed: '已验证完成',
  failed: '执行失败', cancel_pending: '正在取消 · 等待工具停止确认', cancelled: '已取消', interrupted: '运行已中断',
  review_required: '执行结束 · 待人工审阅 / 试玩',
};
const ACTIONS: Record<string, string> = {
  'agent.next_action': '观察与规划', 'blender.asset.create': 'Blender 创建资产',
  'blender.scene.inspect': '检查 Blender 场景', 'blender.asset.export': '导出 FBX',
  'unity.asset.import': 'Unity 导入并放置', 'unity.scene.inspect': '检查 Unity 场景',
  'agent.finish': '核验交付',
  'codex.task.execute': 'Codex 自主执行',
  'code.workspace.inspect': '检查分支文件', 'code.file.read': '读取源码', 'code.file.write': '写入并回读源码',
  'code.dependencies.prepare': '准备游戏工程依赖', 'code.project.status': '读取工程运行状态',
  'code.project.check': 'TypeScript 检查', 'code.project.build': '构建游戏',
  'code.preview.start': '启动本地预览', 'code.preview.stop': '停止本地预览',
  'project.assets.list': '读取项目资产与版本',
  'environment.scene.read': '读取当前场景与对象',
  'environment.object.transform': '修改对象变换并回读',
  'code.browser.observe': '采集当前构建画面与浏览器错误',
};
const busy = (task: AgentTask) => ['queued', 'running'].includes(task.status);

function useTasks(projectId: string | null) {
  const production = useProduction(projectId);
  const unscoped = useQuery({ queryKey: agentTaskKeys.list(null), queryFn: ({ signal }) => agentTasks.list(null, signal),
    enabled: !projectId, retry: false });
  return projectId ? { ...production, data: production.data ? { tasks: production.data.tasks } : undefined } : unscoped;
}

export function AgentTaskWorkbench({ projectId, onDirtyChange }: { projectId: string | null; onDirtyChange?: (value: boolean) => void }) {
  const [goal, setGoal] = useState('');
  const query = useTasks(projectId);
  const cache = useQueryClient();
  const prepare = useMutation({ mutationFn: () => agentTasks.prepare({ goal: goal.trim(), execution_mode: 'typed-tools', allow_image_generation: false, allow_playtest:false,
    allow_game_execution:false,allow_dependency_install:false,task_profile: 'auto', ...(projectId ? { project_id: projectId } : {}) }),
    onSuccess: () => { setGoal(''); void cache.invalidateQueries({ queryKey: ['agent-tasks'] }); } });
  useEffect(() => { onDirtyChange?.(!!goal.trim()); }, [goal, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  return <section className="agent-task-workbench" aria-label="Agent 任务">
    <header><strong>告诉 Agent 你要完成什么</strong><p>自动准备专用工程，确认一次范围后执行。只在越界、预算或工具阻塞时询问。</p></header>
    <form onSubmit={event => { event.preventDefault(); if (goal.trim() && !prepare.isPending) prepare.mutate(); }}>
      <textarea aria-label="Agent 任务目标" placeholder="例如：创建一个 1×2×3 米的箱体，导出并放入 Unity 场景。" rows={3} maxLength={8000}
        value={goal} onChange={event => setGoal(event.target.value)} disabled={prepare.isPending} />
      <div className="agent-task-form-actions"><small>首版支持有界基础资产闭环；不自动构建、渲染或游测。</small>
        <button type="submit" disabled={!goal.trim() || prepare.isPending}>{prepare.isPending ? '准备授权卡…' : '准备任务'}</button></div>
    </form>
    {prepare.error && <p role="alert">{prepare.error.message}</p>}
    {query.isPending && <p role="status">读取任务记录…</p>}
    {query.error && <p role="alert">任务服务未连接：{query.error.message} <button onClick={() => void query.refetch()}>重新连接</button></p>}
    {query.data?.tasks.length === 0 && <p className="agent-task-empty">还没有任务。准备授权卡不会启动模型或外部工具。</p>}
    <div className="agent-task-list">{query.data?.tasks.map(task => <TaskCard key={task.id} task={task} />)}</div>
  </section>;
}

/** Timeline-only embedding for the conversation canvas; preparation remains owned by the caller. */
export function AgentTaskTimeline({ projectId, cardId, onContinue }: { projectId: string | null; cardId?: string; onContinue?: () => void }) {
  if (!projectId) return null;
  return <ProjectAgentTaskTimeline projectId={projectId} {...(cardId === undefined ? {} : { cardId })} {...(onContinue ? { onContinue } : {})} />;
}

function ProjectAgentTaskTimeline({ projectId, cardId, onContinue }: { projectId: string; cardId?: string; onContinue?: () => void }) {
  const query = useTasks(projectId);
  if (query.isPending) return <p className="agent-task-timeline-state" role="status">正在读取任务记录…</p>;
  if (query.error) return <p className="agent-task-timeline-state" role="alert">任务服务未连接：{query.error.message} <button onClick={() => void query.refetch()}>重新连接</button></p>;
  const tasks = query.data?.tasks.filter(task => cardId === undefined || task.authorization_card.card_id === cardId) ?? [];
  if (!tasks.length) return null;
  return <section className="agent-task-timeline" aria-label="任务时间线"><div className="agent-task-list">{tasks.map(task => <TaskCard key={task.id} task={task} onContinue={onContinue} />)}</div></section>;
}

function TaskCard({ task, onContinue }: { task: AgentTask; onContinue?: () => void }) {
  const cache = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const action = useMutation({ mutationFn: (kind: 'authorize' | 'cancel' | 'resume') => kind === 'authorize'
    ? agentTasks.authorize(task.id, { authorization_card_id: task.authorization_card.id, accept_unknown_cost: true,
      accept_full_access: task.authorization_card.execution_mode === 'codex-full-access' })
    : agentTasks[kind](task.id), onSettled: async () => {
      await cache.invalidateQueries({ queryKey: ['agent-tasks'] });
      await cache.invalidateQueries({ queryKey: productionKeys.snapshot(task.project_id) });
    } });
  const events = useQuery({ queryKey: [...agentTaskKeys.detail(task.id), 'events'], queryFn: ({ signal }) => agentTasks.allEvents(task.id, signal),
    enabled: expanded, retry: false });
  useEffect(() => { if (expanded) void events.refetch(); }, [expanded, task.updated_at]);
  const card = task.authorization_card;
  const fullAccess = card.execution_mode === 'codex-full-access';
  const activity = task.observations.codex_activity;
  const grantExpired = !!task.grant && Date.parse(task.grant.expires_at) <= Date.now();
  const sceneSelection = task.observations.scene_selection;
  const sceneObservation = task.observations.environment_scene;
  const selectedSceneObjectIds = sceneSelection && typeof sceneSelection === 'object'
    && 'selected_scene_object_ids' in sceneSelection && Array.isArray(sceneSelection.selected_scene_object_ids)
    ? sceneSelection.selected_scene_object_ids.filter((value): value is string => typeof value === 'string') : [];
  const observedSceneVersion = sceneObservation && typeof sceneObservation === 'object'
    && 'scene_version' in sceneObservation && typeof sceneObservation.scene_version === 'number'
    ? sceneObservation.scene_version : null;
  useEffect(() => {
    if (card.task_profile === 'environment-scene' && observedSceneVersion != null) {
      void cache.invalidateQueries({queryKey:['environment-scene', task.project_id]});
    }
  }, [cache, card.task_profile, observedSceneVersion, task.project_id]);
  const restart = useMutation({ mutationFn: () => agentTasks.prepare({ goal: task.goal, execution_mode: card.execution_mode, allow_image_generation: card.allow_image_generation, allow_playtest:false,
    allow_game_execution: card.allow_game_execution, allow_dependency_install: card.allow_dependency_install, task_profile: card.task_profile,
    allow_browser_observation: card.allow_browser_observation,
    allow_browser_interaction: card.allow_browser_interaction,
    ...(card.card_id ? { project_id: task.project_id, card_id: card.card_id } : {}),
    ...(card.task_profile === 'environment-scene' ? {project_id:task.project_id,selected_scene_object_ids:selectedSceneObjectIds} : {}) }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['agent-tasks'] }) });
  return <article className="agent-task-card" data-state={task.status}>
    <header><strong>{task.goal}</strong><span role="status">{LABELS[task.status] ?? task.status}</span></header>
    <small>{fullAccess ? `CLI 启动 ${task.cli_invocations_used}/1 · 内部模型次数未知` : `模型调用 ${task.model_calls_used}/${card.max_model_calls}`} · 费用{task.cost_usd == null ? '未知' : `$${task.cost_usd.toFixed(4)}`} · {task.project_id}</small>
    {task.status === 'awaiting_authorization' && <section className="agent-authorization" aria-label="任务授权范围">
      <p>{card.scope}</p><p>专用工作目录：<code>{card.workspace_root}</code></p>
      <p>模型：{task.provider_model ?? 'CLI 默认模型'} · {task.provider_id}</p>
      {card.card_id && <p>卡片：{card.card_id} · 分支：{card.branch}</p>}
      {card.card_id && task.observations.card_context != null && <details><summary>查看本次开发采用的策划快照</summary><pre>{JSON.stringify(task.observations.card_context, null, 2)}</pre></details>}
      <p>{card.cost_notice}</p>{card.task_profile === 'environment-scene'
        ? <p>选中对象只是任务上下文；确认后才授权修改卡片中列出的对象变换。场景数据修改不代表运行游戏已更新。</p>
        : !fullAccess && card.task_profile !== 'card-development' && <p>允许自动准备本任务工程及自有插件、打开专用 Blender/Unity 会话；不修改其他工程、不购买或激活服务。</p>}
      <button disabled={action.isPending} onClick={() => action.mutate('authorize')}>{fullAccess ? '确认完全权限风险并开始 · 费用未知' : '确认范围并开始 · 接受费用可能未知'}</button>
    </section>}
    {task.reason && <p className="agent-task-reason" role="alert">{task.reason}</p>}
    {fullAccess && activity != null && <p className="agent-task-live-activity" role="status">最近执行活动：{activityLabel(activity)}</p>}
    {fullAccess && task.observations.codex != null && <details><summary>查看 Codex 结果与执行摘要</summary><pre>{JSON.stringify(task.observations.codex, null, 2)}</pre></details>}
    {card.allow_game_execution && task.grant && <GameRuntimePanel task={task} />}
    {card.allow_game_execution && task.grant && <BrowserObservationPanel task={task} />}
    {card.allow_game_execution && task.grant && <BrowserInteractionPanel task={task} />}
    <ol className="agent-action-tree">{task.actions.map(record => <li key={record.request_id} data-state={record.state}>
      <strong>{ACTIONS[record.action.capability_id] ?? record.action.capability_id}</strong><span>{record.state === 'succeeded' ? '已执行' : record.state === 'running' ? '执行中' : record.state}</span>
      <small>{record.action.rationale}</small>{record.reason && <p>{record.reason}</p>}
      {record.verification_result && <p>{record.verification_result.verdict === 'PASS' ? '该版本验收通过' : record.verification_result.verdict === 'FAIL' ? '该版本验收失败' : '证据不完整'} · {record.verification_result.project_revision}</p>}
      {record.action.capability_id === 'code.file.write' && record.result && <CodeWriteEvidence result={record.result} />}
      {record.action.capability_id === 'environment.object.transform' && record.result && <SceneTransformEvidence result={record.result} />}
    </li>)}</ol>
    <footer>
      {(busy(task) || ['awaiting_authorization', 'blocked'].includes(task.status)) && <button disabled={action.isPending || task.cancel_requested} onClick={() => action.mutate('cancel')}>{task.cancel_requested ? '正在停止…' : '停止任务'}</button>}
      {task.status === 'blocked' && task.grant && !grantExpired && <button disabled={action.isPending} onClick={() => action.mutate('resume')}>检查连接并继续</button>}
      {((grantExpired && task.status === 'blocked') || ['interrupted', 'failed', 'needs_approval'].includes(task.status)) && <button disabled={restart.isPending} onClick={() => restart.mutate()}>重新准备独立任务</button>}
      {onContinue && ['completed', 'review_required', 'failed', 'needs_approval'].includes(task.status) && <button onClick={onContinue}>继续修改同一工程</button>}
      <button aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? '收起记录' : '查看执行记录'}</button>
    </footer>
    {action.error && <p role="alert">{action.error.message}</p>}
    {restart.error && <p role="alert">{restart.error.message}</p>}
    {expanded && <section className="agent-task-records" aria-label="执行事件与证据">
      {events.error && <p role="alert">{events.error.message}</p>}
      <ol>{events.data?.events.map(event => <li key={event.sequence}><time>{new Date(event.occurred_at).toLocaleTimeString()}</time> {event.event_type}</li>)}</ol>
      <details><summary>工具回读证据</summary><pre>{JSON.stringify(task.observations, null, 2)}</pre></details>
    </section>}
  </article>;
}

type GameOperation = 'prepare' | 'check' | 'build' | 'preview_start' | 'preview_stop';

function GameRuntimePanel({ task }: { task: AgentTask }) {
  const cache = useQueryClient();
  const query = useQuery({ queryKey: agentTaskKeys.game(task.id), queryFn: ({ signal }) => agentTasks.gameStatus(task.id, signal),
    retry: false, refetchInterval: state => {
      const snapshot = state.state.data as GameProjectExecution | undefined;
      return busy(task) || snapshot?.preview?.status === 'running' ? 1500 : false;
    } });
  const operation = useMutation({ mutationFn: async (kind: GameOperation | 'check_build') => {
    if (kind !== 'check_build') return agentTasks.gameOperation(task.id, kind);
    const checked = await agentTasks.gameOperation(task.id, 'check');
    if (checked.check?.passed !== true) return checked;
    return agentTasks.gameOperation(task.id, 'build');
  }, onSuccess: snapshot => {
    cache.setQueryData(agentTaskKeys.game(task.id), snapshot);
    void cache.invalidateQueries({ queryKey: ['agent-tasks'] });
  } });
  const snapshot = query.data;
  if (query.isPending) return <section className="agent-game-runtime"><p role="status">读取工程运行状态…</p></section>;
  if (query.error) return <section className="agent-game-runtime"><p role="alert">工程状态读取失败：{query.error.message}</p></section>;
  if (!snapshot) return null;
  const previewRunning = snapshot.preview?.status === 'running';
  const agentBusy = busy(task);
  const latest = [snapshot.dependency, snapshot.check, snapshot.build, snapshot.preview].filter(Boolean).at(-1);
  return <section className="agent-game-runtime" aria-label="游戏工程运行">
    <header><div><strong>游戏工程</strong><small>{snapshot.branch}</small></div>
      {previewRunning && snapshot.preview?.preview_url && !snapshot.preview.source_stale
        ? <a href={snapshot.preview.preview_url} target="_blank" rel="noopener noreferrer">打开独立预览 ↗</a>
        : <span>{snapshot.preview?.source_stale ? '源码已改变 · 需重新构建' : '预览未运行'}</span>}</header>
    <p><code>{snapshot.workspace_root}</code></p>
    <dl><div><dt>依赖</dt><dd>{snapshot.dependencies_ready ? '已准备' : '未准备'}</dd></div>
      <div><dt>类型检查</dt><dd>{runLabel(snapshot.check)}</dd></div><div><dt>构建</dt><dd>{runLabel(snapshot.build)}</dd></div>
      <div><dt>预览</dt><dd>{previewRunning ? '运行中' : runLabel(snapshot.preview)}</dd></div></dl>
    <div className="agent-game-actions">
      {task.authorization_card.allow_dependency_install && <button disabled={operation.isPending || agentBusy} onClick={() => operation.mutate('prepare')}>准备依赖</button>}
      <button disabled={operation.isPending || agentBusy || !snapshot.dependencies_ready} onClick={() => operation.mutate('check_build')}>检查并构建</button>
      <button disabled={operation.isPending || agentBusy || snapshot.build?.status !== 'succeeded' || snapshot.build.source_stale === true || previewRunning} onClick={() => operation.mutate('preview_start')}>启动预览</button>
      <button disabled={operation.isPending || agentBusy || !previewRunning} onClick={() => operation.mutate('preview_stop')}>停止预览</button>
    </div>
    {operation.isPending && <p role="status">正在执行固定工程操作…</p>}
    {operation.error && <p role="alert">{operation.error.message}</p>}
    {latest?.log && <details><summary>最近日志 · {latest.operation}</summary><pre>{latest.log}</pre></details>}
    <small>浏览器错误与玩法结果尚未自动判定，请在独立预览中验收。</small>
  </section>;
}

function runLabel(run: GameProjectExecution['check'] | undefined) {
  if (!run) return '未执行';
  if (run.status === 'succeeded') return '通过';
  if (run.status === 'stale' || run.source_stale) return '源码已改变';
  if (run.status === 'running') return '运行中';
  if (run.status === 'stopped') return '已停止';
  return `失败${run.exit_code == null ? '' : ` · exit ${run.exit_code}`}`;
}

function CodeWriteEvidence({ result }: { result: unknown }) {
  if (!result || typeof result !== 'object' || !('evidence' in result)) return null;
  const evidence = result.evidence;
  if (!evidence || typeof evidence !== 'object' || !('path' in evidence)) return null;
  const diff = 'diff' in evidence && typeof evidence.diff === 'string' ? evidence.diff : null;
  return <details><summary>文件变更 · {String(evidence.path)}</summary>
    {diff ? <pre>{diff}</pre> : <pre>{JSON.stringify(evidence, null, 2)}</pre>}</details>;
}

function SceneTransformEvidence({ result }: { result: unknown }) {
  if (!result || typeof result !== 'object' || !('evidence' in result)) return null;
  const evidence = result.evidence;
  if (!evidence || typeof evidence !== 'object' || !('object' in evidence)) return null;
  const object = evidence.object;
  if (!object || typeof object !== 'object' || !('transform' in object)) return null;
  const transform = object.transform;
  if (!transform || typeof transform !== 'object') return null;
  const position = 'position_m' in transform && Array.isArray(transform.position_m)
    ? transform.position_m.join(', ') : '未知';
  const rotation = 'rotation_y_deg' in transform ? String(transform.rotation_y_deg) : '未知';
  const scale = 'scale' in transform ? String(transform.scale) : '未知';
  const version = 'scene_version' in evidence ? String(evidence.scene_version) : '未知';
  return <details><summary>场景 v{version} · 已回读实际变换</summary>
    <p>位置 [{position}] m · Y 旋转 {rotation}° · 缩放 {scale}</p>
    <small>仅项目场景数据；未验证运行中的游戏。</small></details>;
}

export function activityLabel(value: unknown): string {
  if (!value || typeof value !== 'object' || !('type' in value) || !('phase' in value)) return '等待工具事件';
  const types: Record<string, string> = { command_execution: '命令执行', file_change: '文件修改', todo_list: '更新计划（未验证）', turn: '模型运行', error: '执行异常' };
  const phases: Record<string, string> = { started: '开始', updated: '进行中', completed: '返回结果', failed: '失败', error: '错误' };
  return `${types[String(value.type)] ?? '工具活动'} · ${phases[String(value.phase)] ?? '状态更新'}`;
}

export function AgentTaskActivity({ projectId }: { projectId: string | null }) {
  if (!projectId) return null;
  return <ProjectAgentTaskActivity projectId={projectId} />;
}

function ProjectAgentTaskActivity({ projectId }: { projectId: string }) {
  const tasks = useTasks(projectId);
  const task = tasks.data?.tasks.find(busy) ?? tasks.data?.tasks[0];
  if (!task) return null;
  const current = task.actions.find(record => record.state === 'running') ?? task.actions.at(-1);
  return <aside className="agent-task-activity" aria-label="当前 Agent 进度" role="status">
    <strong>{LABELS[task.status] ?? task.status}</strong><span>{current ? ACTIONS[current.action.capability_id] ?? current.action.capability_id : task.goal}</span>
    <small>{task.authorization_card.execution_mode === 'codex-full-access' ? `CLI ${task.cli_invocations_used}/1` : `模型 ${task.model_calls_used}/${task.authorization_card.max_model_calls}`} · {task.cost_usd == null ? '费用未知' : '费用已报告'}</small>
  </aside>;
}
