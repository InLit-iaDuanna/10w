import './logic.css';
import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { logicEditorDefinitions } from '../editors/definitions.ts';
import { createLogicEditorState } from '../editors/state.ts';
import type { LogicEditorView } from '../editors/editorTypes.ts';
import { GraphCanvas } from './GraphCanvas.tsx';
import { NodeInspector } from './NodeInspector.tsx';
import { ProposalReview } from './ProposalReview.tsx';
import { logicWorkbenchKeys, type GameplayGraph, type LogicWorkbenchApi, type PreviewStep } from './api-types.ts';

export interface LogicWorkbenchProps {
  api: LogicWorkbenchApi;
  selectedObject: string | null;
  onSelectObject: (id: string) => void;
  onState: (state: Record<string, unknown>, version: string) => void;
  onExport: (name: string, data: unknown) => void;
  projectId?: string;
  initialGraph?: GameplayGraph;
  onGraphChange?: (graph: GameplayGraph) => void;
  initialText?: { json?: string; code?: string; path?: string; rationale?: string };
  onTextChange?: (patch: Record<string, string>) => void;
}

export function LogicWorkbench(props: LogicWorkbenchProps) {
  const query = useQuery({ queryKey: [...logicWorkbenchKeys.demo, props.projectId ?? 'standalone'], queryFn: props.api.loadDemo, enabled: !props.initialGraph, retry: false, refetchOnWindowFocus: false });
  const [draft, setDraft] = useState<GameplayGraph | null>(null);
  const graph = draft ?? props.initialGraph ?? query.data;
  const [selectedNode, setSelectedNode] = useState(props.initialGraph?.nodes[0]?.node_id ?? '');
  const [tab, setTab] = useState<'graph' | 'relationships' | 'json' | 'code'>('graph');
  const [jsonDraft, setJsonDraft] = useState(props.initialText?.json ?? '');
  const [rationale, setRationale] = useState(props.initialText?.rationale ?? '');
  const [codeDiff, setCodeDiff] = useState(props.initialText?.code ?? '');
  const [codePath, setCodePath] = useState(props.initialText?.path ?? '');
  const [error, setError] = useState('');
  const [steps, setSteps] = useState<PreviewStep[]>([]);
  const [screen, setScreen] = useState<LogicEditorView | null>(null);
  const validation = useMutation({ mutationFn: props.api.validate });
  const preview = useMutation({ mutationFn: props.api.preview });
  const proposal = useMutation({ mutationFn: props.api.propose });
  const codeProposal = useMutation({ mutationFn: props.api.proposeCode });
  const busy = validation.isPending || preview.isPending || proposal.isPending || codeProposal.isPending;
  const status = graph ? 'ready' : query.isPending ? 'loading' : query.isError ? 'failed' : 'empty';

  useEffect(() => {
    let active = true;
    const definition = logicEditorDefinitions.find(item => item.id === 'logic.state_graph')!;
    definition.load().then(runtime => {
      if (active) setScreen(runtime.default.createView(definition, { ...createLogicEditorState(status, 'mock'), ...(query.error ? { errorCode: 'LOCAL_API_UNAVAILABLE' } : {}) }));
    }).catch(cause => { if (active) setError(String(cause)); });
    return () => { active = false; };
  }, [status]);

  useEffect(() => {
    if (!graph || !props.selectedObject) return;
    const node = graph.nodes.find(item => (item.sceneops_ids ?? []).includes(props.selectedObject!));
    if (node) setSelectedNode(node.node_id);
  }, [props.selectedObject, query.data]);

  function update(value: GameplayGraph) {
    const base = props.initialGraph ?? query.data;
    if (!base) return;
    const next = { ...value, version: base.version + 1 };
    setDraft(next); props.onGraphChange?.(next);
    preview.reset(); validation.reset(); proposal.reset(); setSteps([]); setError('');
    props.onState({}, '草稿已修改，预览待重新开始');
  }
  function selectNode(nodeId: string) {
    setSelectedNode(nodeId);
    const id = graph?.nodes.find(node => node.node_id === nodeId)?.sceneops_ids?.[0];
    if (id) props.onSelectObject(id);
  }
  async function startPreview(nextSteps: PreviewStep[]) {
    if (!graph) return;
    setError('');
    try {
      const result = await preview.mutateAsync({ graph, steps: nextSteps });
      setSteps(nextSteps);
      props.onState(result.state, `${graph.graph_id}:v${graph.version}:${nextSteps.length}`);
      const node = graph.nodes.find(item => item.node_id === result.current_node_id);
      setSelectedNode(result.current_node_id);
      if (node?.sceneops_ids?.[0]) props.onSelectObject(node.sceneops_ids[0]);
    } catch (cause) { setError(String(cause)); }
  }
  async function validate() {
    if (!graph) return;
    setError('');
    try { await validation.mutateAsync(graph); } catch (cause) { setError(String(cause)); }
  }
  async function propose() {
    if (!draft) { setError('请先编辑玩法图，再生成 ChangeSet。'); return; }
    setError('');
    try { await proposal.mutateAsync({ graph: draft, rationale }); } catch (cause) { setError(String(cause)); }
  }
  function applyJson() {
    try {
      const value = JSON.parse(jsonDraft);
      if (!value || !Array.isArray(value.nodes) || !value.nodes.length || !Array.isArray(value.edges)) throw new Error('图 JSON 必须含 nodes 与 edges；详细合同将由本地 API 校验。');
      // Keep rendering a known graph until the backend accepts the complete contract.
      void validation.mutateAsync(value).then(report => {
        if (!report.valid) throw new Error(report.issues.map(issue => `${issue.code}: ${issue.message}`).join('\n'));
        update(value); setTab('graph');
      }).catch(cause => setError(String(cause)));
    } catch (cause) { setError(String(cause)); }
  }
  async function proposeCode() {
    if (!graph) return;
    setError('');
    try {
      await codeProposal.mutateAsync({ proposal_id: `proposal_${crypto.randomUUID()}`, graph_id: graph.graph_id, graph_version: graph.version, base_version: 'demo-project-v1', target_paths: [codePath], target_sceneops_ids: (graph.scene_objects ?? []).map(object => object.sceneops_id), unified_diff: codeDiff, rationale, expected_result: '按审阅的 C# 差异更新交互实现。', impact_scope: '当前场景引用的 C# 文件', risk: 'medium', validation_plan: ['先审阅差异；获授权后由 Unity 适配器 dry-run、编译及测试'], rollback_plan: ['恢复基础版本的原文件'], mode: 'planned' });
    } catch (cause) { setError(String(cause)); }
  }

  const node = graph?.nodes.find(item => item.node_id === selectedNode);
  return <section className="logic-workbench"><div className="panel-header"><span>02 / 玩法逻辑</span><span className="badge mock">{screen?.modeLabel ?? 'MOCK'} · {screen?.statusLabel ?? '加载中'}</span></div>
    {!graph && query.isPending && <p className="notice">正在连接本地玩法 API…</p>}
    {query.isError && <div className="error" role="alert"><strong>本地玩法 API 未连接</strong><p>{String(query.error)}</p><button onClick={() => query.refetch()}>重试连接</button></div>}
    {graph && <><fieldset disabled={busy} className="logic-fields">
      <div className="logic-toolbar"><div className="tabs">{(['graph','relationships','json','code'] as const).map(value => <button key={value} aria-pressed={tab === value} onClick={() => { setTab(value); if (value === 'json') setJsonDraft(JSON.stringify(graph, null, 2)); }}>{({ graph: '状态图', relationships: '对象关系', json: '完整图 JSON', code: 'C# 差异' })[value]}</button>)}</div><span className="muted">v{graph.version} · {draft ? '未提交草稿' : '原始样例'}</span><button onClick={validate}>验证草稿</button><button onClick={() => props.onExport('gameplay-graph.json', graph)}>导出图</button></div>
      {tab === 'graph' && <div className="logic-layout"><div><GraphCanvas graph={graph} selectedNode={selectedNode} selectedObject={props.selectedObject} currentNode={preview.data?.current_node_id} onSelect={selectNode}/><div className="actions"><button onClick={() => { const nodeId = `state_${crypto.randomUUID()}`; update({ ...graph, nodes: [...graph.nodes, { node_id: nodeId, kind: 'state', label: '新状态', sceneops_ids: props.selectedObject ? [props.selectedObject] : [], conditions: [], effects: [], emitted_event_ids: [], acceptance_criterion_ids: [] }] }); setSelectedNode(nodeId); }}>添加状态</button><small>青色边框 = 所选对象引用 · 绿点 = 预览当前状态</small></div></div>{node ? <NodeInspector key={node.node_id} graph={graph} node={node} update={update} onSelectObject={props.onSelectObject}/> : <p>选择一个节点以编辑。</p>}</div>}
      {tab === 'relationships' && <div className="relationship-list"><h3>交互关系 / 稳定对象绑定</h3>{(graph.relationships ?? []).map(relationship => <div className="relationship-row" key={relationship.relationship_id}><code>{relationship.relationship_id}</code><select aria-label={`来源 ${relationship.relationship_id}`} value={relationship.source_sceneops_id} onChange={event => update({ ...graph, relationships: graph.relationships!.map(item => item.relationship_id === relationship.relationship_id ? { ...item, source_sceneops_id: event.target.value } : item) })}>{graph.scene_objects?.map(object => <option key={object.sceneops_id} value={object.sceneops_id}>{object.display_name}</option>)}</select><input aria-label={`关系 ${relationship.relationship_id}`} value={relationship.relation_type} onChange={event => update({ ...graph, relationships: graph.relationships!.map(item => item.relationship_id === relationship.relationship_id ? { ...item, relation_type: event.target.value } : item) })}/><select aria-label={`目标对象 ${relationship.relationship_id}`} value={relationship.target_sceneops_id} onChange={event => update({ ...graph, relationships: graph.relationships!.map(item => item.relationship_id === relationship.relationship_id ? { ...item, target_sceneops_id: event.target.value } : item) })}>{graph.scene_objects?.map(object => <option key={object.sceneops_id} value={object.sceneops_id}>{object.display_name}</option>)}</select><button onClick={() => props.onSelectObject(relationship.target_sceneops_id)}>定位目标</button></div>)}</div>}
      {tab === 'json' && <div className="json-editor"><p>完整编辑状态变量、节点、条件、效果和边；更新前由同一个确定性服务检查。</p><textarea aria-label="完整玩法图 JSON" value={jsonDraft} onChange={event => { setJsonDraft(event.target.value); props.onTextChange?.({ json: event.target.value }); }}/><button onClick={applyJson}>验证并更新草稿</button></div>}
      {tab === 'code' && <div className="json-editor"><p>粘贴 unified diff 生成既有 CodeChangeSet。此入口不执行 C#、编译或写文件。</p><label>Unity 相对路径<input value={codePath} onChange={event => { setCodePath(event.target.value); props.onTextChange?.({ path: event.target.value }); }}/></label><textarea aria-label="C# unified diff" placeholder={'--- a/Assets/SceneOps/Homecoming.cs\n+++ b/Assets/SceneOps/Homecoming.cs\n@@ …'} value={codeDiff} onChange={event => { setCodeDiff(event.target.value); props.onTextChange?.({ code: event.target.value }); }}/><button onClick={proposeCode}>生成代码 ChangeSet</button></div>}
      <div className="proposal-actions"><label>变更理由<input value={rationale} onChange={event => { setRationale(event.target.value); props.onTextChange?.({ rationale: event.target.value }); }}/></label><button className="primary" onClick={propose}>生成玩法 ChangeSet</button><button onClick={() => { setDraft(null); preview.reset(); validation.reset(); proposal.reset(); setSteps([]); setError(''); props.onState({}, '预览未开始'); }}>恢复原始样例</button></div>
    </fieldset>
    {validation.data && <div className={validation.data.valid ? 'notice' : 'error'} role="status"><strong>{validation.data.valid ? '✓ 图验证通过' : '图验证发现错误'} · live 本地确定性验证</strong>{validation.data.issues.map((issue, index) => <p key={index}><code>{issue.code}</code> {issue.location} · {issue.message}</p>)}</div>}
    <section className="runtime-preview"><div className="panel-header"><strong>本地逻辑状态预览</strong><span className="badge mock">mock 场景 · live 解释器</span></div><p className="muted">按可用转移推进，观察背包、门锁与任务状态。每次请求从图起点确定性重放；不启动 AI playtest。</p><div className="actions"><button disabled={busy} onClick={() => startPreview([])}>{preview.data ? '重置预览' : '开始本地预览'}</button>{preview.data?.available.map((step, index) => <button className="primary" key={index} disabled={busy} onClick={() => startPreview([...steps, step])}>→ {graph.nodes.find(item => item.node_id === step.target_node_id)?.label ?? step.target_node_id}{step.event_id ? ` / ${step.event_id}` : ''}</button>)}</div>
      {preview.data ? <><div className="state-values"><strong>当前：{preview.data.current_node_id}</strong>{Object.entries(preview.data.state).map(([key, value]) => <div key={key}><code>{key}</code><b>{JSON.stringify(value)}</b></div>)}</div><p className="event-log">事件：{preview.data.events.join(' → ')}</p>{preview.data.available.length === 0 && <p className="notice">没有下一步；当前图已到达终点或无可用转移。</p>}</> : <p className="muted">预览尚未开始，或草稿修改后需要重新开始。</p>}
    </section>
    {proposal.data && <ProposalReview changeSet={proposal.data.change_set} diff={proposal.data.diff} onExport={props.onExport}/>}
    {codeProposal.data && <ProposalReview changeSet={codeProposal.data} onExport={props.onExport}/>}</>}
    {busy && <p role="status" className="notice">正在执行本地请求…</p>}{error && <p role="alert" className="error">{error}</p>}
  </section>;
}
