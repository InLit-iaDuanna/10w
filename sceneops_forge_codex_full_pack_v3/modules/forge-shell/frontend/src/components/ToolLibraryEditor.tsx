import React, { useId, useMemo, useState } from 'react';
import type { EditorHostProps, EditorPlacement } from '../contracts.ts';
import { useShellTools } from './ToolRuntime.ts';
import './tool-picker.css';

const groupDetails: Record<string, { title: string; description: string; glyph: string }> = {
  conversation: { title: '对话', description: '从目标开始，持续整理制作上下文。', glyph: '●' },
  workbench: { title: '制作工作台', description: '按生产环节进入专业编辑空间。', glyph: 'W' },
  planning: { title: 'AI 规划', description: '把制作目标组织成可执行的生产路径。', glyph: 'AI' },
  system: { title: '系统', description: '管理工作台、命令和连接状态。', glyph: 'S' },
};

const categoryGroups: Record<string, keyof typeof groupDetails> = {
  assistant: 'conversation',
  '工作台': 'workbench',
  'AI 制作': 'planning',
  system: 'system',
};
const groupOrder = ['conversation', 'workbench', 'planning', 'system'] as const;

const editorDescriptions: Record<string, string> = {
  'assistant.conversation': '描述目标、获取建议并打开所需功能。',
  'shell.tool-library': '从当前区域选择并替换为其他功能。',
  'shell.command-search': '快速执行打开、保存与布局命令。',
  'workspace.projects': '浏览并切换当前电脑上的项目。',
  'harness.pipeline': '将目标拆解为可追踪的 AI 生产计划。',
  'workbench.project-planning': '编排需求、任务与制作节奏。',
  'workbench.concept-assets': '衔接概念方向与资产生产。',
  'workbench.character-animation': '管理角色制作与动画交付。',
  'workbench.world-logic': '组织场景、玩法逻辑与交互。',
  'workbench.ui-audio-vfx': '统一界面、声音与视觉特效。',
  'workbench.render-ops': '检查镜头、画面与渲染任务。',
  'workbench.unity-build': '推进 Unity 集成、构建与交付。',
  'workbench.version-review': '查看版本变化并进行评审。',
  'workbench.ai-playtest': '编排游测规格并查看已有证据。',
  'workbench.integration-ops': '查看外部工具连接与运行状况。',
};

export default function ToolLibraryEditor({ instanceId }: EditorHostProps) {
  const runtime = useShellTools();
  const [query, setQuery] = useState('');
  const [placement, setPlacement] = useState('current');
  const [error, setError] = useState('');
  const searchId = useId();
  const placements: Record<string, EditorPlacement> = {
    current: { mode: 'replace', relativeToInstanceId: instanceId },
    right: { mode: 'split', direction: 'right', relativeToInstanceId: instanceId }, left: { mode: 'split', direction: 'left', relativeToInstanceId: instanceId },
    above: { mode: 'split', direction: 'above', relativeToInstanceId: instanceId }, below: { mode: 'split', direction: 'below', relativeToInstanceId: instanceId },
    tab: { mode: 'tab', relativeToInstanceId: instanceId }, floating: { mode: 'floating' }, popout: { mode: 'popout' },
  };
  const visibleEditors = useMemo(() => runtime.editors.filter(editor =>
    `${editor.title} ${editor.id} ${editor.category} ${editorDescriptions[editor.id] ?? ''} ${groupDetails[categoryGroups[editor.category] ?? 'system'].title}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  ), [query, runtime.editors]);
  const groupedEditors = useMemo(() => visibleEditors.reduce<Record<string, typeof visibleEditors>>((groups, editor) => {
    const group = categoryGroups[editor.category] ?? 'system';
    (groups[group] ??= []).push(editor);
    return groups;
  }, {}), [visibleEditors]);
  return <section className="shell-tool-content picker-tool-library" aria-label="工具库">
    <header className="picker-header">
      <div><span className="picker-eyebrow">WORKBENCH / TOOLS</span><h2>选择功能</h2><p>从这里替换当前区域，保留已有的位置和尺寸。</p></div>
      <span className="picker-mode"><span aria-hidden="true">⌘</span> 原位打开</span>
    </header>
    <div className="picker-search-field">
      <label htmlFor={searchId}>查找功能</label>
      <div className="picker-search-control"><svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="10.8" cy="10.8" r="5.8" /><path d="m16 16 4 4" /></svg><input id={searchId} aria-label="搜索工具" placeholder="按名称、用途或类别搜索" value={query} onChange={e => setQuery(e.target.value)} /></div>
    </div>
    <details className="picker-placement">
      <summary>位置选项 <span>{placement === 'current' ? '当前区域' : '已选择其他位置'}</span></summary>
      <label><span>打开位置</span><select aria-label="打开位置" value={placement} onChange={e => setPlacement(e.target.value)}>
      {Object.entries({ current: '当前区域', tab: '当前区域新标签', right: '右侧拆分', left: '左侧拆分', above: '上方拆分', below: '下方拆分', floating: '浮动', popout: '弹出窗口' }).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
      </select></label>
    </details>
    <div className="picker-list-meta"><span>{visibleEditors.length} 个可用功能</span><span>选择后立即打开</span></div>
    <div className="picker-groups">{groupOrder.filter(group => groupedEditors[group]).map(group => {
      const details = groupDetails[group];
      const editors = groupedEditors[group] ?? [];
      return <section key={group} className="picker-group">
        <header><span className="picker-group-glyph" aria-hidden="true">{details.glyph}</span><div><h3>{details.title}</h3><p>{details.description}</p></div></header>
        <div className="picker-tool-grid">{editors.map(editor => <button className="picker-tool-item" key={editor.id} title={`技术标识：${editor.id}`} onClick={() => void (placement === 'current'
      ? runtime.execute('workbench.switch_editor', {instanceId, editorId: editor.id})
      : runtime.open(editor.id, placements[placement])).catch(e => setError(e.message))}>
          <span className="picker-tool-icon" aria-hidden="true">{details.glyph}</span>
          <span className="picker-tool-copy"><strong>{editor.title}</strong><small>{editorDescriptions[editor.id] ?? details.description}</small></span>
          <svg className="picker-open-arrow" aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6" /></svg>
        </button>)}</div>
      </section>;
    })}</div>
    {!visibleEditors.length && <div className="picker-empty"><strong>没有找到匹配的功能</strong><span>尝试功能名称、用途或其他类别关键词。</span></div>}
    {error && <p className="picker-feedback is-error" role="alert"><span aria-hidden="true">!</span><span><strong>无法打开功能</strong>{error}</span></p>}
  </section>;
}
