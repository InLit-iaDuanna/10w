import { useMemo } from 'react';
import type { IntegratedWorkbenchProps } from '@sceneops/core-ui';
import { createProjectFetch } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { VersionReviewWorkbench } from './lab/VersionReviewWorkbench';
import { createReviewClient } from './lab/client';

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const client = useMemo(() => createReviewClient(createProjectFetch(props.project.project_id)), [props.project.project_id]);
  return <>
    <IntegratedDraftForm title="版本评审与变更准备" draft={draft} fields={[
      { key: 'title', label: '评审标题' }, { key: 'base_version', label: '基线版本' }, { key: 'target_version', label: '目标版本' },
      { key: 'changes', label: '待评审变更', multiline: true }, { key: 'comment', label: '对象评论草稿', multiline: true },
      { key: 'decision', label: '决策理由', multiline: true }, { key: 'evidence', label: '证据引用', multiline: true },
    ]}>
      <p>评论目标：{props.context.selectedSceneObjectIds.join('、') || '未选择对象'}。本地草稿不是正式审批，不会创建 Git 提交、锁、回滚或发布。</p>
    </IntegratedDraftForm>
    {props.document.sample_id && <VersionReviewWorkbench embedded client={client} projectId={props.project.project_id} onTarget={id => props.onContextChange({ selectedSceneObjectIds: [id] })}/>}
    {!props.document.sample_id && <p>尚无版本差异与评审会话；可以先整理自己的版本和评论，再手动导入 Mock 记录浏览四层差异。</p>}
  </>;
}
