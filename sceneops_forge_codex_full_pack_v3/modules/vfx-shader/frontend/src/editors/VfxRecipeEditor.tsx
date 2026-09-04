import React from 'react';
import type { VfxShaderEditorProps } from '../types';

export default function VfxRecipeEditor(props: VfxShaderEditorProps) {
  if (props.state.kind !== 'ready') {
    return <section role={props.state.kind === 'failed' ? 'alert' : 'status'} data-state={props.state.kind}><h2>VFX Recipe</h2><p>{props.state.kind === 'offline' ? 'Unity 离线；仍可编辑 Recipe。' : `状态：${props.state.kind}`}</p></section>;
  }
  const { recipe, mode } = props.state;
  return (
    <main data-state="ready" aria-label="VFX Recipe 编辑器">
      <h2>{recipe.titleZh}</h2>
      <p>{recipe.recipeId} · {mode.toUpperCase()}</p>
      <dl>
        <dt>质量档位</dt><dd>{recipe.qualityTier}</dd>
        <dt>事件绑定</dt><dd>{recipe.enabledBindingCount}/{recipe.bindingCount} 已启用</dd>
        <dt>审批状态</dt><dd>{recipe.approvalState}</dd>
      </dl>
      {recipe.warningMessages.length > 0 && <section role="alert"><h3>预算警告</h3><ul>{recipe.warningMessages.map((item) => <li key={item}>{item}</li>)}</ul></section>}
      {recipe.approvalState === 'proposed' && <button onClick={props.onRequestApproval}>提交 ChangeSet 审批</button>}
    </main>
  );
}
