import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { agentTasks, agentTaskKeys, type AgentTask } from './client';

export function BrowserObservationPanel({task}: {task: AgentTask}) {
  const cache = useQueryClient();
  const query = useQuery({queryKey:agentTaskKeys.game(task.id),
    queryFn:({signal}) => agentTasks.gameStatus(task.id, signal), retry:false});
  useEffect(() => { void cache.invalidateQueries({queryKey:agentTaskKeys.game(task.id)}); }, [cache, task.id, task.updated_at]);
  const observe = useMutation({mutationFn:() => agentTasks.gameOperation(task.id, 'observe'),
    onSuccess:value => cache.setQueryData(agentTaskKeys.game(task.id), value)});
  const cancel = useMutation({mutationFn:() => agentTasks.cancelObservation(task.id)});
  const revoke = useMutation({mutationFn:() => agentTasks.revokeObservation(task.id),
    onSuccess:() => cache.invalidateQueries({queryKey:['agent-production', task.project_id]})});
  const run = query.data?.observation;
  const result = run?.observation;
  const artifact = result && typeof result === 'object' ? result.screenshot_artifact : null;
  const imageUrl = artifact && typeof artifact === 'object' && !Array.isArray(artifact)
    && 'id' in artifact && 'version' in artifact
    && typeof artifact.id === 'string' && typeof artifact.version === 'number'
    ? `/api/agent/projects/${encodeURIComponent(task.project_id)}/artifacts/${encodeURIComponent(artifact.id)}/content?version=${artifact.version}` : null;
  const authorized = task.authorization_card.allow_browser_observation && !!task.browser_authorization
    && !task.browser_authorization.revoked && Date.parse(task.browser_authorization.expires_at) > Date.now();
  return <section className="agent-game-runtime" aria-label="当前构建观察">
    <header><strong>当前构建观察</strong>
      <button disabled={!authorized || observe.isPending || ['running','queued'].includes(task.status)}
        onClick={() => observe.mutate()}>观察当前画面</button>
      {observe.isPending && <button disabled={cancel.isPending} onClick={() => cancel.mutate()}>取消本次观察</button>}
      {authorized && <button disabled={revoke.isPending} onClick={() => revoke.mutate()}>撤销观察授权</button>}
    </header>
    {!authorized && <p>需要有效且包含“独立浏览器运行与截图”的任务授权；可在下一次开发任务的执行范围中勾选。</p>}
    {observe.isPending && <p role="status">正在独立浏览器中加载当前构建并采集画面…</p>}
    {(observe.error || cancel.error || revoke.error || query.error) && <p role="alert">{(observe.error || cancel.error || revoke.error || query.error)?.message}</p>}
    {run && <div>
      <p>{run.mode} · {run.status} {run.failure_code ?? ''}</p>
      <small>构建 {run.build_run_id ?? '未解析'} · 预览 {run.preview_run_id ?? '未解析'}</small>
      {run.source_stale && <p role="alert">检查期间构建改变，以下内容不是当前构建的有效证据。</p>}
      {imageUrl && !run.source_stale && <img src={imageUrl} alt="当前登记构建的实际浏览器截图" style={{maxWidth:'100%'}} />}
      <details><summary>加载状态、浏览器错误和基础诊断</summary><pre>{JSON.stringify(result ?? {reason:run.log}, null, 2)}</pre></details>
      <small>截图已采集不代表视觉模型已评审；此检查不执行玩法验证。游戏诊断未提供时仅显示基础页面诊断。</small>
    </div>}
  </section>;
}
