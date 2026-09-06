import { useState, type ReactNode } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { agentTasks } from './client';
import { productionApi, productionKeys, useProduction, type ProductionArtifact } from './production-client';
import './production.css';

export const productionStateLabels: Record<string, string> = {
  planned: '待执行', running: '执行中', blocked: '受阻', failed: '失败', cancelled: '已停止',
  review_required: '产物待审阅', completed: '执行结束', awaiting_authorization: '等待主对话授权',
  needs_approval: '需要补充授权', interrupted: '已中断', queued: '等待执行', cancel_pending: '正在取消，尚未确认停止',
};
export type ProductionSelection = { projectId: string; taskId?: string; artifactId?: string; moduleId: string };
const verificationLabels: Record<string, string> = { passed: '此版本检查通过', failed: '此版本检查失败',
  inconclusive: '证据不完整，不能判定', reported: 'Agent 报告，尚未验证', unverified: '未验证' };

export function ProductionModuleView({ projectId, moduleId, onDiscuss, renderModel }: {
  projectId: string | null; moduleId: string; onDiscuss: (selection: ProductionSelection) => void;
  renderModel?: (artifact: ProductionArtifact, url: string) => ReactNode;
}) {
  const query = useProduction(projectId);
  const cache = useQueryClient();
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null);
  const stop = useMutation({ mutationFn: agentTasks.cancel,
    onSuccess: () => cache.invalidateQueries({ queryKey: productionKeys.snapshot(projectId) }) });
  if (!projectId) return <section className="production-module-view"><p>尚未选择项目。请在主对话描述目标，创建任务后这里会显示本环节状态与产物。</p>
    <button onClick={() => onDiscuss({ projectId: '', moduleId })}>回到主对话</button></section>;
  if (query.isPending) return <p role="status">读取生产状态…</p>;
  if (query.error) return <p role="alert">{query.error.message} <button onClick={() => void query.refetch()}>重新读取</button></p>;
  const steps = query.data?.steps.filter(step => step.module_id === moduleId) ?? [];
  const artifacts = query.data?.artifacts.filter(artifact => artifact.module_id === moduleId) ?? [];
  const module = query.data?.modules.find(item => item.id === moduleId);
  const active = steps.find(step => step.state === 'running') ?? steps.at(-1);
  const task = query.data?.tasks.find(task => task.id === active?.task_id);
  const artifact = artifacts.find(item => `${item.id}:${item.version}` === selectedArtifact) ?? artifacts.at(-1);
  return <section className="production-module-view" aria-label="模块生产状态">
    <header><strong>{active ? productionStateLabels[active.state] : '尚无执行记录'}</strong>
      <span role="status">{query.connectionState === 'connected' ? '实时同步' : '连接断开 · 保留最后状态'}</span></header>
    {module?.readiness_notice && <p className="production-notice">{module.readiness_notice}</p>}
    {task && <p className="production-task-goal">{task.goal}</p>}
    <div className="production-controls"><button onClick={() => onDiscuss({ projectId, moduleId,
      ...(task ? { taskId: task.id } : {}), ...(artifact ? { artifactId: artifact.id } : {}) })}>在主对话讨论 / 审批</button>
      {task && ['queued', 'running', 'blocked'].includes(task.status) && <button disabled={stop.isPending} onClick={() => stop.mutate(task.id)}>停止此任务</button>}</div>
    {stop.error && <p role="alert">{stop.error.message}</p>}
    <ol className="production-steps">{steps.map(step => <li key={step.id} data-state={step.state}>
      <header><strong>{step.title}</strong><span>{productionStateLabels[step.state]}</span></header>
      <small>{step.mode} · {verificationLabels[step.verification]} · {new Date(step.updated_at).toLocaleTimeString()}</small>
      {step.verification_result && <p>版本 {step.verification_result.project_revision} · {step.verification_result.verdict} · {step.verification_result.suite_id} v{step.verification_result.suite_version}</p>}
      {step.dependencies.length > 0 && <p>前置步骤：{step.dependencies.join('、')}</p>}
      {step.reason && <p>{step.reason}</p>}
    </li>)}</ol>
    {!steps.length && <p className="production-empty">此项目尚未执行本环节。任务开始后显示真实步骤，不模拟进度。</p>}
    <section className="production-artifacts" aria-label="本模块产物"><h3>产物与版本</h3>
      {!artifacts.length ? <p>暂无已登记产物。</p> : <>
        <select aria-label="选择产物版本" value={artifact ? `${artifact.id}:${artifact.version}` : ''} onChange={event => setSelectedArtifact(event.target.value)}>
          {artifacts.map(item => <option key={`${item.id}:${item.version}`} value={`${item.id}:${item.version}`}>{item.name} · v{item.version}</option>)}
        </select>
        {artifact && <ArtifactPreview artifact={artifact} {...(renderModel ? { renderModel } : {})} />}
      </>}
    </section>
    <details><summary>执行标识与诊断</summary><pre>{JSON.stringify({ task_id: task?.id, steps: steps.map(step => ({ id: step.id, run_id: step.run_id, capability: step.capability_id })) }, null, 2)}</pre></details>
  </section>;
}

function ArtifactPreview({ artifact, renderModel }: { artifact: ProductionArtifact; renderModel?: (artifact: ProductionArtifact, url: string) => ReactNode }) {
  const url = productionApi.artifactUrl(artifact);
  return <div className="production-artifact-preview">
    {artifact.kind === 'image' && <img src={url} alt={artifact.name} loading="lazy" />}
    {artifact.kind === 'audio' && <audio controls preload="none" src={url} />}
    {artifact.kind === 'model' && renderModel?.(artifact, url)}
    <p>{artifact.name} · v{artifact.version} · {artifact.mode} · {artifact.verification === 'passed' ? '检查通过' : '产物已存在，业务效果待验收'}</p>
    <a href={url} download={artifact.name}>打开 / 下载实际文件</a>
  </div>;
}

export function ProductionNodeStatus({ projectId, moduleId }: { projectId: string | null; moduleId: string }) {
  const query = useProduction(projectId);
  const steps = query.data?.steps.filter(step => step.module_id === moduleId) ?? [];
  const active = steps.find(step => step.state === 'running') ?? steps.at(-1);
  if (!active) return <small className="production-node-status">未执行</small>;
  return <small className="production-node-status" data-state={active.state}>{productionStateLabels[active.state]}</small>;
}
