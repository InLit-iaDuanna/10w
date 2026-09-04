import { useMemo } from 'react';
import type { IntegratedWorkbenchProps } from '@sceneops/core-ui';
import { createProjectFetch } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { UnityBuildWorkbench } from './workbench/UnityBuildWorkbench';
import { createUnityBuildClient } from './workbench/client';

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const api = useMemo(() => createUnityBuildClient(createProjectFetch(props.project.project_id)), [props.project.project_id]);
  return <>
    <IntegratedDraftForm title="Unity 构建与发布计划" draft={draft} fields={[
      { key: 'title', label: '构建 / 发布标题' }, { key: 'unity_project', label: 'Unity 工程路径（只记录）' },
      { key: 'unity_version', label: 'Unity 版本' }, { key: 'source_version', label: '源版本 / commit' },
      { key: 'target', label: '目标平台与架构' }, { key: 'scenes', label: '包含场景', multiline: true },
      { key: 'notes', label: '发布说明', multiline: true }, { key: 'change_set', label: '拟提交变更与审批要求', multiline: true },
    ]}>
      <label>构建配置<select value={String(draft.payload.profile ?? 'development')} onChange={event => draft.update({ profile: event.target.value })}><option value="development">开发</option><option value="qa">质量检查</option><option value="judge">演示</option><option value="release_candidate">发布候选</option></select></label>
      <p>当前构建：{props.context.activeBuildId || '暂无'}。保存不扫描工程、不运行 Unity、不构建或部署。</p>
    </IntegratedDraftForm>
    {props.document.sample_id && <UnityBuildWorkbench embedded api={api} sampleId={props.document.sample_id} projectId={props.project.project_id}/>}
    {!props.document.sample_id && <p>尚无构建或发布证据；真实 Unity、可信审批与生产发布保持未连接。手动导入 Mock 后可浏览原构建矩阵与候选审查面板。</p>}
  </>;
}
