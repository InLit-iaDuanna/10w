import { useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { createReviewClient } from '../lab/client';
import type { BranchChangeSet } from '../generated/api-types.ts';
import './version-tree.css';
import { ProjectOverview } from './ProjectOverview';

type Props = { projectId: string; projectName: string; client: ReturnType<typeof createReviewClient> };
export function VersionTree({ projectId, projectName, client }: Props) {
  const query = useQuery({ queryKey: ['version-tree', projectId], refetchInterval: 15000, queryFn: () => client.reviewRequest('GET /api/version-collaboration/tree', {}, undefined) });
  const [view, setView] = useState<'overview' | 'history'>('overview');
  const [selected, setSelected] = useState<string | null>(null);
  const [branch, setBranch] = useState('');
  const [branchesOpen, setBranchesOpen] = useState(false);
  const [newBranch, setNewBranch] = useState('');
  const [branchPlan, setBranchPlan] = useState<BranchChangeSet | null>(null);
  const [branchBusy, setBranchBusy] = useState(false);
  const [branchError, setBranchError] = useState('');
  const viewport = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLElement>(null);
  const files = useQuery({ queryKey: ['version-tree-files', projectId, selected], enabled: !!selected, queryFn: () => client.reviewRequest('GET /api/version-collaboration/tree/commits/{commit_id}/files', { commit_id: selected! }, undefined) });
  const data = query.data;
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
    viewport.current.scrollTo({ top: 0, behavior: 'smooth' });
  }
  return <section ref={surface} className="version-tree" aria-label="项目进度与版本">
    <header><strong>{projectName}</strong><span className="vt-muted">{data ? `${data.version.branch ?? '游离 HEAD'} · ${data.mode.toUpperCase()}` : 'Git'}</span>
      <div className="vt-actions" hidden={view !== 'history'}><select aria-label="筛选分支" value={branch} onChange={event => setBranch(event.target.value)}><option value="">全部分支</option>{data?.branches.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select>
      <button onClick={locateHead} disabled={!data}>当前位置</button><button aria-expanded={branchesOpen} onClick={() => { setBranchesOpen(value => !value); setBranchPlan(null); setBranchError(''); }} disabled={!data}>分支</button></div>
    </header>
    <nav className="po-tabs" aria-label="项目视图"><button aria-pressed={view === 'overview'} onClick={() => setView('overview')}>进度总览</button><button aria-pressed={view === 'history'} onClick={() => setView('history')}>版本历史 <small>{data?.commits.length ?? '—'}</small></button><button className="po-refresh" aria-label="刷新项目进度" disabled={query.isFetching} onClick={() => query.refetch()}>{query.isFetching ? '同步中…' : '↻ 刷新'}</button></nav>
    {data && view === 'overview' && <ProjectOverview data={data} onCommit={id => { setSelected(id); setView('history'); }} onBranch={name => { setBranch(name); setView('history'); }} />}
    {query.isPending && <p className="vt-message" role="status">正在读取 Git 版本树…</p>}
    {query.isError && <p className="vt-message" role="alert">{query.error.message} <button onClick={() => query.refetch()}>重试</button></p>}
    {data && view === 'history' && <><div className="vt-status"><span>{data.conflicted ? '存在合并冲突' : data.dirty ? `${data.changes.length} 个文件待提交` : '工作区已同步'}</span><span>{data.progress ? `${stages[data.progress.stage] ?? data.progress.stage} · ${data.progress.confirmed_versions} 个已确认版本 · ${data.progress.planned_cards} 张计划卡片 · ${data.progress.card_branches} 个卡片分支` : '尚未关联项目进度'}</span><span>{data.branches.length} 个本地分支 · {data.commits.length} 次提交</span></div>
      {!data.commits.length ? <p className="vt-message">还没有可展示的提交。</p> : <div className="vt-body">
        <div className="vt-history-list" ref={viewport} aria-label="项目提交历史">
          {[...data.commits].filter(commit => !ancestors || ancestors.has(commit.commit_id)).sort((a, b) => Date.parse(b.authored_at) - Date.parse(a.authored_at)).map(commit => <button key={commit.commit_id} className={`vt-history-row ${selected === commit.commit_id ? 'is-selected' : ''}`} aria-pressed={selected === commit.commit_id} onClick={() => setSelected(commit.commit_id)}>
            <span className="vt-history-dot"/><span className="vt-history-main"><b>{data.progress?.milestones[commit.commit_id] ?? commit.subject}</b><small>{new Date(commit.authored_at).toLocaleString('zh-CN')} · {commit.author}</small><span className="vt-history-refs">{commit.commit_id === data.version.commit_id && <em>当前位置</em>}{data.branches.filter(item => item.commit_id === commit.commit_id).map(item => <em key={item.name} title={item.name}>{data.progress?.branch_labels[item.name] ?? item.name}</em>)}</span></span><code>{commit.commit_id.slice(0, 7)}</code>
          </button>)}
        </div>
        {branchesOpen ? <aside className="vt-detail vt-branches"><button className="vt-close" aria-label="关闭分支面板" onClick={() => setBranchesOpen(false)}>×</button><small>分支管理</small><h3>本地分支</h3>
          {data.branches.map(item => <div className="vt-branch" key={item.name}><span><b>{item.name}</b><small>{item.commit_id.slice(0, 8)}</small></span>{item.current ? <em>当前</em> : <button disabled={branchBusy} onClick={() => void prepareBranch('switch', item.name)}>切换</button>}</div>)}
          <form onSubmit={event => { event.preventDefault(); if (newBranch.trim()) void prepareBranch('create', newBranch.trim()); }}><h3>新建分支</h3><label>分支名称<input value={newBranch} onChange={event => setNewBranch(event.target.value)} placeholder="例如 feature/level-map" /></label><small>起点：{(selected ?? data.version.commit_id).slice(0, 10)}{selected ? ' · 已选版本' : ' · 当前 HEAD'}</small><button disabled={branchBusy || !newBranch.trim()}>预览创建</button></form>
          {branchError && <p className="vt-branch-error" role="alert">{branchError}</p>}
          {branchPlan && <div className="vt-change-set"><small>分支操作预览</small><p>{branchPlan.operation === 'create' ? '创建并切换到' : '切换到'} <b>{branchPlan.branch_name}</b></p><p>起点 {branchPlan.source_commit.slice(0, 10)}</p>{branchPlan.blocked_reasons.map(reason => <p className="vt-branch-error" key={reason}>{blockedLabels[reason] ?? reason}</p>)}<div><button onClick={() => setBranchPlan(null)}>取消</button><button className="vt-primary" disabled={branchBusy || !!branchPlan.blocked_reasons.length} onClick={() => void applyBranch()}>确认执行</button></div></div>}
        </aside> : active && <aside className="vt-detail"><button className="vt-close" aria-label="关闭版本详情" onClick={() => setSelected(null)}>×</button><small>提交详情</small><h3>{active.subject}</h3><p>{active.author}</p><p>{new Date(active.authored_at).toLocaleString('zh-CN')}</p><code>{active.commit_id}</code><p>{active.parent_ids?.length && active.parent_ids.length > 1 ? '合并提交' : '普通提交'}</p><small>父提交</small>{active.parent_ids?.map(id => <button key={id} disabled={!data.commits.some(commit => commit.commit_id === id)} onClick={() => setSelected(id)}>{id.slice(0, 10)}</button>)}{active.commit_id === data.version.commit_id && <><p>当前位置 · {data.dirty ? '有待提交修改' : '工作区干净'}</p>{data.changes.map(change => <p key={change.path} className="vt-file">{change.path}</p>)}</>}<h3>变更文件{(active.parent_ids?.length ?? 0) > 1 ? ' · 相对第一父提交' : ''}</h3>{files.isPending && <p>正在读取…</p>}{files.isError && <p role="alert">{files.error.message}<button onClick={() => files.refetch()}>重试</button></p>}{files.data?.length === 0 && <p>无文件变化</p>}{files.data?.map(file => <p className="vt-file" key={file.path}>{file.path} <small>{({ added: '新增', modified: '修改', deleted: '删除', renamed: '重命名', conflict: '冲突', untracked: '未跟踪' })[file.kind]}</small></p>)}</aside>}
      </div>}
      <footer><span>按提交时间排列 · 点击查看文件变化</span><span>{data.commits.length} 次提交</span></footer>
    </>}
  </section>;
}
