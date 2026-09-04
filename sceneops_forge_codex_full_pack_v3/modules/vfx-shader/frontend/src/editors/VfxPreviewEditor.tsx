import React from 'react';
import type { VfxPreviewEditorProps } from '../types';

export default function VfxPreviewEditor({ state, onRetry, onPlanPreview }: VfxPreviewEditorProps) {
  if (state.kind !== 'ready') {
    const detail = state.kind === 'offline' ? 'Render 离线；仍可生成确定性 Mock 预览计划。' : state.kind === 'permission' ? `需要 ${state.requiredPermission}` : state.kind === 'failed' ? `${state.code} · ${state.message}` : `状态：${state.kind}`;
    return <section role={state.kind === 'failed' ? 'alert' : 'status'} data-state={state.kind}><h2>VFX 预览</h2><p>{detail}</p>{state.kind === 'failed' && <button onClick={onRetry}>重试</button>}{state.kind === 'empty' && <button onClick={onPlanPreview}>创建预览计划</button>}</section>;
  }
  const { preview } = state;
  return (
    <main data-state="ready" aria-label="VFX 确定性预览">
      <h2>预览计划</h2>
      <p>{preview.previewId} · {preview.mode.toUpperCase()}</p>
      <dl>
        <dt>质量档位</dt><dd>{preview.qualityTier}</dd>
        <dt>种子</dt><dd>{preview.seed}</dd>
        <dt>帧数</dt><dd>{preview.frameCount}</dd>
      </dl>
      <h3>渲染 Pass</h3><ol>{preview.passes.map((pass) => <li key={pass}>{pass}</li>)}</ol>
      {preview.warnings.length > 0 && <section role="alert"><h3>预算警告</h3><ul>{preview.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></section>}
    </main>
  );
}
