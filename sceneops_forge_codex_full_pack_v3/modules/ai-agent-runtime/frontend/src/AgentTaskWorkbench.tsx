import { CreationBriefPanel } from './CreationBriefPanel';
import { MemoryMessage } from './MemoryActivity';
import { ExperienceReferences } from './ExperienceReferences';
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentTasks, agentTaskKeys, type AgentTask, type GameProjectExecution } from './client';
import { useProduction, productionKeys } from './production-client';
import './agent-task.css';
import { MarkdownMessage } from '../../../../packages/core-ui/frontend/src/index.ts';
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
  'code.demo_assets.install': '准备项目内置资产',
  'code.demo_content.materialize': '物化 Demo 运行输入',
  'project.assets.list': '读取项目资产与版本',
  'environment.scene.read': '读取当前场景与对象',
  'environment.object.transform': '修改对象变换并回读',
  'project.asset.door.create': '创建可编辑门配方',
  'project.asset.door.update': '更新共享门配方',
  'environment.object.place': '放置场景实例',
  'environment.demo_object.transform': '调整 Demo 实例',
  'environment.key_door.configure': '配置钥匙门行为',
  'environment.object.remove': '移除场景实例',
  'code.browser.observe': '采集当前构建画面与浏览器错误',
};
const busy = (task: AgentTask) => ['queued', 'running'].includes(task.status);

export function isVisibleAgentTask(task: Pick<AgentTask, 'status' | 'actions' | 'model_calls_used' | 'cli_invocations_used'>,
    _inline = false) {
  return task.status !== 'cancelled' || task.actions.length > 0
    || task.model_calls_used > 0 || task.cli_invocations_used > 0;
}

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
  const tasks = query.data?.tasks.filter(task => isVisibleAgentTask(task)) ?? [];
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
    {!query.isPending && !query.error && tasks.length === 0 && <p className="agent-task-empty">还没有任务。准备授权卡不会启动模型或外部工具。</p>}
    <div className="agent-task-list">{tasks.map(task => <TaskCard key={task.id} task={task} />)}</div>
  </section>;
}

/** Timeline-only embedding for the conversation canvas; preparation remains owned by the caller. */
export function AgentTaskTimeline({ projectId, cardId, conversationId, taskProfile, onContinue, onPreviewChange, onRunPresence }: { projectId: string | null; cardId?: string; conversationId?: string; taskProfile?: string | string[];
  onContinue?: () => void; onPreviewChange?: (url: string | null) => void; onRunPresence?: (present: boolean, running?: {id: string; cancelRequested: boolean}) => void }) {
  if (!projectId) return null;
  return <ProjectAgentTaskTimeline projectId={projectId} conversationId={conversationId} taskProfile={taskProfile} {...(cardId === undefined ? {} : { cardId })}
    {...(onContinue ? { onContinue } : {})} {...(onPreviewChange ? { onPreviewChange } : {})}
    {...(onRunPresence ? {onRunPresence} : {})} />;
}

function ProjectAgentTaskTimeline({ projectId, cardId, conversationId, taskProfile, onContinue, onPreviewChange, onRunPresence }: { projectId: string; cardId?: string; conversationId?: string; taskProfile?: string | string[];
  onContinue?: () => void; onPreviewChange?: (url: string | null) => void; onRunPresence?: (present: boolean, running?: {id: string; cancelRequested: boolean}) => void }) {
  const query = useTasks(projectId);
  const tasks = query.data?.tasks.filter(task => isVisibleAgentTask(task, true)
    && (taskProfile === undefined || (Array.isArray(taskProfile)
      ? taskProfile.includes(task.authorization_card.task_profile)
      : task.authorization_card.task_profile === taskProfile))
    && (cardId === undefined || task.authorization_card.card_id === cardId || task.observations.planning_card_id === cardId)
    && (conversationId === undefined || taskConversationId(task) === conversationId)) ?? [];
  const running = tasks.find(task => busy(task) || task.status === 'cancel_pending' || task.status === 'blocked');
  useEffect(() => { onRunPresence?.(tasks.length > 0, running ? {id:running.id, cancelRequested:!!running.cancel_requested || running.status === 'cancel_pending'} : undefined); }, [onRunPresence, tasks.length, running?.id, running?.cancel_requested, running?.status]);
  useEffect(() => () => onRunPresence?.(false), [onRunPresence]);
  if (query.isPending) return <p className="agent-task-timeline-state" role="status">正在读取任务记录…</p>;
  if (query.error) return <p className="agent-task-timeline-state" role="alert">任务服务未连接：{query.error.message} <button onClick={() => void query.refetch()}>重新连接</button></p>;
  if (!tasks.length) return null;
  const displayTasks = [...tasks].sort((a,b) => a.created_at.localeCompare(b.created_at));
  return <>{displayTasks.map(task => <TaskCard key={task.id} task={task} inline
    {...(onContinue ? {onContinue} : {})} {...(task.id === displayTasks.at(-1)?.id && onPreviewChange ? {onPreviewChange} : {})} />)}</>;
}

