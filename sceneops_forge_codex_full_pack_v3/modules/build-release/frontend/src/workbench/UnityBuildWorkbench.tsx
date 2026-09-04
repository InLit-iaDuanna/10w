import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  workbenchApi,
  workbenchKeys,
  type Scenario,
  type Snapshot,
  type ProposalInput,
  type ChangeSet,
} from "./client";
import "./workbench.css";
const labels: Record<string, string> = {
  development: "开发",
  qa: "质量检查",
  judge: "演示",
  release_candidate: "发布候选",
  succeeded: "已完成",
  waiting_approval: "等待审批",
  blocked: "受阻",
  pending_approval: "等待审批",
};
const show = (value: string) => labels[value] || value;
function Badge({ mode }: { mode: string }) {
  return <span className={`badge ${mode}`}>{mode}</span>;
}
function Json({
  value,
  title = "完整记录",
}: {
  value: unknown;
  title?: string;
}) {
  return (
    <details>
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
function download(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
export function UnityBuildWorkbench() {
  const query = useQuery({
    queryKey: workbenchKeys.snapshot,
    queryFn: workbenchApi.snapshot,
  });
  const [slug, setSlug] = useState("remember-home");
  const [tab, setTab] = useState("build");
  if (query.isPending)
    return (
      <main className="ub">
        <p role="status">正在读取本地工作台…</p>
      </main>
    );
  if (query.isError)
    return (
      <main className="ub">
        <h1>本地 API 未连接</h1>
        <p role="alert">{query.error.message}</p>
        <p>请从工作台目录启动 dev；检查 8317 端口日志。Unity 无需启动。</p>
        <button onClick={() => query.refetch()}>重试连接</button>
      </main>
    );
  const snapshot = query.data;
  const scenario = snapshot.scenarios.find((s) => s.slug === slug);
  if (!scenario)
    return (
      <main className="ub">
        <h1>没有构建记录</h1>
        <button onClick={() => query.refetch()}>刷新</button>
      </main>
    );
  return (
    <main className="ub">
      <header>
        <div>
          <small>SCENEOPS FORGE / 工作台 08</small>
          <h1>Unity 与构建发布</h1>
        </div>
        <div>
          <Badge mode="mock" /> 隔离演示{" "}
          <button onClick={() => query.refetch()} disabled={query.isFetching}>
            刷新记录
          </button>
        </div>
      </header>
      <div className="notice">
        <Badge mode="blocked" /> Unity 未连接 · 构建 / 测试 /
        发布未执行。可浏览完整演示证据、编辑并保存本地提案。
      </div>
      <div className="toolbar">
        <label>
          示例项目{" "}
          <select value={slug} onChange={(e) => setSlug(e.target.value)}>
            <option value="remember-home">Remember Home · 钥匙与家门</option>
            <option value="warehouse-escape">
              Warehouse Escape · 仓库逃脱
            </option>
          </select>
        </label>
        <span>来源记录 2026-09-04 · 无 live / cached 证据</span>
      </div>
      <nav aria-label="工作台工具">
        {[
          ["build", "构建矩阵与产物"],
          ["unity", "Unity 能力与命令"],
          ["release", "候选与发布提案"],
        ].map(([id, title]) => (
          <button
            aria-current={tab === id ? "page" : undefined}
            onClick={() => setTab(id)}
            key={id}
          >
            {title}
          </button>
        ))}
      </nav>
      {tab === "build" ? (
        <Builds scenario={scenario} />
      ) : tab === "unity" ? (
        <Unity snapshot={snapshot} />
      ) : (
        <Release
          key={slug + ":" + scenario.proposal.revision}
          scenario={scenario}
        />
      )}
      <footer>
        本地草稿保存在此工作台 SQLite 中；mock
        构建记录不是可玩程序。真实外部操作需要可信审批与后续明确授权。
      </footer>
    </main>
  );
}
function Builds({ scenario: s }: { scenario: Scenario }) {
  const [runId, setRunId] = useState("");
  const run = s.runs.find((r) => r.build_run_id === runId) || s.runs[0];
  const manifest = s.manifests.find((m) => m.manifest_id === run.manifest_id)!;
  return (
    <>
      <section>
        <div className="section-title">
          <h2>BuildMatrix</h2>
          <Badge mode="mock" />
        </div>
        <p className="muted">
          {s.matrix.matrix_id} · source commit{" "}
          <code>{s.matrix.source_commit}</code>
        </p>
        <table>
          <thead>
            <tr>
              <th>配置</th>
              <th>平台 / 架构</th>
              <th>运行状态</th>
              <th>执行模式</th>
            </tr>
          </thead>
          <tbody>
            {s.matrix.targets.map((t) => (
              <tr key={t.target_id}>
                <td>{show(t.profile)}</td>
                <td>
                  {t.platform} / {t.architecture}
                </td>
                <td>{t.profile === "qa" ? "两条静态 A/B 记录" : "尚未执行"}</td>
                <td>
                  <Badge mode={t.profile === "qa" ? "mock" : "planned"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Json value={s.matrix} title="检查矩阵设置与目标 ID" />
      </section>
      <div className="columns">
        <section>
          <h2>构建记录</h2>
          <p>选择 A / B 查看来源链、产物和证据。</p>
          {s.runs.map((r) => (
            <button
              className={`run ${run.build_run_id === r.build_run_id ? "selected" : ""}`}
              key={r.build_run_id}
              onClick={() => setRunId(r.build_run_id)}
            >
              <strong>{r.build_run_id}</strong>
              <span>
                {show(r.status)} · attempt {r.attempt} <Badge mode={r.mode} />
              </span>
            </button>
          ))}
          <div className="notice">
            记录回放 · 固定完成进度 100%，未启动任何任务。
          </div>
          <progress value={100} max={100} />
          <ol className="steps">
            <li>
              输入与目标已记录 <Badge mode="mock" />
            </li>
            <li>
              模拟构建已完成 <Badge mode="mock" />
            </li>
            <li>
              模拟证据已归档 <Badge mode="mock" />
            </li>
          </ol>
          <p className="muted">
            {run.started_at} → {run.finished_at}
          </p>
          <Json value={run} title="构建运行记录" />
        </section>
        <section>
          <h2>产物与追溯</h2>
          <p>
            Unity {manifest.unity_version} · {manifest.build_recipe_version}
          </p>
          {manifest.artifacts.map((a) => (
            <article key={a.artifact_id}>
              <h3>
                {a.artifact_id} <Badge mode={a.mode} />
              </h3>
              <p>
                <code>{a.uri}</code>
              </p>
              <p>{a.size_bytes} bytes（fixture 元数据） · 不可下载为游戏</p>
              <Json value={a} title="产物版本、checksum 与 provenance" />
            </article>
          ))}
          <button
            onClick={() =>
              download(manifest, manifest.manifest_id + ".mock.json")
            }
          >
            导出 mock 清单 JSON
          </button>
          <Json
            value={manifest}
            title="完整构建清单（资产、场景、包、测试证据）"
          />
        </section>
      </div>
    </>
  );
}
function Unity({ snapshot }: { snapshot: Snapshot }) {
  const u = snapshot.unity;
  const [filter, setFilter] = useState("");
  return (
    <>
      <section>
        <h2>
          连接与包能力 <Badge mode={u.connection_mode} />
        </h2>
        <p>{u.connection_reason}</p>
        <p>
          已集成包 <code>com.sceneops.forge.unity 0.1.0</code> · 固定 Editor{" "}
          {u.capabilities.pinned_unity_version}
        </p>
        <p>
          支持 dry-run、取消、重试；任意 C# 执行关闭。此入口仅开放本地提案预览。
        </p>
        <Json value={u.capabilities} title="完整能力报告" />
      </section>
      <div className="columns">
        <section>
          <h2>
            对象 / 身份链 <Badge mode="mock" />
          </h2>
          <p>
            以下为原 Unity fixture
            中的示例钥匙，与真实场景及上方构建项目选择无关。
          </p>
          {u.objects.map((o, i) => (
            <Json
              key={i}
              value={o}
              title="sobj_home_key · sinst_home_key_a · 组件与引用"
            />
          ))}
        </section>
        <section>
          <h2>
            命令记录 <Badge mode="mock" />
          </h2>
          <label>
            筛选命令{" "}
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="例如 build / inspect"
            />
          </label>
          <p>原始静态 fixture；没有在本轮调用命令。</p>
          {u.commands
            .filter((c) => String(c.command).includes(filter))
            .map((c, i) => (
              <Json key={i} value={c} title={String(c.command) + " · mock"} />
            ))}
        </section>
      </div>
    </>
  );
}
function Release({ scenario: s }: { scenario: Scenario }) {
  const client = useQueryClient();
  const p = s.proposal;
  const [title, setTitle] = useState(p.title),
    [notes, setNotes] = useState(p.notes),
    [target, setTarget] = useState<ProposalInput["target"]>(p.target),
    [json, setJson] = useState(JSON.stringify(p.change_set, null, 2));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: (body: ProposalInput) => workbenchApi.save(s.slug, body),
    onSuccess: () => {
      setSaved(true);
      client.invalidateQueries({ queryKey: workbenchKeys.snapshot });
    },
  });
  const preview = useMutation({ mutationFn: workbenchApi.preview });
  const action = (kind: "save" | "preview" | "export") => {
    setError("");
    try {
      const change = JSON.parse(json) as ChangeSet;
      if (kind === "export") {
        download(
          {
            title,
            notes,
            target,
            change_set: change,
            mode: "planned",
            approval_state: "pending",
          },
          s.slug + ".proposal.json",
        );
        return;
      }
      if (kind === "preview") preview.mutate(change);
      else
        save.mutate({
          expected_revision: p.revision,
          title,
          notes,
          target,
          change_set: change,
        });
    } catch (e) {
      setError("ChangeSet JSON 格式错误：" + String(e));
    }
  };
  return (
    <>
      <section>
        <h2>
          ReleaseCandidate <Badge mode={s.candidate.mode} />
        </h2>
        <p>
          <code>{s.candidate.candidate_id}</code> · {show(s.candidate.status)}
        </p>
        <div className="facts">
          <span>
            A/B 输入一致：
            {s.candidate.reproducibility.inputs_match ? "是" : "否"}
          </span>
          <span>
            输出一致：{s.candidate.reproducibility.outputs_match ? "是" : "否"}
          </span>
          <span>
            可信审批：{s.candidate.approvals.length} /{" "}
            {s.candidate.required_approval_roles.join(", ")}
          </span>
        </div>
        <p>此判断只基于 mock 记录。没有真实构建验证，也没有发布权限。</p>
        {s.candidate.blockers.map((b) => (
          <p role="status" key={b}>
            {b}
          </p>
        ))}
        <Json value={s.candidate} title="完整候选与审批要求" />
        <div className="gates">
          {s.gates.map((g) => (
            <details key={g.gate_id}>
              <summary>
                {g.category} · {g.status} <Badge mode={g.mode} />
              </summary>
              <pre>{JSON.stringify(g, null, 2)}</pre>
            </details>
          ))}
        </div>
      </section>
      <section>
        <div className="section-title">
          <h2>本地发布提案</h2>
          <span>
            <Badge mode="planned" /> revision {p.revision} · pending
          </span>
        </div>
        <p>
          保存会校验 ChangeSet、命令白名单与 base
          version，并持久保存草稿。不会批准、构建或发布。
        </p>
        {p.revision > 0 && (
          <p role="status" className="success">
            已保存的本地草稿 · {p.updated_at}
          </p>
        )}
        <div className="form-row">
          <label>
            标题
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={160}
            />
          </label>
          <label>
            拟发布目标
            <select
              value={target}
              onChange={(e) =>
                setTarget(e.target.value as ProposalInput["target"])
              }
            >
              <option value="local">本地 local</option>
              <option value="judge">演示 judge</option>
            </select>
          </label>
        </div>
        <label>
          发布说明
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            maxLength={4000}
          />
        </label>
        <label>
          ChangeSet · 可编辑完整字段
          <textarea
            className="code-editor"
            value={json}
            onChange={(e) => setJson(e.target.value)}
            rows={18}
            spellCheck={false}
          />
        </label>
        <p className="muted">
          示例 ChangeSet 针对 Unity fixture
          钥匙；属于独立待审提案，未计入上述候选的已批准变更。
        </p>
        <div className="actions">
          <button
            onClick={() => action("preview")}
            disabled={preview.isPending}
          >
            仅预览 ChangeSet
          </button>
          <button
            className="primary"
            onClick={() => action("save")}
            disabled={save.isPending}
          >
            {save.isPending ? "保存中…" : "保存本地提案"}
          </button>
          <button onClick={() => action("export")}>导出提案</button>
          <button disabled title="尚未配置可信审批和外部适配器">
            发布 / 部署 · blocked
          </button>
        </div>
        {(error || save.error || preview.error) && (
          <p role="alert" className="error">
            {error || save.error?.message || preview.error?.message}
          </p>
        )}
        {saved && <p role="status">已保存</p>}
        {preview.data && (
          <Json value={preview.data} title="预览成功 · planned（展开检查）" />
        )}
      </section>
    </>
  );
}
