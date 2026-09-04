import * as React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { renderLabApi, type LabState } from './api';
import { RecipeForm, recipeLabels } from './RecipeForm';
import { AovPanel, ComparisonPanel, ProposalPanel, ProvenancePanel } from './ReviewPanels';
import './workbench.css';

const tabs = ['变体比较', 'AOV 通道', '来源链', '审批提案'] as const;
const states: Record<string, string> = {
  queued: '排队中', running: '运行中', waiting_approval: '等待审批',
  succeeded: '已完成', failed: '失败', cancelled: '已取消',
};

function browserSession() {
  const key = 'sceneops.render-lab.session';
  const saved = sessionStorage.getItem(key);
  if (saved) return saved;
  const id = crypto.randomUUID();
  sessionStorage.setItem(key, id);
  return id;
}

export function RenderLabWorkbench() {
  const [session] = React.useState(browserSession);
  const api = React.useMemo(() => renderLabApi(session), [session]);
  const key = ['render-ops', 'lab', session];
  const cache = useQueryClient();
  const query = useQuery({ queryKey: key, queryFn: api.state });
  const [selected, setSelected] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState<(typeof tabs)[number]>('变体比较');
  const [showHelp, setShowHelp] = React.useState(false);
  const mutation = useMutation({ mutationFn: (action: () => Promise<LabState>) => action(),
    onSuccess: state => cache.setQueryData(key, state) });
  const state = query.data;
  const current = state?.jobs.find(record => record.job.job_id === selected) ?? state?.jobs[state.jobs.length - 1];
  return <div className="render-lab">
    <header className="rl-topbar"><a className="rl-brand" href="/">S<span>SceneOps Forge</span></a>
      <div className="rl-title"><small>工作台 07</small><h1>渲染与 AI 变体</h1></div>
      <span className="rl-mode">MOCK · 本地演示</span>
      <button onClick={() => setShowHelp(value => !value)}>操作说明</button>
      <button disabled={mutation.isPending || !state} onClick={() => {
        if (window.confirm('重置当前浏览器会话中的任务、审批和提案？只影响本地演示记录。')) {
          setSelected(null); mutation.mutate(api.reset);
        }
      }}>重置演示</button>
    </header>
    <div className="rl-notice"><span className="rl-dot" />真实渲染 / ComfyUI / 工程写回：BLOCKED
      <span>本地服务可用 · 固定样本可审阅 · 不执行外部作业</span></div>
    {showHelp && <section className="rl-guide"><h2>从配方到审批提案</h2><ol>
      <li>左侧修改提示词或配方，创建任务。队列显示实际缓存规划。</li>
      <li>选择任务并载入固定 mock 样本，查看 AOV 和两份候选图。</li>
      <li>比较页选择基准 / 候选，计算 256 个像素的差异。</li>
      <li>在「审批提案」确认变体、输入灯光强度、生成并审批提案。</li>
    </ol><p>同一标签页刷新可保留本地 API 会话；API 重启或重置后恢复演示数据。提示词、采样数和 Seed 不改变固定样本图像。来源中的 checksum 为 mock 占位值。</p></section>}
    {query.isPending && <div className="rl-empty" role="status"><h2>正在连接本地 API…</h2><p>读取演示场景、配方目录与审批记录。</p></div>}
    {query.error && <div className="rl-empty" role="alert"><h2>本地 API 未连接</h2><p>{query.error.message}</p><p>请确认工作台 dev 命令仍在运行。</p><button onClick={() => query.refetch()}>重新连接</button></div>}
    {mutation.error && <div className="rl-error" role="alert">{mutation.error.message}<button onClick={() => mutation.reset()}>关闭</button></div>}
    {state && current && <>
      <div className="rl-workspace">
        <RecipeForm state={state} busy={mutation.isPending} onPlan={input => mutation.mutate(async () => {
          const next = await api.plan(input); setSelected(next.jobs[next.jobs.length - 1].job.job_id); return next;
        })} />
        <main className="rl-center"><div className="rl-tabs" role="tablist" aria-label="渲染工具">
          {tabs.map(label => <button key={label} role="tab" aria-selected={tab === label} onClick={() => setTab(label)}>{label}</button>)}
        </div><div role="tabpanel" key={`${current.job.job_id}-${current.job.attempt}-${current.variants.length}-${tab}`}>
          {tab === '变体比较' && <ComparisonPanel job={current} api={api} />}
          {tab === 'AOV 通道' && <AovPanel job={current} />}
          {tab === '来源链' && <ProvenancePanel job={current} />}
          {tab === '审批提案' && <ProposalPanel job={current} api={api} busy={mutation.isPending} mutate={request => mutation.mutate(request)} />}
        </div></main>
        <aside className="rl-inspector"><div className="rl-section-heading">02 / 当前任务</div>
          <h3>{recipeLabels[current.recipe.recipe_id]}</h3><code>{current.job.job_id}</code>
          <dl><dt>状态</dt><dd>{states[current.job.state]}</dd><dt>执行模式</dt><dd>MOCK</dd>
            <dt>第几次尝试</dt><dd>{current.job.attempt}</dd><dt>样本分辨率</dt><dd>16 × 16</dd>
            <dt>复用通道</dt><dd>{current.job.cache_plan.reused_passes.length}</dd>
            <dt>待采集通道（规划）</dt><dd>{current.job.cache_plan.capture_passes.length}</dd></dl>
          <details><summary>各通道规划原因</summary><dl>{Object.entries(current.job.cache_plan.reasons).map(([pass, reason]) => <React.Fragment key={pass}><dt>{pass}</dt><dd>{reason}</dd></React.Fragment>)}</dl></details>
          <div className="rl-section-heading">本地操作记录</div>
          <ol className="rl-activity">{state.activity.slice().reverse().map((line, index) => <li key={index}>{line}</li>)}</ol>
        </aside>
      </div>
      <section className="rl-queue"><div className="rl-section-heading"><span>03 / 渲染队列 · {state.jobs.length} 个任务</span><small>点击任务切换上下文</small></div>
        <div className="rl-table-scroll"><table><thead><tr><th>任务</th><th>配方</th><th>状态</th><th>模式</th><th>复用 / 待采集</th><th>操作</th></tr></thead>
          <tbody>{state.jobs.slice().reverse().map(record => <tr key={record.job.job_id} data-selected={current.job.job_id === record.job.job_id}>
            <td><button className="rl-link" onClick={() => setSelected(record.job.job_id)}>{record.job.job_id}</button></td><td>{recipeLabels[record.recipe.recipe_id]}</td>
            <td>{states[record.job.state]}</td><td><span className="rl-mode">MOCK</span></td>
            <td>{record.job.cache_plan.reused_passes.length} / {record.job.cache_plan.capture_passes.length}</td>
            <td><div className="rl-row-actions">{record.job.state === 'queued' && <button disabled={mutation.isPending} onClick={() => mutation.mutate(() => api.jobAction(record.job.job_id, 'load-fixture'))}>载入固定样本</button>}
              {['queued', 'waiting_approval', 'running'].includes(record.job.state) && <button disabled={mutation.isPending} onClick={() => mutation.mutate(() => api.jobAction(record.job.job_id, 'cancel'))}>取消</button>}
              {['cancelled', 'failed'].includes(record.job.state) && <button disabled={mutation.isPending} onClick={() => mutation.mutate(() => api.jobAction(record.job.job_id, 'retry'))}>重试</button>}
            </div></td></tr>)}</tbody></table></div>
      </section>
    </>}
    <footer className="rl-footer"><span>Render Ops / 独立工作台</span><span>live · cached · <strong>mock</strong> · planned · blocked</span></footer>
  </div>;
}
