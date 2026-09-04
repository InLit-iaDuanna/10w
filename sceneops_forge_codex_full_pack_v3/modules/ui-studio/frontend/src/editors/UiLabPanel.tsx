import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { components } from '../lab-api';
type S = components['schemas'];

export function UiLabPanel({ fixture, template, event, api, onProposal, initialDraft, onDraftChange, mode = 'mock' }: {
  fixture: S['Fixture']; template: 'home' | 'warehouse'; event: string;
  api: { check: (draft: S['Draft']) => Promise<S['Check']>; propose: (draft: S['Draft']) => Promise<S['Proposal']> };
  onProposal: () => void;
  initialDraft?: S['Draft']; onDraftChange?: (draft: S['Draft']) => void; mode?: 'mock' | 'planned';
}) {
  const [draft, setDraft] = useState<S['Draft']>(initialDraft ?? { template, event, flow: fixture.flow, profile: fixture.profile, character_limit: 32 });
  const [selected, setSelected] = useState(fixture.flow.entry_screen_id);
  const check = useMutation({ mutationFn: (value: S['Draft']) => api.check({ ...value, template, event }) });
  const proposal = useMutation({ mutationFn: (value: S['Draft']) => api.propose({ ...value, template, event }), onSuccess: onProposal });
  const busy = check.isPending || proposal.isPending;
  const update = (next: S['Draft']) => { setDraft(next); onDraftChange?.(next); check.reset(); proposal.reset(); };
  const screen = draft.flow.screens.find(item => item.id === selected)!;
  const editScreen = (next: S['UiScreen']) => update({ ...draft, flow: { ...draft.flow,
    screens: draft.flow.screens.map(item => item.id === selected ? next : item) } });
  const { width, height, safe_area: safe } = draft.profile;
  const safeWidth = width - safe.left - safe.right;
  const safeHeight = height - safe.top - safe.bottom;
  return <div className="module-grid">
    <div className="editor-main">
      <div className="section-heading"><h2>界面流程</h2><span className="badge mock">{mode} · 界面草稿</span></div>
      <div className="flow-list" aria-label="流程界面">{draft.flow.screens.map(item =>
        <button key={item.id} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>
          <small>{item.kind}</small>{item.title}<span>{item.next_screen_ids?.join(' → ') || '流程结束'}</span>
        </button>)}</div>
      <div className="section-heading"><h3>安全区预览</h3><small>{width} × {height} · 结构示意，非设备截图</small></div>
      <div className="ui-stage"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="UI 安全区布局预览">
        <rect width={width} height={height} fill="#1c2527" />
        <path d={`M0 ${height * .74}L${width * .25} ${height * .42}L${width * .6} ${height * .7}L${width} ${height * .3}V${height}H0Z`} fill="#263735" />
        <rect x={safe.left} y={safe.top} width={Math.max(0, safeWidth)} height={Math.max(0, safeHeight)} fill="none" stroke="#58c8c5" strokeDasharray="10 8" />
        {(screen.elements ?? []).map(element => {
          const x = (element.anchor.includes('right') ? width - safe.right - element.width :
            element.anchor.endsWith('center') ? safe.left + (safeWidth - element.width) / 2 : safe.left) + element.offset_x;
          const y = (element.anchor.includes('bottom') ? height - safe.bottom - element.height :
            element.anchor === 'safe-center' ? safe.top + (safeHeight - element.height) / 2 : safe.top) + element.offset_y;
          return <g key={element.id}><rect x={x} y={y} width={element.width} height={element.height} rx="8" fill="#101619" stroke="#eca85b" />
            <text x={x + 16} y={y + element.height / 2 + 7} fill="#f2eee5" fontSize="22">{screen.localized_text['zh-CN']}</text></g>;
        })}
      </svg></div>
      <p className="muted">青色虚线为安全区；边界与文案校验在本地服务执行。选中界面可独立编辑。</p>
      <div className="actions"><button className="primary" disabled={busy} onClick={() => check.mutate(draft)}>{check.isPending ? '校验中…' : '运行 UI 校验'}</button>
        <button disabled={busy} onClick={() => proposal.mutate(draft)}>创建 UI 映射提案</button></div>
      <div aria-live="polite">{check.data && <div className={check.data.issues.length ? 'notice warning' : 'notice success'}>
        <strong>{check.data.issues.length ? `${check.data.issues.length} 个问题` : '校验通过'} · live 本地规则</strong>
        <p>{check.data.message}</p>{check.data.issues.map((issue, i) => <p key={i}>{issue.screen_id}：{issue.message}</p>)}
      </div>}{proposal.data && <p className="notice success">UI 提案已进入右侧审批列表；尚未写入 Unity。</p>}
      {(check.error || proposal.error) && <p className="notice error" role="alert">{(check.error || proposal.error)?.message}</p>}</div>
    </div>
    <fieldset className="inspector" disabled={busy}><legend>UI 属性</legend>
      <label>界面标题<input value={screen.title} onChange={e => editScreen({ ...screen, title: e.target.value })}/></label>
      <label>当前提示文本<textarea value={screen.localized_text['zh-CN']} onChange={e => editScreen({ ...screen, localized_text: { ...screen.localized_text, 'zh-CN': e.target.value } })} /></label>
      <label>字符预算<input type="number" min="1" max="1000" value={draft.character_limit} onChange={e => update({ ...draft, character_limit: Number(e.target.value) })} /></label>
      <div className="field-pair">{(['width', 'height'] as const).map(key => <label key={key}>{key === 'width' ? '画布宽度' : '画布高度'}<input type="number" min="1" value={draft.profile[key]} onChange={e => update({ ...draft, profile: { ...draft.profile, [key]: Number(e.target.value) } })} /></label>)}</div>
      <h3>安全边距 · px</h3><div className="field-pair">{(['left', 'top', 'right', 'bottom'] as const).map((key, i) => <label key={key}>{['左', '上', '右', '下'][i]}<input type="number" min="0" value={safe[key]} onChange={e => update({ ...draft, profile: { ...draft.profile, safe_area: { ...safe, [key]: Number(e.target.value) } } })} /></label>)}</div>
      {(screen.elements ?? []).map(element => <div key={element.id}><h3>元素偏移</h3><div className="field-pair">{(['offset_x', 'offset_y'] as const).map(key => <label key={key}>{key === 'offset_x' ? 'X' : 'Y'}<input type="number" value={element[key]} onChange={e => editScreen({ ...screen, elements: screen.elements?.map(item => item.id === element.id ? { ...item, [key]: Number(e.target.value) } : item) })} /></label>)}</div></div>)}
      <p className="muted">映射目标由顶部事件确定。校验通过不等于设备适配完成。</p>
    </fieldset>
  </div>;
}
