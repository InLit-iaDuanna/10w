import { Component, lazy, Suspense, useState, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider, useMutation } from '@tanstack/react-query';
import { loadWorldSession, loadWorldWorkbench, type JsonValue } from '../../../../modules/world-composer/frontend/src/index.ts';
import { loadLogicWorkbench, loadProposalReview } from '../../../../modules/logic-studio/frontend/src/index.ts';
import { logicApi, proposeWorld } from './api.ts';
import './style.css';

const WorldWorkbench = lazy(async () => ({ default: (await loadWorldWorkbench()).WorldWorkbench }));
const LogicWorkbench = lazy(async () => ({ default: (await loadLogicWorkbench()).LogicWorkbench }));
const ProposalReview = lazy(async () => ({ default: (await loadProposalReview()).ProposalReview }));
const { createWorldSession } = await loadWorldSession();
const session = createWorldSession();
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

function exportDocument(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function Workbench() {
  const [selected, setSelected] = useState(session.selection.active.primarySceneopsId);
  const [previewState, setPreviewState] = useState<{ state: Record<string, JsonValue>; version: string }>({ state: {}, version: '预览未开始' });
  const proposal = useMutation({ mutationFn: proposeWorld });
  function select(id: string) { setSelected(session.selection.selectOnly(id).primarySceneopsId); }
  return <div className="world-logic-lab">
    <header className="masthead"><a href="#top" className="wordmark">S<span>F</span></a><div><small>SCENEOPS FORGE / WORKBENCH 05</small><h1>场景与玩法</h1></div><div className="header-context"><strong>Find My Way Home</strong><small>钥匙与家门 · 隔离演示工作区</small></div><span className="badge mock">MOCK 数据</span></header>
    <div className="intro" id="top"><div><h2>把空间里的对象，连接成可检查的行为。</h2><p>先选择场景对象并批注，再编辑下方状态图；用本地预览观察钥匙、背包和家门的状态变化。</p></div><div className="integration-status"><span className="badge blocked">Unity · blocked</span><span className="badge blocked">Blender · blocked</span><span className="badge planned">外部写回 · planned</span></div></div>
    <div className="selection-strip"><span>共享选择</span><code>{selected ?? '未选择对象'}</code><span className="muted">sceneops_id · 跨视图引用</span><a href="#logic">跳到玩法图 ↓</a></div>
    <Suspense fallback={<p className="notice">正在加载空间编辑器…</p>}><WorldWorkbench session={session} selectedId={selected} onSelect={select} gameState={previewState.state} gameStateVersion={previewState.version} onPropose={proposal.mutateAsync} onExport={exportDocument}/>{proposal.data && <ProposalReview changeSet={proposal.data} onExport={exportDocument}/>}</Suspense>
    <div id="logic"><Suspense fallback={<p className="notice">正在加载玩法编辑器…</p>}><LogicWorkbench api={logicApi} selectedObject={selected} onSelectObject={select} onState={(state, version) => setPreviewState({ state: state as Record<string, JsonValue>, version })} onExport={exportDocument}/></Suspense></div>
    <footer><span>草稿与批注仅保留在当前页面，刷新会重置；需要保留时请导出 JSON。</span><span>本地预览 ≠ Unity / AI playtest · 无生产写回</span></footer>
  </div>;
}
class WorkbenchErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(error: Error) { return { error: error.message }; }
  render() { return this.state.error ? <main className="error"><h1>工作台加载失败</h1><p>{this.state.error}</p><button onClick={() => location.reload()}>重新加载</button></main> : this.props.children; }
}
createRoot(document.getElementById('root')!).render(<WorkbenchErrorBoundary><QueryClientProvider client={queryClient}><Workbench/></QueryClientProvider></WorkbenchErrorBoundary>);
