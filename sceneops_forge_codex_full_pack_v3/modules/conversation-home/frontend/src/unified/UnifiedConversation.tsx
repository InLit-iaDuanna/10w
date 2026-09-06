import { Fragment, useEffect, useReducer, useRef, useState } from 'react';
import type { WorkbenchContext } from '@sceneops/core-ui';
import { MarkdownMessage } from '@sceneops/core-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiKeys, readConversation, sendChatStream } from './aiClient.ts';
import type { AIModuleDocument, AIConversation } from './aiClient.ts';
import { UnifiedModelPicker, useAIAvailability } from './UnifiedModelPicker.tsx';
import type { ModuleId } from '@sceneops/workspace-client';
import { ConversationDocumentPicker, useConversationDocument } from './ConversationDocumentPicker.tsx';
import {
  createOutgoingAttempt,
  hasPendingAttempt,
  outgoingConversationReducer,
} from './outgoingConversation.ts';
import type { CancellationCause, OutgoingAttempt } from './outgoingConversation.ts';
import './unified-ai.css';
import { AgentTaskTimeline, agentTasks, productionKeys, type AgentTask } from '@sceneops/ai-agent-runtime';

type ConversationProps = {
  context: WorkbenchContext;
  onDirtyChange?: (dirty: boolean) => void;
  initialModuleId?: ModuleId;
  /** Opens the host-owned production-plan editor. The conversation never creates a plan itself. */
  onOpenPipeline?: () => void;
  onTaskPrepared?: (task: AgentTask) => void;
};

type SendVariables = {
  attemptId: string;
  text: string;
  context: WorkbenchContext;
  signal: AbortSignal;
  document?: { moduleId: string; payload: AIModuleDocument };
};

type ActiveRequest = { attemptId: string; controller: AbortController; contextIdentity: string };

const providerLabels: Record<string, string> = {
  codebuddycli: 'CodeBuddy CLI',
  codexcli: 'Codex CLI',
  'openai-compatible': '兼容服务',
};

const modeLabels: Record<string, string> = {
  live: '真实', cached: '缓存', mock: '模拟', planned: '计划中', blocked: '受阻',
};

const cancellationLabels: Record<CancellationCause, string> = {
  user: '已停止等待；取消前完成的回复可能已经保存。',
  context_changed: '上下文已变化，已停止等待；服务端完成状态尚未确认。',
  request_aborted: '请求已中止；服务端完成状态尚未确认。',
};

function contextIdentity(context: WorkbenchContext): string {
  return JSON.stringify([
    context.projectId, context.branchId, context.sceneId,
    context.selectedSceneObjectIds, context.selectedAssetIds,
    context.activeFeatureId, context.activeTaskId, context.activeChangeSetId,
    context.activeRenderJobId, context.activeBuildId, context.activePlaytestRunId,
    context.activeIssueId,
    context.selectedArtifactIds, context.activeProductionModuleId,
  ]);
}

function snapshotContext(context: WorkbenchContext): WorkbenchContext {
  return {
    ...context,
    selectedSceneObjectIds: [...context.selectedSceneObjectIds],
    selectedAssetIds: [...context.selectedAssetIds],
  };
}

export function UnifiedConversation({ context, onDirtyChange, onOpenPipeline, initialModuleId, onTaskPrepared }: ConversationProps) {
  // A project change disposes pending requests and cannot mix transcript or composer state.
  return <ProjectConversation key={context.projectId ?? 'pre_project'} context={context} onDirtyChange={onDirtyChange} initialModuleId={initialModuleId} {...(onTaskPrepared ? { onTaskPrepared } : {})} {...(onOpenPipeline ? { onOpenPipeline } : {})} />;
}

