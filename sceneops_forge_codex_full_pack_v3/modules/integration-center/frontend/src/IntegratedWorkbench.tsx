import { useMemo } from 'react';
import type { IntegratedWorkbenchProps } from '@sceneops/core-ui';
import { createProjectFetch } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import IntegrationOpsWorkbench from './workbench/IntegrationOpsWorkbench';
import { createOperationsClient } from './workbench/api';

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const client = useMemo(() => createOperationsClient(createProjectFetch(props.project.project_id)), [props.project.project_id]);
  return <>
    <IntegratedDraftForm title="集成配置与排障记录" draft={draft} fields={[
      { key: 'integration_name', label: '集成名称' }, { key: 'endpoint', label: '服务地址（仅记录，不自动连接）' },
      { key: 'required_version', label: '要求版本' }, { key: 'capabilities', label: '需要的能力', multiline: true },
      { key: 'notes', label: '诊断与排障记录', multiline: true },
    ]}><p>不要在草稿中填写密码、Token 或密钥。连接状态以当前项目的实际探测/证据为准，不从配置推断已连接。</p></IntegratedDraftForm>
    <IntegrationOpsWorkbench embedded projectId={props.project.project_id} client={client} initialJob={props.context.activeTaskId ?? ''}/>
  </>;
}
