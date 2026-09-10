import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentTasks, agentTaskKeys, type AgentTask } from './client';

export function BrowserInteractionPanel({task}: {task: AgentTask}) {
  const cache = useQueryClient();
  const query = useQuery({queryKey:agentTaskKeys.game(task.id), queryFn:() => agentTasks.gameStatus(task.id)});
  const build = useMutation({mutationFn:() => agentTasks.gameOperation(task.id, 'build_test'),
    onSuccess:value => cache.setQueryData(agentTaskKeys.game(task.id), value)});
  const check = useMutation({mutationFn:(delivery:boolean) => agentTasks.interact(task.id, {
    check:delivery ? 'current-input' : 'movement-collection', state_id:'start',
    steps: delivery ? [{keys:['ArrowDown'],duration_ms:400},{keys:[],duration_ms:160}]
      : [{keys:['ArrowDown'],duration_ms:400},{keys:[],duration_ms:160},
        {keys:['ArrowUp'],duration_ms:400},{keys:['ArrowDown'],duration_ms:400}],
  }), onSuccess:value => cache.setQueryData(agentTaskKeys.game(task.id), value)});
  const cancel = useMutation({mutationFn:() => agentTasks.cancelObservation(task.id)});
  const revoke = useMutation({mutationFn:() => agentTasks.revokeInteraction(task.id)});
  const authorization = task.browser_interaction_authorization;
  const authorized = task.authorization_card.allow_browser_interaction && authorization
    && !authorization.revoked
    && (authorization.expires_at == null || Date.parse(authorization.expires_at) > Date.now()) && !revoke.isSuccess;
  const busy = build.isPending || check.isPending || ['running','queued'].includes(task.status);
  const run = query.data?.interaction;
  const result = run?.observation;
  const artifact = result?.screenshot_artifact;
  const imageUrl = artifact && typeof artifact === 'object' && !Array.isArray(artifact)
    && 'id' in artifact && 'version' in artifact
    && typeof artifact.id === 'string' && typeof artifact.version === 'number'
    ? `/api/agent/projects/${encodeURIComponent(task.project_id)}/artifacts/${encodeURIComponent(artifact.id)}/content?version=${artifact.version}` : null;
  return <section className="agent-game-runtime" aria-label="受控输入检查">
    <header><strong>受控输入检查</strong>
      <button disabled={!authorized || busy} onClick={() => build.mutate()}>生成测试构建</button>
      <button disabled={!authorized || busy || query.data?.test_build?.status !== 'succeeded'}
        onClick={() => check.mutate(false)}>检查移动与收集</button>
      <button disabled={!authorized || busy} onClick={() => check.mutate(true)}>普通构建输入检查</button>
      {check.isPending && <button onClick={() => cancel.mutate()}>取消输入检查</button>}
      {authorized && <button onClick={() => revoke.mutate()}>撤销交互授权</button>}
    </header>
    {!authorized && <p>需要单独授权测试构建、状态控制与有限键盘输入；旧观察授权不会自动升级。</p>}
    <p>测试起点 start：向下移动 → 松键 → 返回 → 再次经过收集物。仅适用于具有该起点的收集场景，不是通用玩法或视觉验收。</p>
    {(build.isPending || check.isPending) && <p role="status">正在执行本次受控检查…</p>}
    {(query.error || build.error || check.error || cancel.error || revoke.error) && <p role="alert">{(query.error || build.error || check.error || cancel.error || revoke.error)?.message}</p>}
    {query.data?.test_build && <p>测试构建：{query.data.test_build.status} {query.data.test_build.failure_code}</p>}
    {run && <div><p>输入检查：{run.status} {run.failure_code}</p>
      <small>{run.build_kind === 'test' ? '测试构建证据' : '普通交付构建证据'} · 构建 {run.build_run_id} · 预览 {run.preview_run_id}</small>
      {run.source_stale && <p role="alert">构建已改变，结果不代表当前状态。</p>}
      {imageUrl && !run.source_stale && <img src={imageUrl} alt="受控输入后的实际构建截图" style={{maxWidth:'100%'}} />}
      <details open><summary>输入事件、独立状态回读与检查结果</summary><pre>{JSON.stringify(result ?? {reason:run.log},null,2)}</pre></details>
      <small>已采集截图不代表视觉模型已理解；受控时间不代表真实帧率，局部行为检查不代表完整玩法通过。</small>
    </div>}
  </section>;
}
