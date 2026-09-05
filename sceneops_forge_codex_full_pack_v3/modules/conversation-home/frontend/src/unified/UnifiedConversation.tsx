import { useEffect, useRef, useState } from 'react';
import type { WorkbenchContext } from '@sceneops/core-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiKeys, readConversation, sendChat } from './aiClient.ts';
import { UnifiedModelPicker, useAIAvailability } from './UnifiedModelPicker.tsx';
import type { ModuleId } from '@sceneops/workspace-client';
import { ConversationDocumentPicker, useConversationDocument } from './ConversationDocumentPicker.tsx';
import './unified-ai.css';

type ConversationProps = {
  context: WorkbenchContext;
  onDirtyChange?: (dirty: boolean) => void;
  /** Opens the host-owned production-plan editor. The conversation never creates a plan itself. */
  onOpenPipeline?: () => void;
};

const providerLabels: Record<string, string> = {
  codebuddycli: 'CodeBuddy CLI',
  'openai-compatible': '兼容服务',
};

const modeLabels: Record<string, string> = {
  live: '真实',
  cached: '缓存',
  mock: '模拟',
  planned: '计划中',
  blocked: '受阻',
};

export function UnifiedConversation({ context, onDirtyChange, onOpenPipeline }: ConversationProps) {
  // A project change disposes pending requests and cannot mix transcripts or composer state.
  return <ProjectConversation key={context.projectId ?? 'pre_project'} context={context} onDirtyChange={onDirtyChange} onOpenPipeline={onOpenPipeline} />;
}