export function TaskCard({ task, onContinue, inline = false, onPreviewChange }: { task: AgentTask; onContinue?: () => void;
  inline?: boolean; onPreviewChange?: (url: string | null) => void }) {
  const cache = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [followupGoal, setFollowupGoal] = useState('');
  const followupRequestId = useRef<string | null>(null);
  const action = useMutation({ mutationFn: (kind: 'authorize' | 'cancel' | 'resume') => kind === 'authorize'
    ? agentTasks.authorize(task.id, { authorization_card_id: task.authorization_card.id, accept_unknown_cost: true,
      accept_full_access: task.authorization_card.execution_mode !== 'typed-tools' })
    : agentTasks[kind](task.id), onSettled: async () => {
      await cache.invalidateQueries({ queryKey: ['agent-tasks'] });
      await cache.invalidateQueries({ queryKey: productionKeys.snapshot(task.project_id) });
    } });
  const events = useQuery({ queryKey: [...agentTaskKeys.detail(task.id), 'events'], queryFn: ({ signal }) => agentTasks.allEvents(task.id, signal),
    enabled: expanded, retry: false });
  useEffect(() => { if (expanded) void events.refetch(); }, [expanded, task.updated_at]);
  const card = task.authorization_card;
  const fullAccess = card.execution_mode !== 'typed-tools';
  const native = card.execution_mode === 'agent-full-access';
  const nativeProduction = task.observations.native_production === true;
  const latestGoal = Array.isArray(task.observations.demo_goals) ? task.observations.demo_goals.at(-1) : undefined;
  const memorySourceId = typeof latestGoal?.request_id === 'string' ? `task:${task.id}:request:${latestGoal.request_id}` : `task:${task.id}:goal`;
  const demoExecution = card.include_demo_assets;
  const projectDemo = ['project-demo', 'project-demo-agent'].includes(card.task_profile);
  const unityAsset = card.task_profile === 'unity-asset-edit';
  const agentProjectDemo = card.task_profile === 'project-demo-agent';
  const continueDemo = useMutation({mutationFn:(value:{goal:string;requestId:string})=>
    agentTasks.continueProjectDemo(task.id,{goal:value.goal,request_id:value.requestId}),onSuccess:async()=>{
      setFollowupGoal(''); followupRequestId.current=null;
      await cache.invalidateQueries({queryKey:['agent-tasks']});
      await cache.invalidateQueries({queryKey:productionKeys.snapshot(task.project_id)});
    }});
  const activity = task.observations.codex_activity;
  const grantExpired = !!task.grant?.expires_at && Date.parse(task.grant.expires_at) <= Date.now();
  const sceneSelection = task.observations.scene_selection;
  const sceneObservation = task.observations.environment_scene;
  const selectedSceneObjectIds = sceneSelection && typeof sceneSelection === 'object'
    && 'selected_scene_object_ids' in sceneSelection && Array.isArray(sceneSelection.selected_scene_object_ids)
    ? sceneSelection.selected_scene_object_ids.filter((value): value is string => typeof value === 'string') : [];
  const observedSceneVersion = sceneObservation && typeof sceneObservation === 'object'
    && 'scene_version' in sceneObservation && typeof sceneObservation.scene_version === 'number'
    ? sceneObservation.scene_version : null;
  const demoMaterialization = task.observations.demo_materialization;
  const productionPreparation = task.observations.production_preparation;
  const demoSceneVersion = demoMaterialization && typeof demoMaterialization === 'object'
    && 'scene_version' in demoMaterialization && typeof demoMaterialization.scene_version === 'number'
    ? demoMaterialization.scene_version : null;
  useEffect(() => {
    if (card.task_profile === 'environment-scene' && observedSceneVersion != null) {
      void cache.invalidateQueries({queryKey:['environment-scene', task.project_id]});
    }
  }, [cache, card.task_profile, observedSceneVersion, task.project_id]);
  useEffect(() => {
    if (projectDemo && demoSceneVersion != null) {
      void cache.invalidateQueries({queryKey:['environment-scene', task.project_id]});
      void cache.invalidateQueries({queryKey:['project-assets', task.project_id]});
    }
  }, [cache, projectDemo, demoSceneVersion, task.project_id]);
  const restart = useMutation({ mutationFn: () => agentTasks.prepare({ goal: task.goal, execution_mode: card.execution_mode, allow_image_generation: card.allow_image_generation, allow_playtest:false,
    allow_game_execution: card.allow_game_execution, allow_dependency_install: card.allow_dependency_install, task_profile: card.task_profile,
    allow_browser_observation: card.allow_browser_observation,
    allow_browser_interaction: card.allow_browser_interaction,
    allow_model_image_input: card.allow_model_image_input,
    ...(card.card_id ? { project_id: task.project_id, card_id: card.card_id } : {}),
    ...(card.task_profile === 'environment-scene' ? {project_id:task.project_id,selected_scene_object_ids:selectedSceneObjectIds} : {}) }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['agent-tasks'] }) });
  const followup = !inline && agentProjectDemo && task.grant && (nativeProduction || (!native && !grantExpired)) && ['completed','review_required','failed','interrupted','cancelled'].includes(task.status)
      && <form className="agent-demo-followup" onSubmit={event=>{event.preventDefault();const goal=followupGoal.trim();if(!goal||continueDemo.isPending)return;
        followupRequestId.current ??= crypto.randomUUID();continueDemo.mutate({goal,requestId:followupRequestId.current});}}>
        <textarea aria-label="继续修改当前 Demo" rows={2} maxLength={8000} value={followupGoal}
          onChange={event=>{setFollowupGoal(event.target.value);followupRequestId.current=null;}}
          placeholder="例如：移动太慢，请提高角色速度并保留当前场景。" />
        <button disabled={!followupGoal.trim()||continueDemo.isPending}>{continueDemo.isPending?'正在继续…':'继续修改同一作品'}</button>
        {continueDemo.error && <p role="alert">{continueDemo.error.message}</p>}
      </form>;
  const authorization = task.status === 'awaiting_authorization' && (nativeProduction ? <CreationBriefPanel key={task.id} task={task} /> : <section className="agent-authorization" aria-label={inline ? '本轮执行授权范围' : '任务授权范围'}>
    {inline && <header><strong>{projectDemo ? '发起项目初版制作？' : demoExecution ? '允许 Agent 执行当前 Demo？' : 'Agent 请求执行权限'}</strong><span>仅当前项目</span></header>}
    {projectDemo
      ? <p>{agentProjectDemo
          ? '允许后，制作模型会读取已确认方向与当前工作区，选择并保存实际内容或源码修改，再完成物化、检查、构建和右侧试玩更新。'
          : '允许后，SceneOps 会按已确认方向登记内容，物化当前场景与资产，完成检查、构建并更新右侧试玩。'}</p>
      : demoExecution && <p>允许后，Agent 会连续修改源码、准备依赖、检查、构建并启动右侧预览。项目内置基础场景资产，人物以颜色区分身份。</p>}
    {unityAsset && <p>单独确认本次 Unity 有限范围。确认后开始首次导入与 Agent 执行；后续在本次范围内修改单个实例、保存与重开场景、进入与退出 Play。</p>}
    {inline && !projectDemo && !unityAsset && <ul className="agent-permission-list">
      <li>{projectDemo ? '读取当前登记工作区与项目源码' : '读取当前分支与项目源码'}</li>
      {card.capability_ids.includes('code.file.write') && <li>{projectDemo ? '修改当前登记工作区的普通源码并回读' : '修改当前分支源码并回读'}</li>}
      {card.allow_dependency_install && <li>准备当前项目依赖</li>}
      {card.allow_game_execution && <li>执行检查、构建并启动本地预览</li>}
      {card.allow_blender_edit && <li>在隔离 Blender 会话编辑所选资产，保存原生源与 GLB，更新共享引用</li>}
      {card.allow_browser_observation && <li>在独立浏览器读取当前构建画面与错误</li>}
      {card.allow_browser_interaction && <li>运行受控键盘输入检查</li>}
      {card.allow_model_image_input && <li>把本任务登记的当前截图发送给决策模型</li>}
    </ul>}
    <details open={!inline}><summary>{inline ? '查看完整执行范围' : '执行范围'}</summary>
      <p>{card.scope}</p><p>专用工作目录：<code>{card.workspace_root}</code></p>
      {card.workspace_id && <p>登记工作区：<code>{card.workspace_id}</code></p>}
      <p>模型：{task.provider_model ?? 'CLI 默认模型'} · {task.provider_id}</p>
      {card.card_id && <p>卡片：{card.card_id} · 分支：{card.branch}</p>}
      {card.card_id && task.observations.card_context != null && <details><summary>查看本次开发采用的策划快照</summary><pre>{JSON.stringify(task.observations.card_context, null, 2)}</pre></details>}
      {unityAsset && <p>本次最多 {card.max_model_calls} 次模型请求 · 时限 {card.max_duration_seconds} 秒</p>}
      <p>{card.cost_notice}</p>{card.task_profile === 'environment-scene'
        ? <p>选中对象只是任务上下文；确认后才授权修改卡片中列出的对象变换。场景数据修改不代表运行游戏已更新。</p>
        : !fullAccess && !['card-development', 'project-demo', 'project-demo-agent', 'unity-asset-edit'].includes(card.task_profile) && <p>允许自动准备本任务工程及自有插件、打开专用 Blender/Unity 会话；不修改其他工程、不购买或激活服务。</p>}
      {native && card.task_profile === 'card-development' && <p>如果同一对话的上一轮已停止但留下待核查修改，本次授权会保留当前文件并从同一卡片分支继续；不会重放上一轮命令。其他对话或分支仍不能并发写入。</p>}
    </details>
    <div className="agent-authorization-actions"><button disabled={action.isPending} onClick={() => action.mutate('authorize')}>{unityAsset ? '确认本次 Unity 有限授权' : demoExecution ? '允许并开始执行' : fullAccess ? '允许完全权限并开始' : '允许本次执行'}</button>
      {demoExecution && <button disabled={action.isPending} onClick={() => action.mutate('cancel', {onSuccess: () => onContinue?.()})}>继续讨论</button>}</div>
    {action.isPending && <p role="status">正在授予本次执行权限…</p>}
  </section>);
  if (inline) return <article className="agent-conversation-run" data-state={task.status}>
    {projectDemo && <p className="agent-request-goal"><strong>制作要求</strong><br />{task.goal}</p>}
    {productionPreparation != null && <ProductionPreparationSummary value={productionPreparation} />}
    <ExperienceReferences projectId={task.project_id ?? null} useKey={`task:${task.id}:call:`} exact={false} sourceId={memorySourceId} /><MemoryMessage projectId={task.project_id ?? null} originKey={`task:${task.id}`} sourceId={memorySourceId} text={task.goal} active={busy(task) || task.status==='cancel_pending'}/>

    {authorization}
    {native && task.status !== 'awaiting_authorization' && <NativeConversation task={task} />}
    {!native && agentProjectDemo && task.status !== 'awaiting_authorization' && <TypedDemoConversation task={task} />}
    {!native && !agentProjectDemo && task.status !== 'awaiting_authorization' && <>
      <details className="agent-turn-activity"><summary>{busy(task) ? '正在执行' : `历史执行 · 用时 ${Math.max(0, Math.round((Date.parse(task.finished_at ?? task.updated_at) - Date.parse(task.created_at)) / 1000))} 秒`} · {LABELS[task.status] ?? task.status}</summary>

      {fullAccess && activity != null && <p className="agent-task-live-activity" role="status">{activityLabel(activity)}</p>}
      {fullAccess && task.observations.codex != null && <CodexConversationResult value={task.observations.codex} />}
      {!!task.actions.length && <ol className="agent-conversation-events">{task.actions.map(record => <li key={record.request_id} data-state={record.state}>
        <span className="agent-event-marker" aria-hidden="true"/><div><strong>{ACTIONS[record.action.capability_id] ?? record.action.capability_id}</strong>
          <span>{record.state === 'succeeded' ? '完成' : record.state === 'running' ? '执行中' : record.state}</span>
          <p>{record.action.rationale}</p>{record.reason && <p role="alert">{record.reason}</p>}
          {record.verification_result && <p>{record.verification_result.verdict === 'PASS' ? '该版本验收通过' : record.verification_result.verdict === 'FAIL' ? '该版本验收失败' : '证据不完整'} · {record.verification_result.project_revision}</p>}
          {record.action.capability_id === 'code.file.read' && record.result && <CodeReadEvidence result={record.result} />}
          {record.action.capability_id === 'code.file.write' && record.result && <CodeWriteEvidence result={record.result} />}
          {record.action.capability_id === 'environment.object.transform' && record.result && <SceneTransformEvidence result={record.result} />}
        </div>
      </li>)}</ol>}
      {task.reason && <p className="agent-conversation-result">{task.reason}</p>}
      </details>
    </>}
    {card.allow_game_execution && task.grant && <GameRuntimePanel task={task} headless onPreviewChange={onPreviewChange} />}
    {followup}
    <footer>
      {(busy(task) || task.status === 'cancel_pending' || task.status === 'blocked') && <button disabled={action.isPending || task.cancel_requested || task.status === 'cancel_pending'} onClick={() => action.mutate('cancel')}>{task.cancel_requested || task.status === 'cancel_pending' ? '正在停止…' : nativeProduction ? '停止本轮' : '停止任务'}</button>}
      {task.status === 'blocked' && task.grant && !grantExpired && <button disabled={action.isPending} onClick={() => action.mutate('resume')}>检查连接并继续</button>}
    </footer>
    {action.error && <p role="alert">{action.error.message}</p>}
  </article>;
  return <article className={`agent-task-card${inline ? ' agent-conversation-run' : ''}`} data-state={task.status}>
    {productionPreparation != null && <ProductionPreparationSummary value={productionPreparation} />}
    <ExperienceReferences projectId={task.project_id ?? null} useKey={`task:${task.id}:call:`} exact={false} sourceId={memorySourceId} /><MemoryMessage projectId={task.project_id ?? null} originKey={`task:${task.id}`} sourceId={memorySourceId} text={task.goal} active={busy(task) || task.status==='cancel_pending'}/>
    <header><strong>{task.goal}</strong><span role="status">{LABELS[task.status] ?? task.status}</span></header>
    <small>{fullAccess ? `CLI 启动 ${task.cli_invocations_used}/1 · 内部模型次数未知` : `模型调用 ${task.model_calls_used}/${card.max_model_calls}`} · 费用{task.cost_usd == null ? '未知' : `$${task.cost_usd.toFixed(4)}`} · {task.project_id}</small>
    {authorization}
    {task.reason && <p className="agent-task-reason" role="alert">{task.reason}</p>}
    {fullAccess && activity != null && <p className="agent-task-live-activity" role="status">最近执行活动：{activityLabel(activity)}</p>}
    {fullAccess && task.observations.codex != null && <details><summary>查看 Codex 结果与执行摘要</summary><pre>{JSON.stringify(task.observations.codex, null, 2)}</pre></details>}
    {card.allow_game_execution && task.grant && <GameRuntimePanel task={task} onPreviewChange={onPreviewChange} />}
    {card.allow_game_execution && task.grant && <BrowserObservationPanel task={task} />}
    {card.allow_game_execution && task.grant && <BrowserInteractionPanel task={task} />}
    {card.allow_game_execution && task.observations.game_diagnostics != null
      && <GameDiagnosticSummary value={task.observations.game_diagnostics} />}
    {card.allow_model_image_input && task.observations.model_image_input != null
      && <ModelImageInputSummary value={task.observations.model_image_input} />}
    <ol className="agent-action-tree">{task.actions.map(record => <li key={record.request_id} data-state={record.state}>
      <strong>{ACTIONS[record.action.capability_id] ?? record.action.capability_id}</strong><span>{record.state === 'succeeded' ? '已执行' : record.state === 'running' ? '执行中' : record.state}</span>
      <small>{record.action.rationale}</small>{record.reason && <p>{record.reason}</p>}
      {record.verification_result && <p>{record.verification_result.verdict === 'PASS' ? '该版本验收通过' : record.verification_result.verdict === 'FAIL' ? '该版本验收失败' : '证据不完整'} · {record.verification_result.project_revision}</p>}
      {record.action.capability_id === 'code.file.write' && record.result && <CodeWriteEvidence result={record.result} />}
      {record.action.capability_id === 'environment.object.transform' && record.result && <SceneTransformEvidence result={record.result} />}
    </li>)}</ol>
    {followup}
    <footer>
      {(busy(task) || task.status === 'blocked' || (task.status === 'awaiting_authorization' && !demoExecution)) && <button disabled={action.isPending || task.cancel_requested} onClick={() => action.mutate('cancel')}>{task.cancel_requested ? '正在停止…' : '停止任务'}</button>}
      {task.status === 'blocked' && task.grant && !grantExpired && <button disabled={action.isPending} onClick={() => action.mutate('resume')}>检查连接并继续</button>}
      {!inline && !nativeProduction && ((grantExpired && task.status === 'blocked') || ['interrupted', 'failed', 'needs_approval'].includes(task.status)) && <button disabled={restart.isPending} onClick={() => restart.mutate()}>重新准备独立任务</button>}
      {!inline && onContinue && ['completed', 'review_required', 'failed', 'needs_approval'].includes(task.status) && <button onClick={onContinue}>继续修改同一工程</button>}
      {!inline && <button aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? '收起记录' : '查看执行记录'}</button>}
    </footer>
    {action.error && <p role="alert">{action.error.message}</p>}
    {restart.error && <p role="alert">{restart.error.message}</p>}
    {!inline && expanded && <section className="agent-task-records" aria-label="执行事件与证据">
      {events.error && <p role="alert">{events.error.message}</p>}
      <ol>{events.data?.events.map(event => <li key={event.sequence}><time>{new Date(event.occurred_at).toLocaleTimeString()}</time> {event.event_type}</li>)}</ol>
      <details><summary>工具回读证据</summary><pre>{JSON.stringify(task.observations, null, 2)}</pre></details>
    </section>}
  </article>;
}

