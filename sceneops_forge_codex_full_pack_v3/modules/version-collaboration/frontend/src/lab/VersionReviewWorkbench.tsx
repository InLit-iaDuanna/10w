import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { loadReview, reviewRequest } from "./client.ts";
import { DiffPanel, layerNames, type Layer } from "./DiffPanel.tsx";
import { ReviewSidebar } from "./ReviewSidebar.tsx";
import type { DemoEntry } from "../generated/api-types.ts";
import "./workbench.css";

const statusNames: Record<string, string> = { open: "评审中", changes_requested: "要求修改", approved: "已通过", closed: "已关闭" };
const outcomeNames: Record<string, string> = { accept: "接受变更", request_changes: "要求修改", block: "阻断评审", approved: "通过", rejected: "拒绝" };

function Workspace({ entry }: { entry: DemoEntry }) {
  const [layer, setLayer] = useState<Layer>("semantic");
  const [target, setTarget] = useState(entry.inputs.target_ids?.[0] ?? "");
  const [history, setHistory] = useState<"activity" | "approvals" | "decisions">("activity");
  const query = useQuery({ queryKey: ["version-review-lab", entry.review.review_id], queryFn: () => loadReview(entry.review.review_id) });
  if (query.isPending) return <div className="vr-loading" role="status">正在读取版本与评审记录…</div>;
  if (query.isError) return <div className="vr-error" role="alert">无法加载评审：{query.error.message}<button onClick={() => query.refetch()}>重试</button></div>;
  const data = query.data;
  const review = data.review;
  return <div className="vr-workspace"><main className="vr-main">
    <div className="vr-title"><div><p className="vr-eyebrow">VERSION REVIEW / 评审修订 {review.revision}</p><h1>{entry.label}</h1><p className="vr-muted">让每一次变更都有依据、讨论与可追溯的决定。</p></div><span className="vr-status">● {statusNames[review.status]}</span></div>
    <div className="vr-version-pair"><div><span>基线版本</span><code title={review.base_version.commit_id}>{review.base_version.commit_id.slice(0, 12)}</code></div><span>→</span><div><span>目标版本</span><code title={review.target_version.commit_id}>{review.target_version.commit_id.slice(0, 12)}</code></div><small>demo/review<br/>只读版本对 · MOCK</small></div>
    <nav className="vr-tabs" aria-label="差异层">{(Object.keys(layerNames) as Layer[]).map(key => <button key={key} aria-pressed={layer === key} onClick={() => setLayer(key)}>{layerNames[key]} <span>{key === "visual" ? review.diff.visual.changed_samples : review.diff[key].changes.length}</span></button>)}</nav>
    <DiffPanel entry={entry} review={review} layer={layer} selectTarget={setTarget} />
    <section className="vr-history"><div className="vr-section-title"><h2>评审记录</h2><button onClick={() => query.refetch()} disabled={query.isFetching}>刷新记录</button></div>
      <nav className="vr-tabs" aria-label="记录类型">{(["activity", "decisions", "approvals"] as const).map(key => <button key={key} aria-pressed={history === key} onClick={() => setHistory(key)}>{{ activity: "活动时间线", decisions: "决策历史", approvals: "审批历史" }[key]} · {data[key].length}</button>)}</nav>
      {history === "activity" && [...data.activity].reverse().map(item => <article className="vr-history-row" key={item.activity_id}><span className="vr-dot"/><div><p>{item.summary}</p><small>{item.actor_id} · {new Date(item.created_at).toLocaleString("zh-CN")}</small></div><span className="vr-badge">{item.mode.toUpperCase()}</span></article>)}
      {history === "decisions" && [...data.decisions].reverse().map(item => <article className="vr-history-row" key={item.decision_id}><span className="vr-dot"/><div><strong>{outcomeNames[item.outcome]}</strong><p>{item.rationale}</p><small>{item.actor_id} · {item.review_revision_id}</small></div><span className="vr-badge">MOCK</span></article>)}
      {history === "approvals" && [...data.approvals].reverse().map(item => <article className="vr-history-row" key={item.approval_id}><span className="vr-dot"/><div><strong>{outcomeNames[item.outcome]} · 修订 {item.subject_version}</strong><p>{item.rationale}</p><small>{item.approver_id} · {item.created_at}</small><small>绑定 {item.diff_bundle_id}</small><small>证据 {item.evidence_ids.join(" · ")}</small></div><span className="vr-badge">MOCK</span></article>)}
      {data[history].length === 0 && <p className="vr-empty">暂无记录。在右侧提交评审后，这里会显示完整历史。</p>}
    </section>
  </main><ReviewSidebar data={data} entry={entry} target={target} onTarget={setTarget} /></div>;
}

export function VersionReviewWorkbench() {
  const [selected, setSelected] = useState(0);
  const [filter, setFilter] = useState("");
  const catalog = useQuery({ queryKey: ["version-review-catalog"], queryFn: () => reviewRequest("GET /api/lab/catalog", {}, undefined) });
  return <div className="vr-app"><header className="vr-header"><a className="vr-brand" href="/">◈ <strong>SceneOps</strong><span>FORGE</span></a><span className="vr-header-path">工作台 / 09 版本评审</span><span className="vr-badge">本地独立运行</span></header>
    <div className="vr-banner"><span>◉ 隔离演示环境</span> Git / 审批为 MOCK；差异计算与评审存储在本地执行。重启清空会话，不访问真实仓库。</div>
    <div className="vr-layout"><aside className="vr-projects"><p className="vr-eyebrow">评审空间</p><h2>版本与变更</h2><input aria-label="搜索评审" placeholder="搜索项目或评审…" value={filter} onChange={event => setFilter(event.target.value)} />
      {catalog.data?.entries.map((entry, i) => entry.label.toLowerCase().includes(filter.toLowerCase()) && <button className="vr-project" key={entry.review.review_id} aria-pressed={selected === i} onClick={() => setSelected(i)}><span>0{i + 1} / 项目评审</span><strong>{entry.label}</strong><small>基线 → 目标 · 四层差异</small><span className="vr-badge">MOCK</span></button>)}
      {catalog.data && !catalog.data.entries.some(entry => entry.label.toLowerCase().includes(filter.toLowerCase())) && <p className="vr-muted">没有匹配的评审。</p>}
      <div className="vr-sidebar-foot"><span className="vr-good">● 本地服务</span><p>追加式审计记录<br/>不可变差异快照<br/>精确版本评论锚点</p><small>远程锁 / 回滚执行<br/>BLOCKED · 未连接</small></div>
    </aside>{catalog.isPending ? <p className="vr-loading" role="status">正在连接本地 API…</p> : catalog.isError ? <div className="vr-error" role="alert">API 连接失败：{catalog.error.message}<button onClick={() => catalog.refetch()}>重新连接</button></div> : catalog.data.entries[selected] && <Workspace key={catalog.data.entries[selected].review.review_id} entry={catalog.data.entries[selected]} />}</div>
  </div>;
}
