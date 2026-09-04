import './world.css';
import { useRef, useState } from 'react';
import { ScenePreview } from '@sceneops/scene-viewer/react';
import { buildWorldEditorScreen } from '../editor-state.ts';
import { createWorldGraphUpdatePlan } from '../world-graph-plan.ts';
import type { WorldMutationPlan } from '../placement.ts';
import type { CameraPose, JsonValue, WorldAnnotation } from '../contracts.ts';
import { createObjectNote, defaultWorldCamera, type WorldSession } from './world-session.ts';

export interface WorldWorkbenchProps {
  session: WorldSession;
  selectedId: string | null;
  onSelect: (id: string) => void;
  gameState: Record<string, JsonValue>;
  gameStateVersion: string;
  onPropose: (plan: WorldMutationPlan<unknown>) => Promise<unknown>;
  onExport: (name: string, data: unknown) => void;
  initialNotes?: WorldAnnotation[];
  onNotesChange?: (notes: WorldAnnotation[]) => void;
  suspended?: boolean;
  initialForm?: Record<string, string>;
  onFormChange?: (patch: Record<string, string>) => void;
}

export function WorldWorkbench(props: WorldWorkbenchProps) {
  const { session, selectedId } = props;
  const [notes, setNotes] = useState<WorldAnnotation[]>(props.initialNotes ?? []);
  const [problem, setProblem] = useState(props.initialForm?.problem ?? '');
  const [intent, setIntent] = useState(props.initialForm?.intent ?? '');
  const [acceptance, setAcceptance] = useState(props.initialForm?.acceptance ?? '');
  const [relation, setRelation] = useState(props.initialForm?.relation ?? session.scene.world.relations[0]?.predicate ?? '');
  const [relationTarget, setRelationTarget] = useState(props.initialForm?.relationTarget ?? session.scene.world.relations[0]?.targetSceneopsId ?? '');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [cameraRevision, setCameraRevision] = useState(0);
  const camera = useRef<CameraPose>(defaultWorldCamera);
  const restore = useRef<CameraPose>(defaultWorldCamera);
  const selected = session.scene.objects.find(object => object.sceneopsId === selectedId);
  const screen = buildWorldEditorScreen('scene.viewport.3d', '场景空间', { status: 'ready', mode: session.scene.mode, sceneId: session.scene.sceneId, sceneVersion: session.scene.sceneVersion });

  function annotate() {
    if (!selectedId) return;
    try {
      const note = createObjectNote(session, { sceneopsId: selectedId, problem, intent, acceptance, camera: camera.current, gameState: props.gameState, gameStateVersion: props.gameStateVersion });
      const updated = [...notes, note]; setNotes(updated); props.onNotesChange?.(updated); setError(null); setNotice('批注草稿已保存在当前页面，可导出 JSON。');
    } catch (cause) { setError(String(cause)); }
  }
  async function propose() {
    setBusy(true); setError(null);
    try {
      const world = structuredClone(session.scene.world);
      world.relations[0] = { ...world.relations[0], predicate: relation, targetSceneopsId: relationTarget };
      const plan = createWorldGraphUpdatePlan(session.scene, { baseVersion: session.scene.sceneVersion, proposedWorld: world, rationale: intent, targetIntegration: 'unity' });
      await props.onPropose(plan);
      setNotice('场景 ChangeSet 已生成，请在下方提案区审阅。');
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }
  function restoreNote(note: WorldAnnotation) {
    const reference = note.context.spatial.reference;
    if (reference.kind === 'object') props.onSelect(reference.object.sceneopsId);
    restore.current = note.context.camera;
    setCameraRevision(value => value + 1);
  }

  return <section className="world-workbench">
    <div className="panel-header"><span>01 / {screen.title}</span><span className="badge mock">{screen.modeLabel} · {screen.statusLabel}</span></div>
    <div className="scene-layout">
      <aside className="outliner"><h3>场景对象</h3><small>选择会同步到玩法图</small>
        {session.scene.objects.map(object => <button key={object.sceneopsId} className={selectedId === object.sceneopsId ? 'object-row selected' : 'object-row'} onClick={() => props.onSelect(object.sceneopsId)} aria-pressed={selectedId === object.sceneopsId}>
          <span>{object.parentSceneopsId ? '◇' : '▣'} {object.displayName}</span><code>{object.sceneopsId}</code>
        </button>)}
        <div className="legend"><span>● 黄铜：钥匙代理</span><span>● 灰蓝：门代理</span><span>┄ 虚线：玩家路线</span></div>
      </aside>
      <div className="viewport-wrap">
        <div className="viewport-toolbar"><span>右手坐标 · Y↑ · 米</span><button onClick={() => { restore.current = defaultWorldCamera; setCameraRevision(value => value + 1); }}>重置视角</button></div>
        {!props.suspended && <ScenePreview index={session.index} objects={session.objects} paths={session.paths} selectedId={selectedId} onSelect={props.onSelect} onCamera={pose => { camera.current = pose; }} camera={restore.current} cameraRevision={cameraRevision}/> }
        <div className="viewport-caption">拖动旋转 · 滚轮缩放 · 点击对象选择　/　确定性几何代理，非真实 GLB</div>
      </div>
      <aside className="inspector"><h3>对象 / 稳定引用</h3>{selected ? <>
        <strong>{selected.displayName}</strong><code className="id">{selected.sceneopsId}</code>
        <dl><dt>局部位置（米）</dt><dd>{selected.transform.position.join(' / ')}</dd><dt>资产 ID</dt><dd>{selected.asset?.assetId ?? '无资产引用'}</dd><dt>碰撞体</dt><dd>{selected.collider ? `${selected.collider.shape} · ${selected.collider.enabled ? '启用' : '停用'}` : '无'}</dd></dl>
        <h3>对象批注</h3>
        <label>问题<textarea value={problem} onChange={event => { setProblem(event.target.value); props.onFormChange?.({ problem: event.target.value }); }} /></label>
        <label>意图<textarea value={intent} onChange={event => { setIntent(event.target.value); props.onFormChange?.({ intent: event.target.value }); }} /></label>
        <label>验收<input value={acceptance} onChange={event => { setAcceptance(event.target.value); props.onFormChange?.({ acceptance: event.target.value }); }} /></label>
        <button className="primary" onClick={annotate}>添加对象批注</button>
      </> : <p>选择一个对象以查看属性。</p>}</aside>
    </div>
    <div className="world-details">
      <section><h3>空间批注 <span className="count">{notes.length}</span></h3>{notes.length === 0 && <p className="muted">批注记录对象、坐标、视角及当时的逻辑状态。</p>}
        {notes.map(note => <article className="annotation" key={note.annotationId}><button onClick={() => restoreNote(note)}>{note.context.problem}</button><span className="badge planned">draft · mock</span><p>{note.context.intent}</p><code>{note.context.spatial.reference.kind === 'object' ? note.context.spatial.reference.object.sceneopsId : ''}</code><div className="actions"><button onClick={() => restoreNote(note)}>定位 / 恢复视角</button><button onClick={() => props.onExport('annotation.json', note)}>导出批注</button></div></article>)}
      </section>
      {session.scene.world.relations.length > 0 && <section><h3>场景关系草稿</h3><p className="muted">修改当前对象关系；通过 ChangeSet 送审。</p><div className="relation-editor"><code>{session.scene.world.relations[0]?.sourceSceneopsId}</code><input aria-label="场景关系谓词" value={relation} onChange={event => { setRelation(event.target.value); props.onFormChange?.({ relation: event.target.value }); }}/><select aria-label="场景关系目标" value={relationTarget} onChange={event => { setRelationTarget(event.target.value); props.onFormChange?.({ relationTarget: event.target.value }); }}>{session.scene.objects.filter(object => object.sceneopsId !== session.scene.world.relations[0]?.sourceSceneopsId).map(object => <option key={object.sceneopsId} value={object.sceneopsId}>{object.displayName}</option>)}</select></div><button disabled={busy} onClick={propose}>{busy ? '正在创建…' : '生成场景 ChangeSet'}</button></section>}
    </div>
    {notice && <p role="status" className="notice">{notice}</p>}{error && <p role="alert" className="error">{error}</p>}
  </section>;
}
