import { useState } from "react";
import { evidenceSamples, reviewExamples, goalLabels, type LocalReview, type ProposalDraft } from "./evidence.ts";
import { EvidenceViewport } from "./EvidenceViewport.tsx";
import { ReviewPanel } from "./ReviewPanel.tsx";
import "./workbench.css";

// Model IDs advertised by the locally installed `codebuddy --help` on 2026-09-05.
// This is a CLI capability snapshot, not a check of account access.
const codebuddyModels = ["hy4-preview", "hy3", "hy3-x", "glm-5.3", "glm-5.3-flash", "glm-5.2", "glm-5.1", "glm-5v-turbo", "minimax-m3", "minimax-m2.7", "kimi-k3-1", "kimi-k2.7", "kimi-k2.6", "deepseek-v4-pro", "deepseek-v4-flash"];
type ConfigurationDraft = { seed: number; maxSteps: number; objective: string; aiProvider: "codebuddy-cli"; aiModel: string };

export function AIPlaytestWorkbench() {
  const [sampleId, setSampleId] = useState(evidenceSamples[0].id);
  const [frameIndex, setFrameIndex] = useState(0);
  const [issueId, setIssueId] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [mode, setMode] = useState("mock");
  const [tab, setTab] = useState("evidence");
  const [notice, setNotice] = useState("");
  const [reviews, setReviews] = useState<Record<string, LocalReview>>({});
  const [proposals, setProposals] = useState<Record<string, ProposalDraft>>({});
  const [drafts, setDrafts] = useState<Record<string, ConfigurationDraft>>({});
  const sample = evidenceSamples.find(item => item.id === sampleId)!;
  const frame = sample.fixture.frames[frameIndex];
  const issues = reviewExamples.filter(item => item.sampleId === sampleId);
  const issue = issues.find(item => item.id === issueId);
  const draft: ConfigurationDraft = drafts[sample.testCase.test_case_id] ?? { seed: sample.testCase.seed, maxSteps: sample.testCase.controls.max_steps, objective: sample.testCase.objective, aiProvider: "codebuddy-cli", aiModel: "" };
  function selectSample(id: string) { setSampleId(id); setFrameIndex(0); setIssueId(null); setNotice(""); }
  function locateIssue(id: string) {
    const selected = issues.find(item => item.id === id)!;
    setIssueId(id); setFrameIndex(selected.frame); setTab("evidence");
    setNotice(`已定位到观察 ${selected.frame + 1}；仅切换本地 Mock 视图。`);
  }
  return <div className="ap-workbench">
    <header className="ap-topbar"><div className="ap-brand">S<span>↗</span></div><div><small>SCENEOPS FORGE / WORKBENCH 10</small><h1>AI 测试与问题定位</h1></div><span className="ap-top-spacer"/><span className="ap-badge">MOCK · 本地证据</span><span className="ap-connection">● Unity 未连接</span></header>
    <div className="ap-banner"><span>证据审阅模式</span>查看静态场景样例，定位问题并整理修复建议。AI 测试仅辅助预筛，不能替代真人测试。</div>
    <div className="ap-layout">
      <aside className="ap-sidebar">
        <div className="ap-section-title"><h2>场景与构建</h2><small>03</small></div>
        <label>查找样例<input type="search" placeholder="项目、场景、构建…" value={filter} onChange={e => setFilter(e.target.value)} /></label>
        <label>证据来源<select value={mode} onChange={e => setMode(e.target.value)}><option value="mock">Mock · 模拟样例</option><option value="live">Live · 当前真实运行</option><option value="cached">Cached · 真实历史运行</option></select></label>
        {mode === "mock" ? <div className="ap-sample-list">{evidenceSamples.filter(item => `${item.title} ${item.project} ${item.fixture.build.build_id}`.toLowerCase().includes(filter.toLowerCase())).map(item => <button key={item.id} className={item.id === sampleId ? "selected" : ""} onClick={() => selectSample(item.id)}><small>{item.project}</small><strong>{item.title}</strong><code>{item.fixture.build.version}</code></button>)}
          {!evidenceSamples.some(item => `${item.title} ${item.project} ${item.fixture.build.build_id}`.toLowerCase().includes(filter.toLowerCase())) && <p>没有匹配样例，请调整搜索词。</p>}</div>
          : <div className="ap-notice"><strong>{mode === "live" ? "BLOCKED · 没有运行连接" : "PLANNED · 没有真实历史证据"}</strong><p>当前只能浏览明确标记的模拟数据。</p><button onClick={() => setMode("mock")}>返回 Mock 样例</button></div>}
        <div className="ap-sidebar-footer"><small>执行功能</small><button disabled>启动 AI 测试 · 未开放</button><p>不会启动 Unity、AI runner 或后台测试。切换样例只读取已附带的静态数据。</p></div>
      </aside>
      <main className="ap-main">
        <div className="ap-context"><div><small>{sample.project}</small><h2>{sample.title}</h2><code>{sample.fixture.build.build_id}</code></div><span className="ap-badge">MOCK</span></div>
        <nav className="ap-tabs" aria-label="工作台工具"><button aria-selected={tab === "evidence"} onClick={() => setTab("evidence")}>运行证据</button><button aria-selected={tab === "configuration"} onClick={() => setTab("configuration")}>场景配置</button><button aria-selected={tab === "provenance"} onClick={() => setTab("provenance")}>来源与限制</button></nav>
        {notice && <div className="ap-notice" role="status">{notice}</div>}
        {tab === "evidence" && <><EvidenceViewport sample={sample} selected={frameIndex} onSelect={setFrameIndex}/>
          <div className="ap-observation"><div><small>观察时间 · UTC</small><strong>{frame.observed_at}</strong></div><div><small>样例目标进度</small><strong>{Math.round(frame.goals[0].value * 100)}% · {goalLabels[frame.goals[0].state]}</strong></div><div><small>帧耗时 / 内存 · 模拟值</small><strong>{frame.frame_time_ms} ms / {frame.memory_mb} MB</strong></div></div>
          <div className="ap-section-title"><h2>行为时间线</h2><small>静态观察，不是本次执行日志</small></div>
          <div className="ap-timeline">{sample.fixture.frames.map((item, index) => <button key={index} aria-pressed={index === frameIndex} onClick={() => setFrameIndex(index)}><span className="ap-step-number">{String(index + 1).padStart(2, "0")}</span><span><strong>{item.goals[0].detail}</strong><small>{item.observed_at.slice(11,19)} · {item.position_m.join(", ")} m</small></span><span>{Math.round(item.goals[0].value * 100)}%</span></button>)}</div>
          <details className="ap-raw"><summary>当前观察：可用动作、配置结果与游戏状态</summary><pre>{JSON.stringify({ game_state: frame.game_state, actions: frame.actions, configured_results: frame.results }, null, 2)}</pre></details></>}
        {tab === "configuration" && <section className="ap-config"><h3>测试配置草稿 <span className="ap-badge planned">PLANNED</span></h3><p>草稿仅保存在本页。修改不会改变原始证据或启动测试。</p><form onSubmit={event => { event.preventDefault(); setNotice("配置草稿已保存到当前页面；尚未提交测试。"); }}>
          <label>AI 接入方式<input readOnly value="CodeBuddy CLI" /></label>
          <label>AI 模型<select value={draft.aiModel} onChange={e => setDrafts({ ...drafts, [sample.testCase.test_case_id]: { ...draft, aiModel: e.target.value } })} aria-describedby="ap-model-help"><option value="">使用 CodeBuddy CLI 默认模型</option>{codebuddyModels.map(model => <option key={model} value={model}>{model}</option>)}</select></label>
          <p id="ap-model-help">模型列表来自本机 CodeBuddy CLI 帮助（2026-09-05），账号可用性尚未验证。当前仅保存选择；CLI 执行尚未接通，不会发起 AI 调用。</p>
          <label>目标<textarea required value={draft.objective} onChange={e => setDrafts({ ...drafts, [sample.testCase.test_case_id]: { ...draft, objective: e.target.value } })}/></label>
          <label>随机种子<input type="number" step="1" required value={draft.seed} onChange={e => setDrafts({ ...drafts, [sample.testCase.test_case_id]: { ...draft, seed: e.target.valueAsNumber } })}/></label>
          <label>最大步数<input type="number" min="1" max="10000" step="1" required value={draft.maxSteps} onChange={e => setDrafts({ ...drafts, [sample.testCase.test_case_id]: { ...draft, maxSteps: e.target.valueAsNumber } })}/></label>
          <p>原始模式：{sample.testCase.agent_mode} · 动作上限 {sample.testCase.controls.action_timeout_ms} ms · 总时限 {sample.testCase.controls.max_duration_ms} ms</p><button className="primary">保存本地配置草稿</button></form>
          <details><summary>原始 TestCase</summary><pre>{JSON.stringify(sample.testCase, null, 2)}</pre></details></section>}
        {tab === "provenance" && <section className="ap-config"><h3>证据来源</h3><dl><dt>Fixture</dt><dd>{sample.filename}</dd><dt>场景</dt><dd>{sample.fixture.build.scene_id}</dd><dt>Actor</dt><dd>{sample.fixture.actor_sceneops_id}</dd><dt>Adapter</dt><dd>{sample.fixture.adapter.adapter_id} @ {sample.fixture.adapter.adapter_version}</dd></dl><p>这些帧与问题卡是可重复展示的模拟样例，不是成功执行 runner 后导出的 PlaytestRun。没有真实截图、运行测量或已验证的修复结论。</p><p>Live：Blocked；Cached：Planned；源代码写回与 ChangeSet 派发：Planned。当前提案是浏览器内草稿，真实操作仍须经过模块服务与审批。</p></section>}
      </main>
      <aside className="ap-inspector"><div className="ap-section-title"><h2>问题样例</h2><small>{issues.length} 项</small></div><p className="ap-muted">选择问题，将同步定位到对应观察。</p>
        {issues.map(item => <button key={item.id} className={`ap-issue ${item.id === issueId ? "selected" : ""}`} onClick={() => locateIssue(item.id)}><span>{item.severity === "error" ? "!" : "△"}</span><strong>{item.title}</strong><small>{reviews[item.id] ? (reviews[item.id].decision === "confirmed" ? "已模拟确认" : "已模拟拒绝") : "待审阅"} · 观察 {item.frame + 1}</small></button>)}
        {!issues.length && <div className="ap-notice">此样例没有附带问题卡；这不等同于已经通过测试。</div>}
        {issue ? <ReviewPanel key={issue.id} issue={issue} review={reviews[issue.id]} proposal={proposals[issue.id]} onReview={value => setReviews({ ...reviews, [issue.id]: value })} onProposal={value => setProposals({ ...proposals, [issue.id]: value })}/> : <div className="ap-empty"><span>⌖</span><h3>从证据找到源头</h3><p>选择一条问题，查看源对象、匹配依据和修复提案入口。</p></div>}
      </aside>
    </div>
    <footer className="ap-footer"><span>MOCK · 当前页面隔离数据</span><span>{Object.keys(reviews).length} 条模拟审阅 · {Object.keys(proposals).length} 份提案草稿</span><span>刷新清空本地草稿 · 外部执行未开放</span></footer>
  </div>;
}
