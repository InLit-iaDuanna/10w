import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { createReviewClient } from '../lab/client';
import type { BranchChangeSet } from '../generated/api-types.ts';
import { layoutTree } from './layout';
import './version-tree.css';

type Props = { projectId: string; projectName: string; client: ReturnType<typeof createReviewClient> };
export function VersionTree({ projectId, projectName, client }: Props) {
  const query = useQuery({ queryKey: ['version-tree', projectId], queryFn: () => client.reviewRequest('GET /api/version-collaboration/tree', {}, undefined) });
  const [selected, setSelected] = useState<string | null>(null);
  const [branch, setBranch] = useState('');
  const [zoom, setZoom] = useState(1);
  const [branchesOpen, setBranchesOpen] = useState(false);
  const [newBranch, setNewBranch] = useState('');
  const [branchPlan, setBranchPlan] = useState<BranchChangeSet | null>(null);
  const [branchBusy, setBranchBusy] = useState(false);
  const [branchError, setBranchError] = useState('');
  const viewport = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLElement>(null);
  const [surfaceWidth, setSurfaceWidth] = useState(360);
  useEffect(() => {
    const element = surface.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setSurfaceWidth(entry.contentRect.width));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const files = useQuery({ queryKey: ['version-tree-files', projectId, selected], enabled: !!selected, queryFn: () => client.reviewRequest('GET /api/version-collaboration/tree/commits/{commit_id}/files', { commit_id: selected! }, undefined) });
  const data = query.data;
  const graph = useMemo(() => layoutTree(data?.commits ?? [], data?.branches ?? [], surfaceWidth - 18), [data, surfaceWidth]);
  const ancestors = useMemo(() => {
    if (!branch || !data) return null;
    const branchHead = data.branches.find(item => item.name === branch)?.commit_id;
    const pending = branchHead ? [branchHead] : [], found = new Set<string>();
    const commits = new Map(data.commits.map(commit => [commit.commit_id, commit]));
    while (pending.length) {
      const id = pending.pop()!;
      if (found.has(id)) continue;
      found.add(id);
      pending.push(...(commits.get(id)?.parent_ids ?? []));
    }
    return found;
  }, [branch, data]);
  const stages: Record<string, string> = { idea: '创意整理', grill: '需求对齐', outline: '大纲策划', stack: '技术方案', cards: '制作规划' };
  const active = data?.commits.find(commit => commit.commit_id === selected);
  const blockedLabels: Record<string, string> = {
    invalid_branch_name: '分支名称不符合 Git 规则',
    dirty_worktree: '存在未提交文件，请先提交或处理',
    merge_conflict: '存在未解决的合并冲突',
    branch_exists: '同名分支已经存在',
    unknown_source_commit: '起点提交已不在当前版本树中',
    branch_missing: '目标分支不存在',
    already_current: '已经位于此分支',
  };
  async function prepareBranch(operation: 'create' | 'switch', branchName: string) {
    setBranchBusy(true); setBranchError(''); setBranchPlan(null);
    try {
      const plan = await client.reviewRequest('POST /api/version-collaboration/tree/branches/preview', {}, {
        operation, branch_name: branchName, source_commit: operation === 'create' ? selected ?? data?.version.commit_id : null,
      });
      setBranchPlan(plan);
    } catch (error) {
      setBranchError(error instanceof Error ? error.message : String(error));
    } finally { setBranchBusy(false); }
  }
  async function applyBranch() {
    if (!branchPlan) return;
    setBranchBusy(true); setBranchError('');
    try {
      const result = await client.reviewRequest('POST /api/version-collaboration/tree/branches/apply', {}, {
        change_set: branchPlan, confirmed: true,
      });
      setBranchPlan(null); setNewBranch(''); setBranch(''); setSelected(result.head_commit);
      await query.refetch();
    } catch (error) {
      setBranchError(error instanceof Error ? error.message : String(error));
    } finally { setBranchBusy(false); }
  }
  function locateHead() {
    if (!data || !viewport.current) return;
    setBranch(''); setSelected(data.version.commit_id);
    const point = graph.positions.get(data.version.commit_id);
    if (point) viewport.current.scrollTo({ left: point.x * zoom - viewport.current.clientWidth / 2, top: point.y * zoom - viewport.current.clientHeight / 2, behavior: 'smooth' });
  }
  return <section ref={surface} className="version-tree" aria-label="Git 版本树">
    <header><strong>版本树</strong><span className="vt-muted">{data ? `${data.version.branch ?? '游离 HEAD'} · ${data.mode.toUpperCase()}` : 'Git'}</span>
      <div className="vt-actions"><select aria-label="筛选分支" value={branch} onChange={event => setBranch(event.target.value)}><option value="">全部分支</option>{data?.branches.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select>
      <button onClick={locateHead} disabled={!data}>当前位置</button><button aria-expanded={branchesOpen} onClick={() => { setBranchesOpen(value => !value); setBranchPlan(null); setBranchError(''); }} disabled={!data}>分支</button><button onClick={() => query.refetch()} disabled={query.isFetching}>刷新</button></div>
    </header>
    {query.isPending && <p className="vt-message" role="status">正在读取 Git 版本树…</p>}
    {query.isError && <p className="vt-message" role="alert">{query.error.message} <button onClick={() => query.refetch()}>重试</button></p>}
    {data && <><div className="vt-status"><span>{data.conflicted ? '存在合并冲突' : data.dirty ? `${data.changes.length} 个文件待提交` : '工作区已同步'}</span><span>{data.progress ? `${stages[data.progress.stage] ?? data.progress.stage} · ${data.progress.confirmed_versions} 个已确认版本 · ${data.progress.planned_cards} 张计划卡片 · ${data.progress.card_branches} 个卡片分支` : '尚未关联项目进度'}</span><span>{data.branches.length} 个本地分支 · {data.commits.length} 次提交 · 从上到下演进</span></div>
      {!data.commits.length ? <p className="vt-message">还没有可展示的提交。</p> : <div className="vt-body">
        <div className="vt-viewport" ref={viewport} onPointerDown={event => {
          if (event.button !== 0 || (event.target as Element).closest('[data-node]')) return;
          const element = event.currentTarget;
          drag.current = { x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop };
          element.setPointerCapture(event.pointerId);
        }} onPointerMove={event => { if (drag.current) { event.currentTarget.scrollLeft = drag.current.left - event.clientX + drag.current.x; event.currentTarget.scrollTop = drag.current.top - event.clientY + drag.current.y; } }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
          <svg width={graph.width * zoom} height={graph.height * zoom} viewBox={`0 0 ${graph.width} ${graph.height}`} aria-label="提交分叉与合并关系">
            <g className="vt-project-node" transform={`translate(${graph.project.x},${graph.project.y})`}><title>{projectName}</title><rect x="-22" y="-20" width="230" height="52" rx="8"/><text x="0" y="0">项目</text><text x="0" y="20">{projectName.length > 24 ? `${projectName.slice(0, 24)}…` : projectName}</text></g>
            {graph.roots.map(commit => { const point = graph.positions.get(commit.commit_id)!; return <path key={`project-${commit.commit_id}`} d={`M ${graph.project.x} ${graph.project.y + 32} L ${point.x} ${point.y}`} className="vt-edge vt-project-edge"/>; })}
            {data.commits.flatMap(commit => (commit.parent_ids ?? []).map(parent => {
              const from = graph.positions.get(parent), to = graph.positions.get(commit.commit_id)!;
              if (!from) return null;
              return <path key={`${parent}-${commit.commit_id}`} d={`M ${from.x} ${from.y} C ${from.x} ${(from.y + to.y) / 2}, ${to.x} ${(from.y + to.y) / 2}, ${to.x} ${to.y}`} className={`vt-edge ${ancestors && !ancestors.has(commit.commit_id) ? 'vt-dim' : ''}`} />;
            }))}
            {data.commits.map(commit => {
              const point = graph.positions.get(commit.commit_id)!;
              const head = commit.commit_id === data.version.commit_id;
              const refs = data.branches.filter(item => item.commit_id === commit.commit_id).map(item => item.name);
              return <g data-node key={commit.commit_id} transform={`translate(${point.x},${point.y})`} role="button" tabIndex={0} aria-label={`${commit.subject}${head ? '，当前位置' : ''}`} aria-pressed={selected === commit.commit_id} className={`vt-node ${selected === commit.commit_id ? 'vt-selected' : ''} ${ancestors && !ancestors.has(commit.commit_id) ? 'vt-dim' : ''}`} onClick={() => setSelected(commit.commit_id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelected(commit.commit_id); } }}>
                <title>{commit.subject}{refs.length ? ` · ${refs.join(' / ')}` : ''}</title><rect x="-18" y="-27" width="225" height="65" rx="7" /><circle r={head ? 7 : 5} className={head ? 'vt-head' : ''} />
                <text x="18" y="-8" className="vt-ref">{head ? 'HEAD · ' : ''}{data.progress?.milestones[commit.commit_id] ?? commit.commit_id.slice(0, 7)}</text><text x="18" y="13">{commit.subject.length > 19 ? `${commit.subject.slice(0, 19)}…` : commit.subject}</text>
              </g>;
            })}
            {graph.branchTips.map(tip => { const point = graph.positions.get(tip.branch.commit_id)!; const activeBranch = branch === tip.branch.name; return <g key={`branch-${tip.branch.name}`} role="button" tabIndex={0} aria-label={`分支 ${tip.branch.name}${tip.branch.current ? '，当前分支' : ''}`} aria-pressed={activeBranch} className={`vt-branch-node ${activeBranch ? 'vt-selected' : ''}`} onClick={() => setBranch(activeBranch ? '' : tip.branch.name)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setBranch(activeBranch ? '' : tip.branch.name); } }}>
              <path d={`M ${point.x} ${point.y + 32} H 22 V ${tip.y} H ${tip.x - 16}`} className={`vt-edge vt-branch-edge ${ancestors && !activeBranch ? 'vt-dim' : ''}`}/>
              <g data-node transform={`translate(${tip.x},${tip.y})`}><title>{tip.branch.name}</title><rect x="-16" y="-24" width="220" height="60" rx="8"/><circle r="4"/><text x="14" y="-3">{tip.branch.name.length > 29 ? `${tip.branch.name.slice(0, 29)}…` : tip.branch.name}</text><text x="14" y="19" className="vt-ref">{tip.branch.current ? '● 当前分支' : data.progress?.branch_labels[tip.branch.name] ?? '项目分支'}</text></g>
            </g>; })}
          </svg>
        </div>
        {branchesOpen ? <aside className="vt-detail vt-branches"><button className="vt-close" aria-label="关闭分支面板" onClick={() => setBranchesOpen(false)}>×</button><small>分支管理</small><h3>本地分支</h3>
          {data.branches.map(item => <div className="vt-branch" key={item.name}><span><b>{item.name}</b><small>{item.commit_id.slice(0, 8)}</small></span>{item.current ? <em>当前</em> : <button disabled={branchBusy} onClick={() => void prepareBranch('switch', item.name)}>切换</button>}</div>)}
          <form onSubmit={event => { event.preventDefault(); if (newBranch.trim()) void prepareBranch('create', newBranch.trim()); }}><h3>新建分支</h3><label>分支名称<input value={newBranch} onChange={event => setNewBranch(event.target.value)} placeholder="例如 feature/level-map" /></label><small>起点：{(selected ?? data.version.commit_id).slice(0, 10)}{selected ? ' · 已选版本' : ' · 当前 HEAD'}</small><button disabled={branchBusy || !newBranch.trim()}>预览创建</button></form>
          {branchError && <p className="vt-branch-error" role="alert">{branchError}</p>}
          {branchPlan && <div className="vt-change-set"><small>分支操作预览</small><p>{branchPlan.operation === 'create' ? '创建并切换到' : '切换到'} <b>{branchPlan.branch_name}</b></p><p>起点 {branchPlan.source_commit.slice(0, 10)}</p>{branchPlan.blocked_reasons.map(reason => <p className="vt-branch-error" key={reason}>{blockedLabels[reason] ?? reason}</p>)}<div><button onClick={() => setBranchPlan(null)}>取消</button><button className="vt-primary" disabled={branchBusy || !!branchPlan.blocked_reasons.length} onClick={() => void applyBranch()}>确认执行</button></div></div>}
        </aside> : active && <aside className="vt-detail"><button className="vt-close" aria-label="关闭版本详情" onClick={() => setSelected(null)}>×</button><small>提交详情</small><h3>{active.subject}</h3><p>{active.author}</p><p>{new Date(active.authored_at).toLocaleString('zh-CN')}</p><code>{active.commit_id}</code><p>{active.parent_ids?.length && active.parent_ids.length > 1 ? '合并提交' : '普通提交'}</p><small>父提交</small>{active.parent_ids?.map(id => <button key={id} disabled={!graph.positions.has(id)} onClick={() => setSelected(id)}>{id.slice(0, 10)}</button>)}{active.commit_id === data.version.commit_id && <><p>当前位置 · {data.dirty ? '有待提交修改' : '工作区干净'}</p>{data.changes.map(change => <p key={change.path} className="vt-file">{change.path}</p>)}</>}<h3>变更文件{(active.parent_ids?.length ?? 0) > 1 ? ' · 相对第一父提交' : ''}</h3>{files.isPending && <p>正在读取…</p>}{files.isError && <p role="alert">{files.error.message}<button onClick={() => files.refetch()}>重试</button></p>}{files.data?.length === 0 && <p>无文件变化</p>}{files.data?.map(file => <p className="vt-file" key={file.path}>{file.path} <small>{({ added: '新增', modified: '修改', deleted: '删除', renamed: '重命名', conflict: '冲突', untracked: '未跟踪' })[file.kind]}</small></p>)}</aside>}
      </div>}
      <footer><span>实线：提交 · 虚线：分支</span><div><button aria-label="缩小" disabled={zoom <= .5} onClick={() => setZoom(value => Math.max(.5, value - .1))}>−</button><button title="适应当前区域宽度" onClick={() => { setZoom(1); viewport.current?.scrollTo({ left: 0, top: 0 }); }}>适应</button><button aria-label="放大" disabled={zoom >= 1.5} onClick={() => setZoom(value => Math.min(1.5, value + .1))}>＋</button></div></footer>
    </>}
  </section>;
}
