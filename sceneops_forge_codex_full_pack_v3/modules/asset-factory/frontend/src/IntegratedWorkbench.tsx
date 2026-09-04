import { useMemo } from 'react';
import type { IntegratedWorkbenchProps } from '@sceneops/core-ui';
import { createProjectFetch } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { ConceptAssetsWorkbench } from './ConceptAssetsWorkbench';
import { createConceptAssetsClient } from './labClient';

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const client = useMemo(() => createConceptAssetsClient(createProjectFetch(props.project.project_id)), [props.project.project_id]);
  return <>
    <IntegratedDraftForm title="概念与资产规格" draft={draft} fields={[
      { key: 'subject', label: '资产名称' }, { key: 'gameplay_function', label: '玩法用途', multiline: true },
      { key: 'style_constraints', label: '风格与禁止元素', multiline: true }, { key: 'materials', label: '材质要求' },
      { key: 'dimensions', label: '尺寸（米）' }, { key: 'triangle_budget', label: '三角面预算' },
      { key: 'source_uri', label: '来源路径或资源引用（只记录，不读取）' }, { key: 'license', label: '许可与来源说明' },
    ]}>
      <p>当前资产选择：{props.context.selectedAssetIds.join('、') || '未选择'}。制作、发布和 Blender 写入须通过领域 ChangeSet 与审批。</p>
    </IntegratedDraftForm>
    {props.document.sample_id ? <ConceptAssetsWorkbench embedded projectId={props.project.project_id} client={client}/> : <section style={{ padding: 16 }}><h3>概念评审与资产库</h3><p>暂无已批准概念或已生产资产。可以先保存自己的制作规格，或手动导入明确标记的 Mock 样例查看原生产/评审面板。</p></section>}
  </>;
}