function ProjectConversation({ context, onDirtyChange, onOpenPipeline }: ConversationProps) {
  const [draft, setDraft] = useState('');
  const [cancelled, setCancelled] = useState(false);
  const [selectedModule, setSelectedModule] = useState<ModuleId | ''>('');
  const moduleDocument = useConversationDocument(context.projectId, selectedModule);
  const documentReady = !selectedModule || (!!moduleDocument.data && !moduleDocument.isError && !moduleDocument.isFetching);
  const controller = useRef<AbortController | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const cache = useQueryClient();
  const { ready } = useAIAvailability();
  const key = aiKeys.conversation(context.projectId);
  const history = useQuery({ queryKey: key,
    queryFn: ({ signal }) => readConversation(context.projectId, signal), retry: false });
  const send = useMutation({ mutationFn: async (message: string) => {
    controller.current = new AbortController();
    setCancelled(false);
    if (!documentReady) throw new Error('请等所选模块草稿读取完成，或选择不附带草稿。');
    return sendChat(message, context, controller.current.signal,
      selectedModule && moduleDocument.data ? { moduleId: selectedModule, payload: moduleDocument.data.payload } : undefined);
  }, onSuccess: (conversation) => { cache.setQueryData(key, conversation); setDraft(''); },
    onSettled: () => { void cache.invalidateQueries({ queryKey: key }); } });
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    const node = transcript.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [history.data?.messages.length, send.isPending]);
  useEffect(() => { onDirtyChange?.(!!draft.trim() || send.isPending); }, [draft, send.isPending, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (draft.trim() || send.isPending) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [draft, send.isPending]);
  return <section className="unified-ai-conversation" aria-label="统一 AI 对话">
    <header className="unified-ai-topline">
      <span className="unified-ai-project"><i aria-hidden="true" />{context.projectId ? `当前项目 · ${context.projectId}` : '未选择项目 · 本地对话'}</span>
      <span className="unified-ai-mode"><i aria-hidden="true" />规划后执行 · 需人工确认</span>
    </header>
    <div ref={transcript} className="unified-ai-transcript" aria-live="polite">
      {history.isPending && <p role="status">正在读取本地对话…</p>}
      {history.error && <p role="alert">{history.error.message} <button onClick={() => void history.refetch()}>重试读取</button></p>}
      {history.data?.messages.length === 0 && <div className="unified-ai-welcome"><h1>今天要把什么做成可玩的版本？</h1>
        <p>描述目标或问题。生产助手会先整理计划，再由你确认下一步。</p>
        <div className="unified-ai-suggestions" aria-label="对话建议">
          <button type="button" onClick={() => setDraft('为现有项目梳理一个可验证的玩法目标。')}>梳理玩法目标</button>
          <button type="button" onClick={() => setDraft('把这个需求拆成可审批的制作步骤。')}>拆分制作步骤</button>
          <button type="button" onClick={() => setDraft('检查当前问题需要哪些证据与验收条件。')}>定义验收条件</button>
        </div>
        <small>不会自动运行工具、导入案例或改动项目</small></div>}
      {history.data?.messages.map((message) => <article key={message.id} data-role={message.role}>
        <div className="unified-ai-message-meta"><strong>{message.role === 'user' ? '你' : '生产助手'}</strong><span>{message.role === 'user' ? '已发送' : `${providerLabels[message.provider] ?? message.provider} · ${message.model}`}</span><em data-mode={message.mode} title={message.mode}>{message.role === 'user' ? '请求' : modeLabels[message.mode] ?? message.mode}</em></div>
        <p>{message.text}</p></article>)}
      {send.isPending && <p className="unified-ai-waiting" role="status"><i aria-hidden="true" />正在等待当前 AI 服务回复…</p>}
    </div>
    <form className="unified-ai-composer" onSubmit={(event) => { event.preventDefault(); if (draft.trim() && ready && documentReady && !send.isPending) send.mutate(draft.trim()); }}>
      {onOpenPipeline && <div className="unified-ai-composer-head"><button className="unified-ai-pipeline-cta" type="button" onClick={onOpenPipeline}>查看生产计划 <span aria-hidden="true">↗</span></button></div>}
      <label className="unified-ai-input-label"><span>需求或问题</span><textarea aria-label="需求或问题" value={draft} maxLength={16000} rows={2}
        disabled={send.isPending} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
          if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing || event.keyCode === 229) return;
          event.preventDefault();
          event.currentTarget.form?.requestSubmit();
        }} placeholder="描述目标、制作需求，或粘贴遇到的问题…" /></label>
      <div className="unified-ai-composer-footer">
        <div className="unified-ai-composer-tools">
          <UnifiedModelPicker disabled={send.isPending} />
          <ConversationDocumentPicker projectId={context.projectId} selected={selectedModule} onChange={setSelectedModule}
            disabled={send.isPending} document={moduleDocument.data} error={moduleDocument.error}
            loading={moduleDocument.isFetching} retry={() => void moduleDocument.refetch()} />
        </div>
        <div className="unified-ai-actions"><small title="仅发送历史记录与明确选择的已保存内容"><i aria-hidden="true" />仅历史/所选内容 · Enter 发送 · ⇧Enter 换行</small>
          {send.isPending ? <button className="unified-ai-cancel" type="button" aria-label="取消回复" title="取消回复" onClick={() => { setCancelled(true); controller.current?.abort(); }}><svg aria-hidden="true" viewBox="0 0 16 16"><rect x="5" y="5" width="6" height="6" rx="1" /></svg><span>取消</span></button>
            : <button className="unified-ai-send" type="submit" aria-label="发送消息" title="发送消息" disabled={!draft.trim() || !ready || !history.data || !documentReady}><svg aria-hidden="true" viewBox="0 0 16 16"><path d="M8 12.5v-9M4.5 7 8 3.5 11.5 7" /></svg><span>发送</span></button>}</div>
      </div>
      {cancelled && !send.isPending && <p role="status">已请求取消；取消前已经完成的回复仍会保留。</p>}
      {send.error && !cancelled && <p role="alert">{send.error.message} <button type="button"
        disabled={!draft.trim() || !ready || send.isPending || !documentReady} onClick={() => send.mutate(draft.trim())}>重试发送</button></p>}
    </form>
  </section>;
}
