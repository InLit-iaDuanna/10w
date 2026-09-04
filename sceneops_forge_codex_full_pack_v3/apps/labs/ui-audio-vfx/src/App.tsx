import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { UiLabPanel } from '@sceneops/ui-studio';
import { AudioLabPanel } from '@sceneops/audio-studio-frontend';
import { VfxLabPanel } from '@sceneops/vfx-shader-frontend';
import { ui, audio, vfx, result, uiApi, audioApi, vfxApi } from './api';

export function App() {
  const [template, setTemplate] = useState<'home' | 'warehouse'>('home');
  const [eventIndex, setEventIndex] = useState(0);
  const [tab, setTab] = useState<'ui' | 'audio' | 'vfx'>('ui');
  const client = useQueryClient();
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => result(audio.GET('/api/audio/projects')) });
  const uiFixture = useQuery({ queryKey: ['ui-fixture', template], queryFn: () => result(ui.GET('/api/ui/fixture/{template}', { params: { path: { template } } })) });
  const vfxFixture = useQuery({ queryKey: ['vfx-fixture', template], queryFn: () => result(vfx.GET('/api/vfx/fixture/{template}', { params: { path: { template } } })) });
  const proposals = useQuery({ queryKey: ['proposals'], queryFn: async () => {
    const [u, a, v] = await Promise.all([result(ui.GET('/api/ui/proposals')), result(audio.GET('/api/audio/proposals')), result(vfx.GET('/api/vfx/proposals'))]);
    return [...u.map(p => ({ ...p, module: 'ui' as const })), ...a.map(p => ({ ...p, module: 'audio' as const })), ...v.map(p => ({ ...p, module: 'vfx' as const }))];
  } });
  const refresh = () => { void client.invalidateQueries({ queryKey: ['proposals'] }); };
  const approval = useMutation({ mutationFn: ({ module, id }: { module: string; id: string }) => {
    const options = { params: { path: { identity: id } } };
    if (module === 'ui') return result(ui.POST('/api/ui/proposals/{identity}/approve', options));
    if (module === 'audio') return result(audio.POST('/api/audio/proposals/{identity}/approve', options));
    return result(vfx.POST('/api/vfx/proposals/{identity}/approve', options));
  }, onSuccess: refresh });
  const project = projects.data?.find(item => item.id === template);
  const event = project?.events[eventIndex];
  const contextKey = `${template}:${event?.name}`;
  const errors = [projects, uiFixture, vfxFixture].filter(query => query.error);
  return <div className="workbench">
    <header className="app-header"><div className="brand-mark">S</div><strong>SceneOps <span>FORGE</span></strong><div className="header-divider" /><span>工作台 06</span><span className="header-right"><i className="status-dot" />本地会话 · 不连接生产项目</span></header>
    <div className="page-title"><div><p className="eyebrow">EXPERIENCE WORKBENCH</p><h1>UI、音频与特效</h1><p>把一次交互的提示、声音和高亮放在一起。</p></div><div className="integration"><span className="badge blocked">Unity · blocked</span><span className="badge blocked">Render · blocked</span></div></div>
    <section className="context-bar" aria-label="共享项目与事件上下文">
      <label>演示项目<select value={template} onChange={e => { setTemplate(e.target.value as typeof template); setEventIndex(0); }}><option value="home">寻找回家的路</option><option value="warehouse">仓库逃生</option></select></label>
      <label className="event-select">当前事件<select value={eventIndex} disabled={!project} onChange={e => setEventIndex(Number(e.target.value))}>{project?.events.map((item, i) => <option key={item.name} value={i}>{item.name}</option>)}</select></label>
      <div className="target-context"><small>目标对象</small><code>{event?.target || '等待 API'}</code></div><p>切换上下文重置编辑草稿<br />已创建的提案保留在本会话</p>
    </section>
    <div className="workspace-body"><main>
      <nav className="tabs" aria-label="模块编辑器">{(['ui', 'audio', 'vfx'] as const).map((id, i) => <button key={id} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}><span>0{i + 1}</span>{['UI 流程', '音频工作室', '特效 / Shader'][i]}</button>)}</nav>
      {errors.map((query, i) => <div key={i} className="notice error" role="alert">{query.error?.message}<button onClick={() => query.refetch()}>重新连接</button></div>)}
      {!event && !errors.length && <p className="empty-state">正在加载本地演示项目…</p>}
      {event && <div key={contextKey}>
        <section hidden={tab !== 'ui'} aria-label="UI 流程编辑器">{uiFixture.data ? <UiLabPanel fixture={uiFixture.data} template={template} event={event.name} api={uiApi} onProposal={refresh} /> : <p className="empty-state">加载 UI 草稿…</p>}</section>
        <section hidden={tab !== 'audio'} aria-label="音频编辑器"><AudioLabPanel template={template} event={event.name} mixer={event.mixer} api={audioApi} onProposal={refresh} /></section>
        <section hidden={tab !== 'vfx'} aria-label="特效编辑器">{vfxFixture.data ? <VfxLabPanel fixture={vfxFixture.data} template={template} event={event.name} api={vfxApi} onProposal={refresh} /> : <p className="empty-state">加载特效配方…</p>}</section>
      </div>}
    </main><aside className="approval-pane"><div className="section-heading"><h2>审批提案</h2><span className="count">{proposals.data?.length ?? '—'}</span></div>
      <p className="muted">本地审阅人：local-reviewer。批准仅记录本地证据，不发布资产、不写入引擎。</p>
      {proposals.isPending && <p>正在读取提案…</p>}
      {proposals.error && <p className="notice error">{proposals.error.message}<button onClick={() => proposals.refetch()}>重试</button></p>}
      {proposals.data?.length === 0 && <div className="empty-proposals"><span>◇</span><h3>尚无待审提案</h3><p>完成任一模块的编辑，创建提案后在这里查看差异并批准。</p></div>}
      {proposals.data?.map(item => <article className="proposal" key={item.id}><div className="section-heading"><strong>{item.title}</strong><span className={`badge ${item.status === 'approved' ? 'live' : 'planned'}`}>{item.status === 'approved' ? '已批准' : '待审'}</span></div>
        <small>{item.id}</small><details><summary>审阅目标、前后值与回滚计划</summary><pre>{item.details}</pre></details>
        {item.approved_at ? <p className="success-text">本地批准于 {item.approved_at}</p> : <button disabled={approval.isPending} onClick={() => approval.mutate({ module: item.module, id: item.id })}>批准本地提案</button>}
        <p className="muted">planned · 外部发布未执行</p></article>)}
      {approval.error && <p className="notice error" role="alert">{approval.error.message}</p>}
      <div className="notice warning"><strong>会话内存存储</strong><p>API 重启会清空分析和提案。此入口不是生产审批系统。</p></div>
    </aside></div>
    <footer><span><i className="status-dot" />草稿编辑 → 本地校验 → 提案审阅</span><span>live 实际执行 · cached 历史结果（本入口未使用） · mock 示意 · planned 未执行 · blocked 不可用</span></footer>
  </div>;
}
