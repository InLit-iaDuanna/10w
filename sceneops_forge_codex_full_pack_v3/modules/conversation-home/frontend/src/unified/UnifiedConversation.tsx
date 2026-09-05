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
      <span className="unified-ai-project"><i aria-hidden="true" />{context.projectId ? `项目 ${context.projectId}` : '未选择项目 · 本地对话'}</span>
      <span className="unified-ai-mode">计划优先 · 人工审批</span>
    </header>
    <div className="unified-ai-transcript" aria-live="polite">
      {history.isPending && <p role="status">正在读取本地对话…</p>}
      {history.error && <p role="alert">{history.error.message} <button onClick={() => void history.refetch()}>重试读取</button></p>}
      {history.data?.messages.length === 0 && <div className="unified-ai-welcome"><span className="unified-ai-eyebrow">SCENEOPS · V5 PRODUCTION HARNESS</span><h1>从一个可玩的目标，<br />开始一条可审查的制作路径。</h1>
        <p>描述玩法、变更或问题。先形成生产计划，再由你审批下一步。</p>
        <div className="unified-ai-suggestions" aria-label="对话建议">
          <button type="button" onClick={() => setDraft('为现有项目梳理一个可验证的玩法目标。')}>梳理玩法目标</button>
          <button type="button" onClick={() => setDraft('把这个需求拆成可审批的制作步骤。')}>拆分制作步骤</button>
          <button type="button" onClick={() => setDraft('检查当前问题需要哪些证据与验收条件。')}>定义验收条件</button>
        </div>
        <small>AI 仅提供建议，不会自动运行工具、导入案例或改动项目。</small></div>}
      {history.data?.messages.map((message) => <article key={message.id} data-role={message.role}>
        <small>{message.role === 'user' ? '你' : `${message.provider === 'openai-compatible' ? '兼容服务' : 'CodeBuddy'} · ${message.model}`} · {message.mode}</small>
        <p>{message.text}</p></article>)}
      {send.isPending && <p role="status">正在等待当前 AI 服务回复…</p>}
    </div>
    <form onSubmit={(event) => { event.preventDefault(); if (draft.trim() && ready && documentReady && !send.isPending) send.mutate(draft.trim()); }}>
      <div className="unified-ai-composer-head"><span>与生产助手对话</span>{onOpenPipeline && <button className="unified-ai-pipeline-cta" type="button" onClick={onOpenPipeline}>生产计划 <span aria-hidden="true">↗</span></button>}</div>
      <UnifiedModelPicker disabled={send.isPending} />
      <ConversationDocumentPicker projectId={context.projectId} selected={selectedModule} onChange={setSelectedModule}
        disabled={send.isPending} document={moduleDocument.data} error={moduleDocument.error}
        loading={moduleDocument.isFetching} retry={() => void moduleDocument.refetch()} />
      <label className="unified-ai-input-label"><span>需求或问题</span><textarea aria-label="需求或问题" value={draft} maxLength={16000}
        disabled={send.isPending} onChange={(event) => setDraft(event.target.value)} placeholder="描述需求或提出问题…" /></label>
      <div className="unified-ai-actions"><small>只附带已保存历史与明确选中的对象 ID。</small>
        {send.isPending ? <button type="button" onClick={() => { setCancelled(true); controller.current?.abort(); }}>取消</button>
          : <button type="submit" disabled={!draft.trim() || !ready || !history.data || !documentReady}>发送</button>}</div>
      {cancelled && !send.isPending && <p role="status">已请求取消；取消前已经完成的回复仍会保留。</p>}
      {send.error && !cancelled && <p role="alert">{send.error.message} <button type="button"
        disabled={!ready || send.isPending || !documentReady} onClick={() => send.mutate(draft.trim())}>重试发送</button></p>}
    </form>
  </section>;
}