function ProjectConversation({ context, onDirtyChange, onOpenPipeline, initialModuleId, onTaskPrepared }: ConversationProps) {
  const [draft, setDraft] = useState('');
  const [permission, setPermission] = useState<'discussion' | 'task' | 'codex-full-access'>('discussion');
  const [allowImages, setAllowImages] = useState(false);
  const taskPermission = permission !== 'discussion';
  const [attempts, dispatchAttempt] = useReducer(outgoingConversationReducer, []);
  const [selectedModule, setSelectedModule] = useState<ModuleId | ''>(initialModuleId ?? '');
  const moduleDocument = useConversationDocument(context.projectId, selectedModule);
  const documentReady = !selectedModule || (!!moduleDocument.data?.payload && !moduleDocument.isError && !moduleDocument.isFetching);
  const activeRequest = useRef<ActiveRequest | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const cache = useQueryClient();
  const { ready } = useAIAvailability();
  const key = aiKeys.conversation(context.projectId);
  const currentContextIdentity = contextIdentity(context);
  const history = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => readConversation(context.projectId, signal),
    retry: false,
  });
  const send = useMutation({
    mutationFn: (variables: SendVariables) => sendChatStream(
      variables.text,
      variables.context,
      variables.signal,
      (event) => {
        if (event.type === 'text_delta' && event.text) {
          dispatchAttempt({ type: 'response_delta', attemptId: variables.attemptId, text: event.text });
        } else if (event.type === 'status' && event.text) {
          dispatchAttempt({ type: 'response_status', attemptId: variables.attemptId, text: event.text });
        }
      },
      variables.document,
    ),
    onSuccess: (conversation, variables) => {
      cache.setQueryData(key, conversation);
      dispatchAttempt({ type: 'saved', attemptId: variables.attemptId });
    },
    onError: (error, variables) => {
      if (variables.signal.aborted) {
        dispatchAttempt({ type: 'cancelled', attemptId: variables.attemptId, cause: 'request_aborted' });
      } else {
        dispatchAttempt({
          type: 'failed',
          attemptId: variables.attemptId,
          error: error instanceof Error ? error.message : '发送失败，请重试。',
        });
      }
    },
    onSettled: (_data, _error, variables) => {
      if (activeRequest.current?.attemptId === variables.attemptId) activeRequest.current = null;
    },
  });
  const prepareTask = useMutation({
    mutationFn: (goal: string) => agentTasks.prepare({ goal,
      execution_mode: permission === 'codex-full-access' ? 'codex-full-access' : 'typed-tools',
      allow_image_generation: permission === 'codex-full-access' && allowImages,
      allow_playtest: false,
      task_profile: 'auto',
      ...(context.projectId ? { project_id: context.projectId } : {}) }),
    onSuccess: async (task, goal) => {
      setDraft(current => current.trim() === goal ? '' : current);
      await cache.invalidateQueries({ queryKey: ['agent-tasks'] });
      await cache.invalidateQueries({ queryKey: productionKeys.snapshot(task.project_id) });
      requestAnimationFrame(() => { if (transcript.current) transcript.current.scrollTop = transcript.current.scrollHeight; });
    },
  });
  const pendingAttempt = attempts.find(attempt => attempt.status === 'pending');
  const requestBusy = send.isPending || hasPendingAttempt(attempts);

  const startRequest = (text: string, retryAttempt?: OutgoingAttempt) => {
    if (activeRequest.current || requestBusy || !ready || !history.isSuccess || !documentReady) return;
    const attempt = retryAttempt ?? createOutgoingAttempt(crypto.randomUUID(), text, new Date().toISOString());
    const controller = new AbortController();
    activeRequest.current = {
      attemptId: attempt.id,
      controller,
      contextIdentity: currentContextIdentity,
    };
    dispatchAttempt(retryAttempt
      ? { type: 'retried', attemptId: attempt.id }
      : { type: 'started', attempt });
    if (!retryAttempt) setDraft('');
    send.mutate({
      attemptId: attempt.id,
      text: attempt.text,
      context: snapshotContext(context),
      signal: controller.signal,
      ...(selectedModule && moduleDocument.data?.payload
        ? { document: { moduleId: selectedModule, payload: moduleDocument.data.payload } }
        : {}),
    });
  };

  const cancelActiveRequest = (cause: CancellationCause) => {
    const active = activeRequest.current;
    if (!active) return;
    dispatchAttempt({ type: 'cancelled', attemptId: active.attemptId, cause });
    active.controller.abort();
    activeRequest.current = null;
  };

  useEffect(() => () => activeRequest.current?.controller.abort(), []);
  useEffect(() => {
    const active = activeRequest.current;
    if (active && active.contextIdentity !== currentContextIdentity) {
      dispatchAttempt({ type: 'cancelled', attemptId: active.attemptId, cause: 'context_changed' });
      active.controller.abort();
      activeRequest.current = null;
    }
  }, [currentContextIdentity]);
  useEffect(() => {
    const node = transcript.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [history.data?.messages.length, attempts]);
  useEffect(() => { onDirtyChange?.(!!draft.trim() || requestBusy || prepareTask.isPending); }, [draft, requestBusy, prepareTask.isPending, onDirtyChange]);
  const selectedPreparedTask = useRef<string | null>(null);
  useEffect(() => {
    const task = prepareTask.data;
    if (!prepareTask.isSuccess || prepareTask.isPending || draft.trim() || !task || selectedPreparedTask.current === task.id) return;
    selectedPreparedTask.current = task.id;
    onTaskPrepared?.(task);
  }, [prepareTask.data, prepareTask.isSuccess, prepareTask.isPending, draft, onTaskPrepared]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (draft.trim() || requestBusy || prepareTask.isPending) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [draft, requestBusy, prepareTask.isPending]);

  const rows = [
    ...(history.data?.messages.map(message => ({ kind: 'saved' as const, createdAt: message.created_at, message })) ?? []),
    ...attempts.map(attempt => ({ kind: 'outgoing' as const, createdAt: attempt.createdAt, attempt })),
  ].sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  const taskGoalValid = draft.trim().length > 0 && draft.trim().length <= 8000;
  const composerBusy = requestBusy || prepareTask.isPending;
  function submitComposer() {
    const message = draft.trim();
    if (!message || composerBusy) return;
    if (taskPermission) {
      if (!taskGoalValid) return;
      prepareTask.mutate(message);
      return;
    }
    startRequest(message);
  }

  return <section className="unified-ai-conversation" aria-label="统一 AI 对话">
    <header className="unified-ai-topline">
      <span className="unified-ai-project" title={context.projectId ?? '本地对话'}>{history.data?.messages.length ? '对话' : '新对话'}</span>
      {onOpenPipeline && <details className="unified-ai-thread-menu" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false; }} onKeyDown={event => { if (event.key === 'Escape') event.currentTarget.open = false; }}>
        <summary aria-label="对话选项" title="对话选项">···</summary>
        <div><button type="button" onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); onOpenPipeline(); }}>打开生产计划 <span aria-hidden="true">↗</span></button></div>
      </details>}
    </header>
    <div ref={transcript} className="unified-ai-transcript" aria-live="polite">
      {history.isPending && <p role="status">正在读取本地对话…</p>}
      {history.error && <p role="alert">{history.error.message} <button onClick={() => void history.refetch()}>重试读取</button></p>}
      {rows.map(row => row.kind === 'saved'
        ? <SavedMessage key={`saved:${row.message.id}`} message={row.message} />
        : <Fragment key={`outgoing:${row.attempt.id}`}>
            <OutgoingMessage attempt={row.attempt}
              retryDisabled={requestBusy || !ready || !history.isSuccess || !documentReady}
              onRetry={() => startRequest(row.attempt.text, row.attempt)} />
            <StreamingReply attempt={row.attempt} />
          </Fragment>)}
      <AgentTaskTimeline projectId={context.projectId} />
    </div>
    <form className="unified-ai-composer" onSubmit={(event) => {
      event.preventDefault();
      submitComposer();
    }}>
      <label className="unified-ai-input-label"><span>{taskPermission ? '任务目标' : '需求或问题'}</span><textarea aria-label={taskPermission ? '任务目标' : '需求或问题'} value={draft} maxLength={taskPermission ? 8000 : 16000} rows={2}
        onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
          if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing || event.keyCode === 229) return;
          event.preventDefault();
          event.currentTarget.form?.requestSubmit();
        }} placeholder="询问任何内容，或描述你想完成的工作…" /></label>
      <div className="unified-ai-composer-footer">
        <div className="unified-ai-composer-tools">
          <details className="unified-ai-context-menu" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false; }} onKeyDown={event => { if (event.key === 'Escape') event.currentTarget.open = false; }}>
            <summary aria-label="添加上下文" title="添加上下文">+</summary>
            <div className="unified-ai-context-popover"><strong>对话上下文</strong><p>只附带你明确选择的已保存内容，不读取项目文件。</p>
              {context.projectId ? <ConversationDocumentPicker projectId={context.projectId} selected={selectedModule} onChange={setSelectedModule}
                disabled={composerBusy} {...(moduleDocument.data ? { document: moduleDocument.data } : {})} error={moduleDocument.error}
                loading={moduleDocument.isFetching} retry={() => void moduleDocument.refetch()} />
                : <p>先在「本地项目」中选择项目，再添加模块草稿。</p>}
            </div>
          </details>
          <UnifiedModelPicker disabled={composerBusy} compact />
          {selectedModule && permission === 'discussion' && <span className="unified-ai-context-chip" title="已明确选择的模块草稿">已附带草稿</span>}
          {!!context.selectedArtifactIds?.length && <span className="unified-ai-context-chip">已选产物 {context.selectedArtifactIds.length} 项</span>}
        </div>
        <div className="unified-ai-actions">
          <label className="unified-ai-permission"><span>权限</span><select aria-label="执行权限" value={permission} disabled={composerBusy} onChange={event => setPermission(event.target.value as typeof permission)}><option value="discussion">仅讨论</option><option value="task">受控工具（先授权）</option><option value="codex-full-access">Codex 完全权限（先授权）</option></select></label>
          {pendingAttempt ? <button className="unified-ai-cancel" type="button" aria-label="取消回复" title="取消回复" onClick={() => cancelActiveRequest('user')}><svg aria-hidden="true" viewBox="0 0 16 16"><rect x="5" y="5" width="6" height="6" rx="1" /></svg><span>取消</span></button>
            : <button className="unified-ai-send" type="submit" aria-label={taskPermission ? '准备任务授权' : '发送消息'} title={taskPermission ? '准备任务授权' : '发送消息'} disabled={taskPermission ? !taskGoalValid || composerBusy : !draft.trim() || !ready || !history.isSuccess || !documentReady || composerBusy}><svg aria-hidden="true" viewBox="0 0 16 16"><path d="M8 12.5v-9M4.5 7 8 3.5 11.5 7" /></svg><span>{prepareTask.isPending ? '准备中…' : taskPermission ? '准备授权' : '发送'}</span></button>}
        </div>
      </div>
      {taskPermission && <p className="unified-ai-task-note">先准备授权卡，不立即执行。任务仅使用目标，不附带模块草稿，最多 8000 字符。{permission === 'codex-full-access' && ' 需选择 Codex CLI；完全权限允许文件/Shell 操作，并非系统沙箱。low 轻量思考。'}</p>}
      {permission === 'codex-full-access' && <label className="unified-ai-task-note"><input type="checkbox" checked={allowImages} disabled={composerBusy} onChange={event => setAllowImages(event.target.checked)} /> 本任务允许 GPT 图片生成（Codex 登录，不切换付费 API）</label>}
      {prepareTask.error && <p role="alert">准备任务失败：{prepareTask.error.message}</p>}
    </form>
    <div className="unified-ai-composer-note"><span>本地对话 · 操作需确认</span><span>Enter 发送 · Shift + Enter 换行</span></div>
  </section>;
}

