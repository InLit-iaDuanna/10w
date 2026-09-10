import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { SourceIcon } from './SourceIcon';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentTasks, agentTaskKeys, type AgentTask } from './client';
import './card-source-editor.css';

const sectionNames: Record<string, string> = {
  '.': '工程配置与架构说明', src: '入口与界面', 'src/game': '游戏主循环与世界',
  'src/game/data': '玩法数据', 'src/game/components': '组件', 'src/game/objects': '游戏对象', 'src/game/systems': 'ECS 系统',
};

type Props = {embedded?: boolean; projectId: string; cardId: string; onDirtyChange?: (dirty: boolean) => void};
export function CardSourceEditor(props: Props) {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else if (dialog.current?.open) {dialog.current.close(); trigger.current?.focus();}
  }, [open]);
  if (props.embedded) return <div className="source-dialog source-embedded"><SourceWorkspace {...props} /></div>;
  return <div className="card-source-launcher">
    <button ref={trigger} type="button" aria-label="架构与源码" title="打开架构与源码" aria-haspopup="dialog" aria-expanded={open}
      onClick={() => {setLoaded(true);setOpen(true);}}><SourceIcon name="code" /><span>源码</span></button>
    {createPortal(<dialog ref={dialog} className="source-dialog" aria-label="架构与源码工作区"
      onCancel={event => {event.preventDefault();setOpen(false);}}>
      <header className="source-dialog-header"><div className="source-brand"><span className="source-brand-icon"><SourceIcon name="code" /></span><div><strong>架构与源码</strong><small>浏览工程 · 精确修改</small></div></div>
        <button type="button" className="source-close" aria-label="返回对话" onClick={() => setOpen(false)}><span>返回对话</span><SourceIcon name="close" /></button></header>
      {loaded && <SourceWorkspace key={`${props.projectId}/${props.cardId}`} {...props} />}
    </dialog>, document.body)}
  </div>;
}

