import { useMemo } from 'react';
import type { IntegratedWorkbenchProps } from '@sceneops/core-ui';
import { createProjectFetch } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { RenderLabWorkbench } from './lab/RenderLabWorkbench';

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const transport = useMemo(() => createProjectFetch(props.project.project_id), [props.project.project_id]);
  return <>
    <IntegratedDraftForm title="渲染配方与审阅" draft={draft} fields={[
      { key: 'recipe_name', label: '配方名称' }, { key: 'camera_id', label: '固定相机 ID' },
      { key: 'prompt', label: '视觉目标 / 提示词', multiline: true }, { key: 'negative_prompt', label: '禁止变化', multiline: true },
      { key: 'seed', label: '随机种子' }, { key: 'resolution', label: '输出尺寸' }, { key: 'review_notes', label: '人工审阅记录', multiline: true },
    ]}>
      <p>场景：{props.context.sceneId || '未选择'}；渲染任务：{props.context.activeRenderJobId || '暂无'}。配置不会生成图像或改变场景。</p>
      <fieldset><legend>所需 AOV 通道</legend>{['beauty', 'depth', 'normal', 'albedo', 'object_id', 'material_id'].map(pass => <label key={pass}><input type="checkbox" checked={Array.isArray(draft.payload.aov_passes) && draft.payload.aov_passes.includes(pass)} onChange={event => { const values = Array.isArray(draft.payload.aov_passes) ? draft.payload.aov_passes : []; draft.update({ aov_passes: event.target.checked ? [...values, pass] : values.filter(value => value !== pass) }); }}/>{pass}</label>)}</fieldset>
    </IntegratedDraftForm>
    <RenderLabWorkbench embedded projectId={props.project.project_id} fetchImpl={transport}/>
    {!props.document.sample_id && <p>尚无渲染证据。真实渲染、ComfyUI 和场景写回未连接；可手动导入 Mock 样例查看 AOV、变体和审批面板。</p>}
  </>;
}