export function ProductionPreparationSummary({value}:{value:unknown}) {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  const recommendation = record.recommendation && typeof record.recommendation === 'object'
    ? record.recommendation as Record<string, unknown> : record;
  const assets = Array.isArray(recommendation.assets) ? recommendation.assets
    : Array.isArray(recommendation.selected_assets) ? recommendation.selected_assets : [];
  const experiences = Array.isArray(recommendation.experiences) ? recommendation.experiences
    : Array.isArray(recommendation.selected_experiences) ? recommendation.selected_experiences : [];
  const skills = Array.isArray(recommendation.skills) ? recommendation.skills
    : Array.isArray(recommendation.selected_skills) ? recommendation.selected_skills : [];
  const status = typeof record.status === 'string' ? record.status : 'ready';
  const failure = typeof record.failure_message === 'string' ? record.failure_message
    : typeof record.reason === 'string' ? record.reason
    : typeof record.error === 'string' ? record.error : null;
  const call = record.call && typeof record.call === 'object' ? record.call as Record<string, unknown> : null;
  const materialization = Array.isArray(record.materialization) ? record.materialization : [];
  const actualUsage = Array.isArray(record.actual_usage) ? record.actual_usage : [];
  const adjustments = Array.isArray(record.adjustments) ? record.adjustments : [];
  const runtimeValidation = record.runtime_validation && typeof record.runtime_validation === 'object'
    ? record.runtime_validation as Record<string, unknown> : null;
  const label = status === 'completed' || status === 'ready' || status === 'succeeded'
    ? '已完成推荐' : status === 'skipped' ? '未调用推荐模型' : '推荐不可用，制作已继续';
  return <details className="agent-production-preparation">
    <summary>本次选材与经验 · {label}</summary>
    {failure && <p role="status">{failure}</p>}
    <p>推荐资产 {assets.length} 项 · 经验 {experiences.length} 条 · 制作技能 {skills.length} 项</p>
    {!!assets.length && <section><strong>资产</strong><ul>{assets.map((item,index)=><li key={index}>{preparationItem(item)}</li>)}</ul></section>}
    {!!experiences.length && <section><strong>经验</strong><ul>{experiences.map((item,index)=><li key={index}>{preparationItem(item)}</li>)}</ul></section>}
    {!!skills.length && <section><strong>制作方式</strong><ul>{skills.map((item,index)=><li key={index}>{preparationItem(item)}</li>)}</ul></section>}
    {!!materialization.length && <section><strong>资产提供与复制</strong><ul>{materialization.map((item,index)=><li key={index}>{preparationEvidence(item, 'materialization')}</li>)}</ul></section>}
    {!!actualUsage.length && <section><strong>实际引用</strong><ul>{actualUsage.map((item,index)=><li key={index}>{preparationEvidence(item, 'usage')}</li>)}</ul></section>}
    {!!adjustments.length && <section><strong>执行调整与缺口</strong><ul>{adjustments.map((item,index)=><li key={index}>{preparationAdjustment(item)}</li>)}</ul></section>}
    {runtimeValidation && <section><strong>运行验证</strong><p>{evidenceLabel(runtimeValidation.project_pipeline)} · 资产画面：{evidenceLabel(runtimeValidation.asset_visual_validation)}</p>
      {typeof runtimeValidation.reason === 'string' && <small>{runtimeValidation.reason}</small>}</section>}
    {call?.usage != null && <small>推荐模型用量：{JSON.stringify(call.usage)}</small>}
    <details><summary>查看推荐记录</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>
  </details>;
}

