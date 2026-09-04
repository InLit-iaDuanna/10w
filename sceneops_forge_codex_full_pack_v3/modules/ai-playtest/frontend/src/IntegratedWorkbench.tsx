import { useCallback } from 'react';
import type { IntegratedWorkbenchProps, JsonValue } from '@sceneops/core-ui';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { AIPlaytestWorkbench } from './workbench/AIPlaytestWorkbench';
import type { LocalReview, ProposalDraft } from './workbench/evidence';

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const recordsChanged = useCallback((reviews: Record<string, LocalReview>, proposals: Record<string, ProposalDraft>) => {
    draft.update({ reviews: reviews as unknown as JsonValue, proposals: proposals as unknown as JsonValue });
  }, [draft.update]);
  return <>
    <IntegratedDraftForm title="AI 测试配置与人工审阅" draft={draft} fields={[
      { key: 'objective', label: '测试目标', multiline: true }, { key: 'actor_id', label: '玩家对象 ID' },
      { key: 'allowed_actions', label: '允许动作（每行一个）', multiline: true }, { key: 'seed', label: '随机种子' },
      { key: 'max_steps', label: '最大步数' }, { key: 'max_duration', label: '最长运行时间（秒）' },
      { key: 'acceptance', label: '目标判定规则', multiline: true }, { key: 'issue_notes', label: '人工问题与证据记录', multiline: true },
    ]}>
      <p>关联构建：{props.context.activeBuildId || '未选择'}；场景：{props.context.sceneId || '未选择'}。AI 接入统一 CodeBuddy CLI，模型由工作台选择；这里不自动运行 runner。</p>
      <button type="button" disabled title="需要后续明确运行授权与已连接的有界 runner">启动测试 · 未开放</button>
    </IntegratedDraftForm>
    {props.document.sample_id && <AIPlaytestWorkbench embedded sample={props.document.sample_id}
      initialReviews={(props.document.payload.reviews ?? {}) as unknown as Record<string, LocalReview>}
      initialProposals={(props.document.payload.proposals ?? {}) as unknown as Record<string, ProposalDraft>} onRecordsChange={recordsChanged}/>}
    {!props.document.sample_id && <p>暂无运行证据或问题。可编辑自己的测试配置；导入 Mock 样例只显示静态证据，不启动任何案例测试。</p>}
  </>;
}