function SavedMessage({ message }: { message: AIConversation['messages'][number] }) {
  return <article data-role={message.role}>
    <div className="unified-ai-message-meta"><strong>{message.role === 'user' ? '你' : 'SceneOps'}</strong>{message.role !== 'user' && <span title={`${providerLabels[message.provider] ?? message.provider} · ${message.model}`}>{message.model}</span>}<em data-mode={message.mode} title={message.mode}>{message.role === 'user' ? '已保存' : modeLabels[message.mode] ?? message.mode}</em></div>
    {message.role === 'user' ? <p>{message.text}</p> : <MarkdownMessage text={message.text} />}
  </article>;
}

function OutgoingMessage({ attempt, retryDisabled, onRetry }: {
  attempt: OutgoingAttempt;
  retryDisabled: boolean;
  onRetry: () => void;
}) {
  return <article data-role="user" data-delivery={attempt.status}>
    <p>{attempt.text}</p>
    {attempt.status === 'failed' && <div className="unified-ai-outgoing-state is-failed" role="alert">
      <span>未确认发送成功：{attempt.error}</span>
      <button type="button" disabled={retryDisabled} onClick={onRetry}>重试这条消息</button>
    </div>}
    {attempt.status === 'cancelled' && <div className="unified-ai-outgoing-state is-cancelled" role="status">
      <span>{cancellationLabels[attempt.cancellationCause ?? 'request_aborted']}</span>
      <button type="button" disabled={retryDisabled} onClick={onRetry}>重试这条消息</button>
    </div>}
  </article>;
}

function StreamingReply({ attempt }: { attempt: OutgoingAttempt }) {
  if (attempt.status !== 'pending' && !attempt.responseText) return null;
  const incomplete = attempt.status !== 'pending';
  return <article className="unified-ai-streaming-reply" data-role="assistant" data-stream={attempt.status}>
    <div className="unified-ai-message-meta">
      <strong>SceneOps</strong>
      <em data-mode={incomplete ? 'blocked' : 'planned'}>{incomplete ? '未完成 · 未保存' : '实时'}</em>
    </div>
    {attempt.responseText && <MarkdownMessage text={attempt.responseText} />}
    {!incomplete && <div className="unified-ai-stream-state" role="status">
      <i aria-hidden="true" />{attempt.streamStatus ?? '正在等待 AI 回复…'}
    </div>}
    {incomplete && attempt.responseText && <p className="unified-ai-stream-incomplete">
      上方仅为中断前收到的片段，不是已保存的完整回复。
    </p>}
  </article>;
}