function preparationAdjustment(value: unknown) {
  if (!value || typeof value !== 'object') return String(value);
  const item = value as Record<string, unknown>;
  const id = item.candidate_id ?? '未命名';
  return `${String(id)} · ${evidenceLabel(item.state)}${item.reason ? ` · ${String(item.reason)}` : ''}`;
}

function preparationEvidence(value: unknown, kind: 'materialization' | 'usage') {
  if (!value || typeof value !== 'object') return String(value);
  const item = value as Record<string, unknown>;
  const id = item.candidate_id ?? item.source_asset_id ?? '未命名';
  if (kind === 'usage') {
    const paths = Array.isArray(item.reference_paths) ? item.reference_paths.join('、') : '';
    return `${String(id)} · ${evidenceLabel(item.actual_reference)}${paths ? ` · ${paths}` : ''}`;
  }
  const state = item.copy_state ?? item.state ?? item.provision_state ?? 'provided';
  return `${String(id)} · ${evidenceLabel(state)}${item.project_asset_id ? ` · 项目资产 ${String(item.project_asset_id)}` : ''}`;
}

function evidenceLabel(value: unknown) {
  const labels: Record<string, string> = {
    recommended: '已推荐', provided: '已提供', copied: '已复制', preserved: '已保留用户文件',
    adopted: '已采用为项目资产', already_adopted: '项目中已存在', not_adopted: '未采用',
    not_provided: '提供失败',
    provision_failed: '提供失败后调整', selected_reference_not_observed: '未观察到实际采用',
    referenced: '源码已引用', not_observed: '未观察到源码引用', passed: '工程运行链通过',
    failed: '工程运行链未通过', not_run: '工程运行链未执行', not_verified: '未验证',
  };
  const key = String(value ?? 'not_verified');
  return labels[key] ?? key;
}

