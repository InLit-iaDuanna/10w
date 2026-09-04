import { lazy, Suspense, useMemo, useState } from 'react';
import type { IntegratedWorkbenchProps, JsonValue } from '@sceneops/core-ui';
import { requestJson } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { WorldWorkbench } from './web/WorldWorkbench';
import { createWorldSession } from './web/world-session';
import { parseWorldLevelDocument } from './world-model';
import type { WorldAnnotation } from './contracts';
import { loadLogicWorkbench, type LogicWorkbenchApi, type WorldLogicApiComponents } from '../../../logic-studio/frontend/src/index';
const LogicWorkbench = lazy(() => loadLogicWorkbench().then(module => ({ default: module.LogicWorkbench })));
type GameplayGraph = WorldLogicApiComponents['schemas']['GameplayGraph'];
import home from '../../fixtures/remember-home/world.mock.json';
import warehouse from '../../fixtures/warehouse-escape/world.mock.json';

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const json = String(draft.payload.scene_json ?? '');
  const [error, setError] = useState('');
  const document = useMemo(() => draft.payload.scene ?? (props.document.sample_id ? { ...(props.document.sample_id === 'warehouse-escape' ? warehouse : home), projectId: props.project.project_id } : null), [draft.payload.scene, props.document.sample_id, props.project.project_id]);
  const logicApi = useMemo<LogicWorkbenchApi>(() => ({
    loadDemo: () => requestJson('/api/logic/demo', { projectId: props.project.project_id }),
    validate: body => requestJson('/api/logic/validate', { body, projectId: props.project.project_id }),
    preview: body => requestJson('/api/logic/preview', { body, projectId: props.project.project_id }),
    propose: body => requestJson('/api/logic/proposals', { body, projectId: props.project.project_id }),
    proposeCode: body => requestJson('/api/logic/code-proposals', { body, projectId: props.project.project_id }),
  }), [props.project.project_id]);
  const [gameState, setGameState] = useState<{ state: Record<string, JsonValue>; version: string }>({ state: {}, version: '未执行' });
  const session = useMemo(() => document ? createWorldSession(document) : null, [document]);
  function loadScene() {
    try {
      const scene = parseWorldLevelDocument(JSON.parse(json));
      if (scene.projectId !== props.project.project_id) throw new Error('场景 projectId 必须等于当前项目，不能把其他项目数据静默关联过来。');
      draft.update({ scene: scene as unknown as JsonValue }); props.onContextChange({ sceneId: scene.sceneId }); setError('');
    } catch (cause) { setError(String(cause)); }
  }
  return <>
    <IntegratedDraftForm title="场景与玩法设计" draft={draft} fields={[
      { key: 'scene_name', label: '场景名称' }, { key: 'layout', label: '空间布局与动线', multiline: true },
      { key: 'interaction_rules', label: '对象交互与玩法规则', multiline: true }, { key: 'states', label: '状态、条件与转换', multiline: true },
      { key: 'acceptance', label: '场景验收要求', multiline: true },
    ]}>
      <details><summary>载入自己的 WorldLevelDocument</summary><p>当前项目 ID：{props.project.project_id}。只载入空间数据，不执行案例或写回 Unity。</p><textarea aria-label="WorldLevelDocument JSON" rows={8} value={json} onChange={event => draft.update({ scene_json: event.target.value })}/><button type="button" onClick={loadScene}>载入场景文档</button>{error && <p role="alert">{error}</p>}</details>
    </IntegratedDraftForm>
    {session && <WorldWorkbench session={session} selectedId={props.context.selectedSceneObjectIds[0] ?? null} onSelect={id => props.onContextChange({ sceneId: session.scene.sceneId, selectedSceneObjectIds: [id] })} gameState={gameState.state} gameStateVersion={gameState.version} suspended={props.suspended}
      initialForm={draft.payload.world_form as Record<string, string> | undefined} onFormChange={patch => draft.update({ world_form: { ...(draft.payload.world_form as Record<string, JsonValue> ?? {}), ...patch } })}
      initialNotes={(draft.payload.annotations ?? []) as unknown as WorldAnnotation[]} onNotesChange={notes => draft.update({ annotations: notes as unknown as JsonValue })}
      onPropose={async plan => { const proposal = await requestJson('/api/world/proposals', { body: plan, projectId: props.project.project_id }); draft.update({ proposal: proposal as JsonValue }); return proposal; }}
      onExport={(_name, value) => draft.update({ selected_annotation: value as JsonValue })}/>}
    {!draft.payload.graph && !props.document.sample_id && <button onClick={() => draft.update({ graph: { schema_version: 1, graph_id: `graph_${crypto.randomUUID()}`, project_id: props.project.project_id, feature_spec_id: props.context.activeFeatureId ?? `feature_${crypto.randomUUID()}`, version: 1, mode: 'planned', state_variables: [], events: [], scene_objects: [], nodes: [{ node_id: `state_${crypto.randomUUID()}`, kind: 'state', label: '起始状态', sceneops_ids: [], conditions: [], effects: [], emitted_event_ids: [], acceptance_criterion_ids: [] }], edges: [], relationships: [], acceptance_criteria: [], generated_tests: [] } })}>创建自己的玩法图草稿</button>}
    {(draft.payload.graph || props.document.sample_id) && <Suspense fallback={<p>正在加载玩法图…</p>}><LogicWorkbench projectId={props.project.project_id} api={logicApi} initialGraph={props.document.payload.graph as unknown as GameplayGraph | undefined ?? draft.payload.graph as unknown as GameplayGraph | undefined}
      selectedObject={props.context.selectedSceneObjectIds[0] ?? null} onSelectObject={id => props.onContextChange({ selectedSceneObjectIds: [id] })}
      onState={(state, version) => setGameState({ state: state as Record<string, JsonValue>, version })}
      onGraphChange={graph => draft.update({ graph: graph as unknown as JsonValue })}
      initialText={draft.payload.logic_text as Record<string, string> | undefined} onTextChange={patch => draft.update({ logic_text: { ...(draft.payload.logic_text as Record<string, JsonValue> ?? {}), ...patch } })}
      onExport={(_name, value) => draft.update({ logic_export: value as JsonValue })}/></Suspense>}
    {draft.payload.proposal && <details><summary>待审批场景提案</summary><pre>{JSON.stringify(draft.payload.proposal, null, 2)}</pre></details>}
  </>;
}