function SourceWorkspace({projectId, cardId, onDirtyChange}: Props) {
  const cache = useQueryClient();
  const [path, setPath] = useState('');
  const [search, setSearch] = useState('');
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const [showFiles, setShowFiles] = useState(true);
  const lineNumbers = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [base, setBase] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [goal, setGoal] = useState('');
  const [run, setRun] = useState(false);
  const [message, setMessage] = useState('');
  const [task, setTask] = useState<AgentTask | null>(null);
  const index = useQuery({queryKey:agentTaskKeys.source(projectId, cardId),
    queryFn:({signal}) => agentTasks.sourceIndex(projectId, cardId, signal), retry:false});
  const file = useQuery({queryKey:agentTaskKeys.sourceFile(projectId, cardId, path),
    queryFn:({signal}) => agentTasks.sourceFile(projectId, cardId, path, signal), enabled:!!path,
    retry:false, refetchOnWindowFocus:false});
  useEffect(() => {
    if (!path && index.data?.files.length) {
      setPath(index.data.files.find(item => item.path === 'src/main.ts')?.path ?? index.data.files[0].path);
    }
  }, [index.data, path]);
  const dirty = base !== null && draft !== base;
  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  useEffect(() => {
    if (file.data && base === null) { setBase(file.data.content); setDraft(file.data.content); }
  }, [file.data, base]);
  const invalidate = async () => {
    await cache.invalidateQueries({queryKey:['agent-tasks']});
    await cache.invalidateQueries({queryKey:agentTaskKeys.source(projectId, cardId)});
  };
  const save = useMutation({mutationFn:async () => {
    if (base === null) throw new Error('请先读取文件。');
    const result = await agentTasks.saveSource(projectId, cardId, {path, expected_content:base, content:draft, allow_game_execution:run});
    if (!result.actions.some(action => action.action.action_id === 'manual_source_save' && action.state === 'succeeded' && action.effect_state === 'COMMITTED'))
      throw new Error(result.reason ?? '保存未完成，请检查任务记录。');
    return result;
  }, onSuccess:async result => {
    setBase(draft);
    setMessage(result.status !== 'review_required' ? `源码已保存，但后续检查未完成：${result.reason ?? '请查看任务记录'}。`
      : run ? '源码已保存并更新试玩，运行结果见卡片任务记录。' : '源码已保存。重新检查并构建后，试玩才会更新。'); await invalidate();
  }});
  const prepare = useMutation({mutationFn:() => agentTasks.prepare({project_id:projectId, card_id:cardId,
    goal:goal.trim(), task_profile:'card-development', execution_mode:'typed-tools',
    source_write_paths:selected, allow_game_execution:run, allow_image_generation:false,
    allow_playtest:false, allow_dependency_install:false}), onSuccess:async result => {
    setTask(result); setMessage('修改范围已准备，请在下方确认开始。'); await invalidate();
  }});
  const authorize = useMutation({mutationFn:async () => {
    if (!task) throw new Error('请先准备修改范围。');
    return agentTasks.authorize(task.id,{authorization_card_id:task.authorization_card.id,accept_unknown_cost:true,accept_full_access:false});
  }, onSuccess:async () => {setTask(null); setGoal(''); setMessage('AI 已开始精修，进度和结果见卡片任务记录。'); await invalidate();}});
  const pending = save.isPending || prepare.isPending || authorize.isPending;
  const selectFile = (value: string) => {
    if (dirty || pending || value === path) return;
    setPath(value); setBase(null); setDraft(''); setMessage(''); save.reset();
  };
  const toggle = (value: string) => {
    setSelected(current => current.includes(value) ? current.filter(item => item !== value) : [...current,value]);
    setTask(null);
  };
  const selectSection = (section: string) => {
    const paths = index.data?.files.filter(item => item.section === section && item.editable).map(item => item.path) ?? [];
    const next = paths.every(value => selected.includes(value))
      ? selected.filter(value => !paths.includes(value)) : [...new Set([...selected, ...paths])];
    if (next.length > 32) {setMessage('本次最多选择 32 个文件，请缩小修改范围。');return;}
    setSelected(next); setTask(null);
  };
  const visibleFiles = index.data?.files.filter(item => item.path.toLowerCase().includes(search.toLowerCase())) ?? [];
  const groups = [...new Set(visibleFiles.map(item => item.section))].sort((a,b) => {
    const priority = (value:string) => value.startsWith('src/game') ? 0 : value === 'src' ? 1 : value === '.' ? 2 : 3;
    return priority(a)-priority(b) || a.localeCompare(b);
  });
  const editable = index.data?.files.find(item => item.path === path)?.editable ?? false;
  const error = save.error || prepare.error || authorize.error;
  return <div className="card-source-workspace">
    <div className="source-context"><span><SourceIcon name="branch" />{index.data?.branch ?? '读取工程…'}</span><span className="source-architecture">{index.data?.architecture}</span><span className="source-context-count">{index.data?.files.length ?? 0} 个文件</span></div>
    {index.isPending && <div className="source-empty" role="status"><SourceIcon name="folder" /><strong>正在打开工程</strong><span>读取当前卡片的真实源码</span></div>}
    {index.error && <div className="source-empty" role="alert"><strong>暂时无法打开工程</strong><p>{index.error.message}</p><button onClick={() => void index.refetch()}>重新连接</button></div>}
    {index.data && <>
      <div className={`source-layout ${showFiles ? '' : 'source-files-hidden'}`}>
        <aside className="source-sidebar" aria-label="架构分区">
          <div className="source-sidebar-title"><strong>工程文件</strong><span>勾选以限定 AI 范围</span></div>
          <label className="source-search"><SourceIcon name="search" /><input aria-label="搜索工程文件" placeholder="搜索文件…" value={search} onChange={event => setSearch(event.target.value)} /></label>
          <nav className="source-tree" aria-label="工程目录">
            {groups.map(section => {
              const files = visibleFiles.filter(item => item.section === section);
              const closed = !search && collapsed.includes(section);
              const sectionFiles = index.data.files.filter(item => item.section === section && item.editable);
              const allSelected = sectionFiles.length > 0 && sectionFiles.every(item => selected.includes(item.path));
              return <section key={section} className="source-group">
                <div className="source-group-heading"><button type="button" title={section} aria-expanded={!closed}
                  onClick={() => setCollapsed(current => current.includes(section) ? current.filter(value => value !== section) : [...current,section])}>
                  <SourceIcon name="chevron" className={closed ? '' : 'source-chevron-open'} /><SourceIcon name="folder" /><span>{sectionNames[section] ?? section.split('/').at(-1)}</span><small>{files.length}</small></button>
                  <input type="checkbox" aria-label={`选择分区 ${section}`} title="选择整个分区" checked={allSelected} disabled={pending || !sectionFiles.length} onChange={() => selectSection(section)} /></div>
                {!closed && files.map(item => <div className={`source-file-row ${path === item.path ? 'is-active' : ''}`} key={item.path}>
                  <button type="button" title={item.path} aria-current={path === item.path ? 'page' : undefined} disabled={dirty || pending} onClick={() => selectFile(item.path)}>
                    <SourceIcon name="file" /><span>{item.path.split('/').at(-1)}</span>{!item.editable && <SourceIcon name="shield" />}</button>
                  <input type="checkbox" aria-label={`允许修改 ${item.path}`} checked={selected.includes(item.path)} disabled={!item.editable || pending || (!selected.includes(item.path) && selected.length >= 32)} onChange={() => toggle(item.path)} />
                </div>)}
              </section>;
            })}
            {!visibleFiles.length && <p className="source-tree-empty">{search ? '没有匹配的文件' : '当前工程暂无源码'}</p>}
          </nav>
          <footer><SourceIcon name="shield" /><span>{selected.length ? `AI 仅可修改 ${selected.length} 个文件` : '浏览文件不会授权修改'}</span></footer>
        </aside>
        <main className="source-main">
          <div className="source-file-toolbar"><button className="source-icon-button" aria-label={showFiles ? '隐藏文件目录' : '显示文件目录'} onClick={() => setShowFiles(!showFiles)}><SourceIcon name="folder" /></button>
            <div className="source-file-tab"><SourceIcon name="code" /><strong>{path.split('/').at(-1) ?? '源码'}</strong>{dirty && <span className="source-dirty-dot" title="未保存" />}</div>
            <div className="source-file-actions"><button disabled={pending || base === null} title={dirty ? '放弃本次编辑' : '重新读取'} onClick={async () => {
              if (dirty) {setDraft(base!);save.reset();setMessage('已恢复到编辑前的内容。');}
              else {const result = await file.refetch();if (result.data && !result.error) {setBase(result.data.content);setDraft(result.data.content);}}
            }}><SourceIcon name={dirty ? 'undo' : 'refresh'} /><span>{dirty ? '放弃本次编辑' : '重新读取'}</span></button>
            <button className="source-primary" disabled={!dirty || pending || !editable} onClick={() => save.mutate()}><SourceIcon name="save" />{save.isPending ? '保存中…' : run ? '保存并更新试玩' : '保存文件'}</button></div></div>
          <div className="source-breadcrumb"><span title={path}>{path || '选择一个文件'}</span><small>{editable ? dirty ? '未保存' : '可编辑' : '只读'}</small></div>
          <div className="source-code-region">
            {file.error ? <div className="source-empty" role="alert"><strong>文件读取失败</strong><p>{file.error.message}</p><button onClick={() => void file.refetch()}>重试</button></div>
              : base === null ? <div className="source-empty" role="status"><SourceIcon name="code" /><strong>{path ? '正在读取源码…' : '选择文件查看内容'}</strong></div>
              : <div className="source-code-editor"><div className="source-line-numbers" aria-hidden="true" ref={lineNumbers}>{draft.split('\n').map((_,i) => <div key={i}>{i+1}</div>)}</div>
                <textarea aria-label={`源码 ${path}`} spellCheck={false} autoCapitalize="off" autoCorrect="off" wrap="off" value={draft} readOnly={!editable || pending}
                  onScroll={event => {if (lineNumbers.current) lineNumbers.current.scrollTop=event.currentTarget.scrollTop;}}
                  onChange={event => setDraft(event.target.value)} /></div>}
          </div>
          <div className="source-code-status"><span>{draft ? draft.split('\n').length : 0} 行 <i>·</i> UTF-8</span><span>{dirty ? '请先保存或放弃，再切换文件' : '点击文件浏览 · 勾选文件授权 AI'}</span></div>
          <section className="source-refine" aria-label="AI 局部精修">
            <header><div><SourceIcon name="spark" /><strong>AI 局部精修</strong><span>{selected.length} 个文件</span></div>
              <button disabled={!path || !editable || pending || selected.includes(path) || selected.length >= 32} onClick={() => toggle(path)}>加入当前文件<SourceIcon name="arrow" /></button></header>
            {selected.length > 0 && <div className="source-selection">{selected.map(value => <button key={value} title={value} disabled={pending} onClick={() => toggle(value)}><SourceIcon name="file" />{value.split('/').at(-1)}<SourceIcon name="close" /></button>)}</div>}
            <div className="source-prompt"><textarea aria-label="局部精修要求" placeholder={selected.length ? '描述想改进的细节，例如：移动速度降低 20%，保留冲刺逻辑…' : '先勾选左侧文件，或加入当前文件，再描述修改要求…'} maxLength={8000} value={goal} disabled={pending} onChange={event => {setGoal(event.target.value);setTask(null);}} />
              <div className="source-prompt-footer"><label title="需要工程已准备依赖；保存文件和 AI 修改均使用此选项"><input type="checkbox" checked={run} disabled={pending} onChange={event => {setRun(event.target.checked);setTask(null);}} />修改后更新试玩</label>
                <button className="source-primary" disabled={dirty || pending || !selected.length || !goal.trim()} onClick={() => prepare.mutate()}>{prepare.isPending ? '准备中…' : '准备局部修改'}<SourceIcon name="arrow" /></button></div></div>
            {task && <section className="source-consent" aria-label="本次文件修改范围"><strong><SourceIcon name="shield" />确认本次修改范围</strong><p>{task.authorization_card.scope}</p><p>{task.authorization_card.cost_notice}</p><button className="source-primary" disabled={pending || dirty} onClick={() => authorize.mutate()}>确认范围并开始精修<SourceIcon name="arrow" /></button></section>}
          </section>
        </main>
      </div>
    </>}
    {(error || message || index.data?.truncated) && <div className={`source-notice ${error ? 'is-error' : ''}`} role={error ? 'alert' : 'status'}><SourceIcon name={error ? 'shield' : 'check'} /><span>{error?.message ?? (message || '文件列表达到上限，当前展示部分文件。')}</span></div>}
  </div>;
}