function preparationItem(value: unknown) {
  if (typeof value === 'string') return value;
  if (!value || typeof value !== 'object') return String(value);
  const item = value as Record<string, unknown>;
  const id = item.candidate_id ?? item.asset_id ?? item.experience_id ?? item.skill_id ?? item.id ?? '未命名';
  const reason = item.reason ?? item.rationale ?? item.purpose ?? item.use ?? '';
  return `${String(id)}${reason ? ` · ${String(reason)}` : ''}`;
}

type GameOperation = 'prepare' | 'check' | 'build' | 'preview_start' | 'preview_stop';

export function GameRuntimePanel({ task, headless = false, onPreviewChange, previewWhenRunning = false }: { task: AgentTask; headless?: boolean; onPreviewChange?: (url: string | null) => void; previewWhenRunning?: boolean }) {
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
  const updateDemo = useMutation({mutationFn:()=>agentTasks.updateProjectDemo(task.id), onSuccess:async()=>{
    await cache.invalidateQueries({queryKey:['agent-tasks']});
    await cache.invalidateQueries({queryKey:agentTaskKeys.game(task.id)});
  }});
  const snapshot = query.data;
  const deliverable = task.status === 'completed' || task.status === 'review_required';
  const projectDemo = ['project-demo', 'project-demo-agent'].includes(task.authorization_card.task_profile);
  const previewUrl = (previewWhenRunning || projectDemo || deliverable) && snapshot?.preview?.status === 'running' && snapshot.preview.preview_url && (projectDemo || !snapshot.preview.source_stale)
    ? snapshot.preview.preview_url : null;
  useEffect(() => { if (query.data) onPreviewChange?.(previewUrl); }, [onPreviewChange, previewUrl, query.data]);
  if (headless) return null;
  if (query.isPending) return <section className="agent-game-runtime"><p role="status">读取工程运行状态…</p></section>;
  if (query.error) return <section className="agent-game-runtime"><p role="alert">工程状态读取失败：{query.error.message}</p></section>;
  if (!snapshot) return null;
  const previewRunning = snapshot.preview?.status === 'running';
  const agentBusy = busy(task);
  const latest = [snapshot.dependency, snapshot.check, snapshot.build, snapshot.preview].filter(Boolean).at(-1);
  return <section className="agent-game-runtime" aria-label="游戏工程运行">
    <header><div><strong>游戏工程</strong><small>{snapshot.branch}</small></div>
      {previewRunning && snapshot.preview?.preview_url && (projectDemo || !snapshot.preview.source_stale)
        ? <a href={snapshot.preview.preview_url} target="_blank" rel="noopener noreferrer">新窗口打开 ↗</a>
        : <span>{snapshot.preview?.source_stale ? '源码已改变 · 需重新构建' : '预览未运行'}</span>}</header>
    <p><code>{snapshot.workspace_root}</code></p>
    {projectDemo && <p role={snapshot.update_state === 'failed' ? 'alert' : 'status'}>{snapshot.update_state === 'building' ? '正在构建' : snapshot.update_state === 'failed' ? '更新失败 · 上一试玩仍可用' : snapshot.build?.source_stale ? '内容已改变 · 待更新试玩' : snapshot.update_state === 'updated' ? '试玩已更新' : '源已保存后可更新试玩'}</p>}
    <dl><div><dt>依赖</dt><dd>{snapshot.dependencies_ready ? '已准备' : '未准备'}</dd></div>
      <div><dt>类型检查</dt><dd>{runLabel(snapshot.check)}</dd></div><div><dt>构建</dt><dd>{runLabel(snapshot.build)}</dd></div>
      <div><dt>预览</dt><dd>{previewRunning ? '运行中' : runLabel(snapshot.preview)}</dd></div></dl>
    <div className="agent-game-actions">
      {projectDemo && <button className="primary" disabled={updateDemo.isPending || agentBusy} onClick={()=>updateDemo.mutate()}>{updateDemo.isPending ? '正在更新…' : '更新 Demo'}</button>}
      {!projectDemo && task.authorization_card.allow_dependency_install && <button disabled={operation.isPending || agentBusy} onClick={() => operation.mutate('prepare')}>准备依赖</button>}
      {!projectDemo && <button disabled={operation.isPending || agentBusy || !snapshot.dependencies_ready} onClick={() => operation.mutate('check_build')}>检查并构建</button>}
      {!projectDemo && <button disabled={operation.isPending || agentBusy || snapshot.build?.status !== 'succeeded' || snapshot.build.source_stale === true || previewRunning} onClick={() => operation.mutate('preview_start')}>启动预览</button>}
      <button disabled={operation.isPending || agentBusy || !previewRunning} onClick={() => operation.mutate('preview_stop')}>停止预览</button>
    </div>
    {operation.isPending && <p role="status">正在执行固定工程操作…</p>}
    {operation.error && <p role="alert">{operation.error.message}</p>}
    {updateDemo.error && <p role="alert">{updateDemo.error.message}</p>}
    {latest?.log && <details><summary>最近日志 · {latest.operation}</summary><pre>{latest.log}</pre></details>}
    <small>预览运行后会自动显示在右侧；浏览器错误与玩法结果仍需人工验收。</small>
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

function GameDiagnosticSummary({ value }: { value: unknown }) {
  if (!value || typeof value !== 'object' || !('checks' in value)
      || !value.checks || typeof value.checks !== 'object' || Array.isArray(value.checks)) return null;
  const checks = Object.entries(value.checks).filter((entry): entry is [string, Record<string, unknown>] =>
    !!entry[1] && typeof entry[1] === 'object' && !Array.isArray(entry[1]));
  if (!checks.length) return <section className="agent-game-runtime" aria-label="Agent 诊断证据">
    <header><strong>Agent 诊断证据</strong><span>未执行</span></header>
    <small>尚无当前构建的浏览器检查证据。</small></section>;
  const labels: Record<string, string> = { pass:'通过', fail:'失败', stale:'源码已改变',
    not_run:'未执行', unknown:'证据未知' };
  return <section className="agent-game-runtime" aria-label="Agent 诊断证据">
    <header><strong>Agent 诊断证据</strong><span>按构建与检查范围记录</span></header>
    <dl>{checks.map(([name, diagnostic]) => {
      const scope = diagnostic.scope && typeof diagnostic.scope === 'object' && !Array.isArray(diagnostic.scope)
        ? diagnostic.scope as Record<string, unknown> : {};
      const assertions = diagnostic.assertions && typeof diagnostic.assertions === 'object' && !Array.isArray(diagnostic.assertions)
        ? diagnostic.assertions as Record<string, unknown> : {};
      const failed = Array.isArray(assertions.failed) ? assertions.failed.join(', ') : '';
      return <div key={name}><dt>{name}</dt><dd>{labels[String(diagnostic.evidence_status)] ?? '证据未知'}
        {failed && ` · 失败断言 ${failed}`}
        {scope.build_run_id == null ? null : ` · 构建 ${String(scope.build_run_id)}`}</dd></div>;
    })}</dl>
    <small>局部行为通过不代表全局玩法或视觉评审通过；源码改变后的旧证据会标记为过期。</small>
  </section>;
}

function ModelImageInputSummary({ value }: { value: unknown }) {
  if (!value || typeof value !== 'object' || !('status' in value)) return null;
  const status = String(value.status);
  const labels: Record<string, string> = { provided:'截图已随本次模型请求发送', not_authorized:'未授权',
    provider_unsupported:'当前提供方不支持图片输入', provider_support_unknown:'当前模型图片能力未确认',
    no_current_screenshot:'尚无当前截图', screenshot_stale:'截图已因源码改变过期', request_failed:'图片请求未完成' };
  return <section className="agent-game-runtime" aria-label="模型图片输入">
    <header><strong>模型图片输入</strong><span>{labels[status] ?? status}</span></header>
    {'artifact_id' in value && <small>截图 {String(value.artifact_id)} v{'version' in value ? String(value.version) : '?'}
      {'browser_run_id' in value ? ` · 浏览器运行 ${String(value.browser_run_id)}` : ''}</small>}
    <small>{status === 'provided' ? '该记录证明图片字节进入了指定模型请求；不等于完成视觉评审。'
      : '文本诊断仍可使用；不会改换提供方、模型或预算。'}</small>
  </section>;
}

function CodeWriteEvidence({ result }: { result: unknown }) {
  if (!result || typeof result !== 'object' || !('evidence' in result)) return null;
  const evidence = result.evidence;
  if (!evidence || typeof evidence !== 'object' || !('path' in evidence)) return null;
  const diff = 'diff' in evidence && typeof evidence.diff === 'string' ? evidence.diff : null;
  const source = 'readback' in evidence && typeof evidence.readback === 'string' ? evidence.readback
    : 'after' in evidence && typeof evidence.after === 'string' ? evidence.after : null;
  return <details className="agent-source-evidence"><summary>查看源代码 · {String(evidence.path)}</summary>
    {source ? <pre><code>{source}</code></pre> : <pre>{JSON.stringify(evidence, null, 2)}</pre>}
    {diff && <details><summary>查看本次差异</summary><pre>{diff}</pre></details>}
  </details>;
}

function CodeReadEvidence({ result }: { result: unknown }) {
  if (!result || typeof result !== 'object' || !('evidence' in result)) return null;
  const evidence = result.evidence;
  if (!evidence || typeof evidence !== 'object' || !('path' in evidence)
      || !('content' in evidence) || typeof evidence.content !== 'string') return null;
  return <details className="agent-source-evidence"><summary>查看源代码 · {String(evidence.path)}</summary>
    <pre><code>{evidence.content}</code></pre>
  </details>;
}

function CodexConversationResult({ value }: { value: unknown }) {
  if (!value || typeof value !== 'object') return null;
  const result = 'result' in value && value.result && typeof value.result === 'object'
    && 'result' in value.result && typeof value.result.result === 'string' ? value.result.result : null;
  if (result) return <div className="agent-conversation-result"><MarkdownMessage text={result} /></div>;
  return <details><summary>查看 Agent 执行摘要</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}

function providerLabel(provider: string | null) {
  if (provider === 'codebuddycli') return 'CodeBuddy';
  if (provider === 'codexcli') return 'Codex';
  return 'Agent';
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

export function AgentTaskActivity({ projectId, tasks }: { projectId: string | null; tasks?: AgentTask[] }) {
  if (tasks) return <TaskActivityView tasks={tasks}/>;
  if (!projectId) return null;
  return <ProjectAgentTaskActivity projectId={projectId} />;
}

function ProjectAgentTaskActivity({ projectId }: { projectId: string }) {
  const tasks = useTasks(projectId);
  return <TaskActivityView tasks={tasks.data?.tasks ?? []}/>;
}

function TaskActivityView({ tasks }: { tasks: AgentTask[] }) {
  const visible = tasks.filter(task => !task.archived);
  const task = visible.find(busy) ?? visible[0];
  if (!task) return null;
  const current = task.actions.find(record => record.state === 'running') ?? task.actions.at(-1);
  return <aside className="agent-task-activity" aria-label="当前 Agent 进度" role="status">
    <strong>{LABELS[task.status] ?? task.status}</strong><span>{current ? ACTIONS[current.action.capability_id] ?? current.action.capability_id : task.goal}</span>
    <small>{task.authorization_card.execution_mode !== 'typed-tools' ? `CLI ${task.cli_invocations_used}/1` : `模型 ${task.model_calls_used}/${task.authorization_card.max_model_calls}`} · {task.cost_usd == null ? '费用未知' : '费用已报告'}</small>
  </aside>;
}

function taskConversationId(task: AgentTask): string {
  const context = task.observations.production_card_context ?? task.observations.card_context;
  return context && typeof context === 'object' && !Array.isArray(context)
    && 'conversation_id' in context && typeof context.conversation_id === 'string' ? context.conversation_id : 'original';
}

/** Render persisted typed actions directly; these records are not a native text stream. */
export function TypedDemoConversation({task}: {task: AgentTask}) {
  const states: Record<string,string> = {planned:'尚未执行',running:'执行中',succeeded:'已完成',failed:'失败',uncertain:'结果未确认',blocked:'受阻'};
  return <div className="agent-native-conversation" aria-label="Agent 执行记录">
    <p role="status">{LABELS[task.status] ?? task.status}</p>
    {task.actions.map(record => {
      const input = record.action.inputs ?? {};
      const evidence = record.result?.evidence;
      const evidenceRecord = evidence && typeof evidence === 'object' && !Array.isArray(evidence)
        ? evidence as Record<string, unknown> : undefined;
      const path = input.path ?? input.file_path ?? evidenceRecord?.path;
      const command = input.command;
      return <div key={record.request_id ?? record.action.action_id} className="agent-typed-action" data-state={record.state}>
        <details className="agent-native-tool" data-state={record.state}><summary>
          <span className="agent-tool-indicator" aria-hidden="true">{record.state === 'running' ? '◌' : record.state === 'succeeded' ? '✓' : ['failed','blocked','uncertain'].includes(record.state) ? '!' : '·'}</span>
          <span>{ACTIONS[record.action.capability_id] ?? record.action.capability_id}</span>
          {typeof path === 'string' && <code>{path}</code>}
          <span className="agent-tool-state">{states[record.state] ?? record.state}</span></summary>
        {typeof command === 'string' && <pre className="agent-typed-command">{command}</pre>}
        {record.action.rationale && <p>{record.action.rationale}</p>}
        <details><summary>查看输入与结果</summary><pre>{JSON.stringify({capability:record.action.capability_id,inputs:input,result:record.result,verification:record.verification_result}, null, 2)}</pre></details>
        </details>
        {record.reason && <p role="alert">{record.reason}</p>}
      </div>;
    })}
    {!task.actions.length && busy(task) && <p role="status">等待 Agent 返回执行记录…</p>}
    {task.observations.codex != null && <CodexConversationResult value={task.observations.codex} />}
    {task.reason && <p role={['failed','blocked','interrupted','needs_approval'].includes(task.status) ? 'alert' : 'status'}>{task.reason}</p>}
  </div>;
}

function NativeConversation({task}: {task: AgentTask}) {
  const items = Array.isArray(task.observations.native_conversation) ? task.observations.native_conversation : [];
  const workspaceChanges = task.observations.native_workspace_changes;
  const hasWorkspaceChanges = workspaceChanges && typeof workspaceChanges === 'object' && !Array.isArray(workspaceChanges);
  const anonymousTools = items.filter(item => item && typeof item === 'object' && !Array.isArray(item)
    && item.type === 'tool' && (!item.input || typeof item.input !== 'object' || !Object.keys(item.input).length));
  const reply = task.observations.codex;
  const finalText = reply && typeof reply === 'object' && !Array.isArray(reply)
    && 'result' in reply && reply.result && typeof reply.result === 'object' && !Array.isArray(reply.result)
    && 'result' in reply.result && typeof reply.result.result === 'string' ? reply.result.result : '';
  const finalAlreadyShown = items.some(item => item && typeof item === 'object'
    && !Array.isArray(item) && item.type === 'assistant' && item.text === finalText);
  return <div className="agent-native-conversation" aria-label="Agent 对话">
    {items.map((item, index) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) return null;
      if (item.type === 'assistant' && typeof item.text === 'string' && item.text)
        return <div className="agent-native-message" key={index}><MarkdownMessage text={item.text} /></div>;
      if (item.type === 'tool' && typeof item.name === 'string'
          && (item.input && typeof item.input === 'object' && Object.keys(item.input).length))
        return <NativeToolActivity key={index} item={item} />;
      return null;
    })}
    {reply != null && !finalAlreadyShown && <CodexConversationResult value={reply} />}
    {hasWorkspaceChanges
      ? <NativeWorkspaceChanges value={workspaceChanges as Record<string, unknown>} />
      : anonymousTools.length > 0 && !busy(task)
        ? <p className="agent-native-history-note">本次旧记录包含 {anonymousTools.length} 个工具动作，但未保存参数。</p>
        : null}
    {busy(task) && <p className="agent-native-working" role="status">Agent 正在工作…</p>}
    {!busy(task) && task.status !== 'review_required' && task.reason && <p role="alert">{nativeTaskReason(task)}</p>}
  </div>;
}

