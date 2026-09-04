import React from 'react';
import type { VfxParameterView, VfxShaderEditorProps } from '../types';

const panelStyle: React.CSSProperties = {
  height: '100%',
  boxSizing: 'border-box',
  background: 'var(--surface-1, #15181c)',
  color: 'var(--text-primary, #f1ece3)',
  padding: 16,
  fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
};

const statusText: Record<string, { icon: string; title: string }> = {
  loading: { icon: '◌', title: '正在加载 VFX Recipe…' },
  empty: { icon: '◇', title: '还没有 VFX Recipe' },
  failed: { icon: '⛔', title: 'VFX 加载失败' },
  offline: { icon: '↯', title: '集成当前离线' },
  permission: { icon: '◆', title: '没有访问权限' },
  disabled: { icon: '⊘', title: 'VFX/Shader 模块已停用' },
};

function StatusPanel({ state, onRetry, onCreateRecipe }: VfxShaderEditorProps) {
  const display = statusText[state.kind];
  let detail = '';
  if (state.kind === 'failed') detail = `${state.code} · ${state.message}`;
  if (state.kind === 'offline') detail = `${state.integration} 未连接；核心构建不受影响。`;
  if (state.kind === 'permission') detail = `需要 ${state.requiredPermission}`;
  if (state.kind === 'empty') detail = '创建 Recipe 后可编辑参数并生成 Mock 预览。';
  return (
    <section style={panelStyle} role={state.kind === 'failed' ? 'alert' : 'status'} data-state={state.kind}>
      <h2 style={{ fontSize: 15 }}><span aria-hidden>{display.icon}</span> {display.title}</h2>
      {detail && <p style={{ color: 'var(--text-secondary, #a5adb6)' }}>{detail}</p>}
      {state.kind === 'failed' && state.retryable && <button onClick={onRetry}>重试</button>}
      {state.kind === 'empty' && <button onClick={onCreateRecipe}>创建 Recipe</button>}
    </section>
  );
}
function ParameterControl({ parameter, onChange }: { parameter: VfxParameterView; onChange?: VfxShaderEditorProps['onParameterChange'] }) {
  if (parameter.kind === 'boolean') {
    return <input aria-label={parameter.labelZh} type="checkbox" checked={Boolean(parameter.value)} onChange={(event) => onChange?.(parameter.key, event.currentTarget.checked)} />;
  }
  if (parameter.kind === 'color') {
    return <input aria-label={parameter.labelZh} type="color" value={String(parameter.value)} onChange={(event) => onChange?.(parameter.key, event.currentTarget.value)} />;
  }
  return <input aria-label={parameter.labelZh} type="number" value={Number(parameter.value)} min={parameter.minimum} max={parameter.maximum} onChange={(event) => onChange?.(parameter.key, Number(event.currentTarget.value))} />;
}

export default function VfxShaderEditor(props: VfxShaderEditorProps) {
  if (props.state.kind !== 'ready') return <StatusPanel {...props} />;
  const { recipe, mode } = props.state;
  return (
    <main style={panelStyle} data-state="ready" aria-label="VFX Shader 参数编辑器">
      <header style={{ borderBottom: '1px solid var(--border-default, #2f363e)', paddingBottom: 10 }}>
        <h2 style={{ margin: 0, fontSize: 15 }}>{recipe.titleZh}</h2>
        <small>{recipe.recipeId} · {recipe.qualityTier.toUpperCase()} · {mode.toUpperCase()}</small>
      </header>
      {recipe.warningMessages.length > 0 && <section role="alert"><h3>预算警告</h3><ul>{recipe.warningMessages.map((message) => <li key={message}>{message}</li>)}</ul></section>}
      <section aria-label="参数">
        {recipe.parameters.map((parameter) => <label key={parameter.key} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}><span>{parameter.labelZh}</span><ParameterControl parameter={parameter} onChange={props.onParameterChange} /></label>)}
      </section>
      <footer>
        <p>绑定：{recipe.enabledBindingCount}/{recipe.bindingCount} 已启用 · 审批：{recipe.approvalState}</p>
        {recipe.approvalState === 'proposed' && <button onClick={props.onRequestApproval}>提交 ChangeSet 审批</button>}
      </footer>
    </main>
  );
}
