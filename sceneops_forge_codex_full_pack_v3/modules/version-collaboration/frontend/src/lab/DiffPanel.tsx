import type { DemoEntry, ReviewSession, VisualCapture } from "../generated/api-types.ts";

export type Layer = "file" | "semantic" | "visual" | "behavior";
export const layerNames: Record<Layer, string> = { file: "文件差异", semantic: "语义差异", visual: "视觉差异", behavior: "行为差异" };
const value = (item: unknown) => item === undefined ? "—" : JSON.stringify(item, null, 2);

function Capture({ capture, title }: { capture: VisualCapture; title: string }) {
  return <figure className="vr-capture"><figcaption>{title}<span>{capture.width} × {capture.height} · 原始灰度样本</span></figcaption>
    <svg viewBox={`0 0 ${capture.width} ${capture.height}`} role="img" aria-label={`${title}固定相机样本`}>
      {capture.pixels.map((pixel, i) => <rect key={i} x={i % capture.width} y={Math.floor(i / capture.width)} width="1" height="1" fill={`rgb(${pixel},${pixel},${pixel})`} />)}
    </svg><code>[{capture.pixels.join(", ")}]</code><small>{capture.artifact_id}</small></figure>;
}

export function DiffPanel({ entry, review, layer, selectTarget }: {
  entry: DemoEntry; review: ReviewSession; layer: Layer; selectTarget: (id: string) => void;
}) {
  const diff = review.diff;
  return <section className="vr-diff" aria-label={layerNames[layer]}>
    <div className="vr-section-title"><h2>{layerNames[layer]}</h2><span className="vr-badge">MOCK 输入 · 本地计算</span></div>
    {diff[layer].failure_reason && <p role="alert" className="vr-error">{diff[layer].failure_reason}</p>}
    {layer === "file" && <>
      <p className="vr-muted">固定版本间的文件统计。演示仓库不提供源文件行级补丁，也不会读取主仓库。</p>
      <div className="vr-table-wrap"><table><thead><tr><th>文件路径</th><th>变更类型</th><th>新增</th><th>删除</th></tr></thead><tbody>
        {diff.file.changes.map(file => <tr key={file.path}><td><code>{file.path}</code></td><td>{file.kind === "modified" ? "修改" : file.kind}</td><td className="vr-good">+{file.additions ?? "—"}</td><td className="vr-bad">−{file.deletions ?? "—"}</td></tr>)}
      </tbody></table></div>
      <h3>二进制资源与 LFS</h3>
      {diff.file.lfs_pointers.map(pointer => <div className="vr-resource" key={pointer.path}><span>◈</span><div><code>{pointer.path}</code><p>{pointer.size} bytes · {pointer.object_available ? "对象可用" : "仅指针，未下载对象"}</p></div><span className="vr-badge">{pointer.lock_required ? "需要锁定" : "无需锁定"}</span></div>)}
      <div className="vr-note">远程锁、自动提交、合并和回滚执行均未连接。这里的评审不会改变 Git 工作区。</div>
    </>}
    {layer === "semantic" && <>
      <p className="vr-muted">按稳定对象 ID 比较结构化属性。点击对象，将评论锚定到它。</p>
      <table><thead><tr><th>对象 / 属性</th><th>基线</th><th>目标</th></tr></thead><tbody>
        {diff.semantic.changes.map((change, i) => <tr key={i}><td><button className="vr-link" onClick={() => selectTarget(change.entity_id)}>{change.entity_id}</button><small>{change.path || "整个对象"}</small></td><td><pre>{value(change.before)}</pre></td><td className="vr-good"><pre>{value(change.after)}</pre></td></tr>)}
      </tbody></table>
    </>}
    {layer === "visual" && <>
      <p className="vr-muted">固定相机 · {diff.visual.camera_id}。以下为真实 fixture 像素放大显示，不是 Unity 渲染截图。</p>
      <div className="vr-pair">{entry.inputs.visual_before && <Capture capture={entry.inputs.visual_before} title="基线 / BEFORE" />}{entry.inputs.visual_after && <Capture capture={entry.inputs.visual_after} title="目标 / AFTER" />}</div>
      <div className="vr-metrics"><div><strong>{diff.visual.changed_samples} / {diff.visual.sample_count}</strong><span>变化样本</span></div><div><strong>{diff.visual.mean_absolute_error}</strong><span>平均绝对误差</span></div><div><strong>{diff.visual.maximum_absolute_error}</strong><span>最大绝对误差</span></div></div>
    </>}
    {layer === "behavior" && <>
      <p className="vr-muted">同一测试协议、配置、起始状态与随机种子。结果来自预置记录，未运行游戏或 Playtest。</p>
      <div className="vr-pair">{([entry.inputs.behavior_before, entry.inputs.behavior_after]).map((run, i) => run && <article className="vr-run" key={run.run_id}><span>{i ? "目标 / AFTER" : "基线 / BEFORE"}</span><h3 className={run.objective_succeeded ? "vr-good" : "vr-bad"}>{run.objective_succeeded ? "目标完成" : "目标未完成"}</h3><small>种子 {run.seed} · {run.protocol_version}</small>{run.steps.map(step => <div className="vr-step" key={step.step_id}><code>{step.action_id}</code><p>{step.outcome}</p><progress max="1" value={step.goal_progress} /></div>)}</article>)}</div>
      <h3>计算出的行为变更</h3><table><thead><tr><th>指标</th><th>基线</th><th>目标</th></tr></thead><tbody>{diff.behavior.changes.map((change, i) => <tr key={i}><td>{change.key}<small>{change.category}</small></td><td><pre>{value(change.before)}</pre></td><td><pre>{value(change.after)}</pre></td></tr>)}</tbody></table>
    </>}
    {diff.conflicts.length > 0 && <section className="vr-conflicts"><h3>评审提示 · {diff.conflicts.length}</h3>{diff.conflicts.map((conflict, i) => <p key={i}><span className="vr-badge">{conflict.blocking ? "阻断" : "提示"}</span> {conflict.message}</p>)}</section>}
  </section>;
}