function nativeTaskReason(task: AgentTask) {
  const reason = (task.reason ?? '').replace(/^[A-Z][A-Z0-9_]+:\s*/, '');
  if (task.observations.native_production === true && task.status === 'cancelled')
    return '本轮已停止；已保留同一制作会话、工程和已有写入。可在下方继续发送下一轮修改要求。';
  if (!reason.includes('执行已到时间上限')) return reason;
  if (task.authorization_card.max_duration_seconds == null)
    return reason.replace('本次 Agent 执行已到时间上限', '本次 Agent 执行被外部时限终止');
  const minutes = Math.round(task.authorization_card.max_duration_seconds / 60);
  return reason.replace('本次 Agent 执行已到时间上限', `本次 Agent 已运行到 ${minutes} 分钟授权时限`);
}

function NativeToolActivity({item}: {item: Record<string, unknown>}) {
  const name = String(item.name);
  const input = item.input && typeof item.input === 'object' ? item.input as Record<string, unknown> : {};
  const path = typeof input.file_path === 'string' ? input.file_path : typeof input.path === 'string' ? input.path : '';
  const command = typeof input.command === 'string' ? input.command : '';
  const description = typeof input.description === 'string' ? input.description : '';
  const pattern = typeof input.pattern === 'string' ? input.pattern : '';
  const verb = ({Read:'读取', Write:'写入', Edit:'编辑', Bash:'运行命令', Glob:'查找文件', Grep:'搜索内容'} as Record<string,string>)[name] ?? name;
  const detail = path || description || command || pattern;
  const active = item.state === 'running' || item.state === 'in_progress';
  const label = <><span aria-hidden="true">{active ? '◌' : item.state === 'failed' ? '×' : '✓'}</span><span>{verb}</span>{detail && <span className="agent-tool-target">{detail}</span>}</>;
  if (!detail) return <div className="agent-native-tool" title="此条早期记录未保存工具参数">{label}</div>;
  return <details className="agent-native-tool" data-state={active ? 'running' : item.state === 'failed' ? 'failed' : 'completed'}><summary>{label}</summary>
    {path && <p>文件：<code>{path}</code>{typeof input.offset === 'number' ? ` · 从第 ${input.offset} 行` : ''}</p>}
    {description && <p>操作：{description}</p>}
    {command && <pre>{command}</pre>}
    {pattern && <p>搜索：<code>{pattern}</code></p>}
    <small>{active ? '执行中' : item.state === 'failed' ? '执行失败' : '执行结束'}</small>
  </details>;
}

function NativeWorkspaceChanges({value}: {value: Record<string, unknown>}) {
  const files = Array.isArray(value.files) ? value.files.filter(item => item && typeof item === 'object' && !Array.isArray(item)) as Record<string, unknown>[] : [];
  if (value.available === false) return <p className="agent-native-history-note">当前卡片分支的文件状态暂时无法读取。</p>;
  const labels: Record<string, string> = {added:'新增', modified:'修改', deleted:'删除'};
  const marks: Record<string, string> = {added:'A', modified:'M', deleted:'D'};
  return <details className="agent-workspace-changes">
    <summary><span aria-hidden="true">✓</span><strong>当前分支文件变更</strong><small>{files.length} 个文件</small></summary>
    {files.length === 0
      ? <p>工作区相对当前分支没有文件变更。</p>
      : <ul>{files.map((file, index) => {
          const change = typeof file.change === 'string' ? file.change : 'modified';
          const path = typeof file.path === 'string' ? file.path : '';
          return <li key={`${path}-${index}`} data-change={change}>
            <span className="agent-change-mark" aria-label={labels[change] ?? change}>{marks[change] ?? 'M'}</span>
            <code>{path}</code>
          </li>;
        })}</ul>}
  </details>;
}
