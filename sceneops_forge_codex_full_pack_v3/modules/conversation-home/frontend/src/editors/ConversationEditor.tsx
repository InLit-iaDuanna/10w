import React, { useEffect, useRef, useState } from "react";
import type { EditorProps } from "@sceneops/core-contracts";
import type { PreparedAction } from "../assistant-actions/coordinator.ts";
import type { AssistantAction } from "../assistant-actions/types.ts";
import type { BrowserAttachmentSource } from "../composer/attachments.ts";
import { readDroppedEntries } from "../composer/browserDrop.ts";
import { resolveComposerKeyboardIntent } from "../composer/keyboard.ts";
import { ContextChips } from "../components/ContextChips.tsx";
import {
  ConversationHomeFooter,
  ConversationHomeHeader,
} from "../components/ConversationChrome.tsx";
import { ConversationCardView } from "../components/ConversationCardView.tsx";
import { ModeBadge } from "../components/ModeBadge.tsx";
import {
  getConversationCardAction,
  type SuggestedCommand,
} from "../conversation/cards.ts";
import type {
  ConversationAttachment,
  WorkbenchContextSummary,
} from "../conversation/types.ts";
import {
  defaultConversationEditorState,
  type ConversationEditorState,
} from "./state.ts";
import {
  blockedConversationAvailability,
  type ConversationEditorRuntime,
} from "./runtime.ts";

export type ConversationEditorProps = EditorProps<ConversationEditorState> & {
  runtime?: ConversationEditorRuntime;
};

const suggestions = [
  "扫描一个现有 Unity 项目",
  "从一句创意创建项目",
  "继续上次的构建与测试",
] as const;

const emptyContext: WorkbenchContextSummary = {
  projectId: null,
  sceneId: null,
  selectedSceneObjectIds: [],
  activeFeatureId: null,
  activeBuildId: null,
  activeIssueId: null,
};

export default function ConversationEditor(props: ConversationEditorProps) {
  const state = props.localState ?? defaultConversationEditorState;
  const runtime = props.runtime;
  const [preparedActions, setPreparedActions] = useState<
    Record<string, PreparedAction>
  >({});
  const [statusMessage, setStatusMessage] = useState("");
  const [record, setRecord] = useState(() => runtime?.getSnapshot() ?? null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const availability = runtime?.getAvailability() ?? blockedConversationAvailability;
  const context = runtime?.getContextSummary() ?? emptyContext;
  const messages = record?.messages ?? [];
  const mode = record?.executionMode ?? availability.mode;
  const isStreaming = messages.some((message) => message.status === "streaming");
  const canSend = Boolean(runtime) && availability.state === "connected";
  const serviceMessage = availability.message;
  useEffect(() => {
    if (!runtime) {
      return undefined;
    }
    const current = runtime.getSnapshot();
    setRecord(current);
    return runtime.subscribe(setRecord);
  }, [runtime]);

  const updateState = (patch: Partial<ConversationEditorState>) => {
    props.updateLocalState(patch);
  };

  const stageSources = async (sources: BrowserAttachmentSource[]) => {
    if (sources.length === 0) {
      return;
    }
    if (!runtime) {
      setStatusMessage("BLOCKED：附件暂存 adapter 尚未接入。");
      return;
    }
    try {
      const attachments = await runtime.stageAttachments(sources);
      updateState({
        pendingAttachments: [...state.pendingAttachments, ...attachments],
      });
      setStatusMessage(`已附加 ${attachments.length} 项，发送前不会执行或导入。`);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "附件处理失败");
    }
  };

  const send = async (text = state.composerDraft) => {
    if (!runtime) {
      setStatusMessage("BLOCKED：对话运行时尚未接入。");
      return;
    }
    if (availability.state !== "connected") {
      setStatusMessage(`BLOCKED：${serviceMessage}`);
      return;
    }
    if (text.trim().length === 0 && state.pendingAttachments.length === 0) {
      return;
    }
    const result = await runtime.send(text, state.pendingAttachments).catch((error) => {
      setStatusMessage(error instanceof Error ? error.message : "消息发送失败。");
      return null;
    });
    if (!result) {
      return;
    }
    if (result.status === "rejected") {
      setStatusMessage(`${result.code}：${result.message}`);
      return;
    }
    updateState({ composerDraft: "", pendingAttachments: [] });
    setStatusMessage(
      result.storageFailure
        ? `${result.storageFailure.code}：${result.storageFailure.message}`
        : "消息已提交。执行模式显示在响应旁。",
    );
  };

  const prepareAction = async (action: AssistantAction) => {
    if (!runtime) {
      setStatusMessage("BLOCKED：WorkbenchCommandBus 尚未接入。");
      return;
    }
    try {
      const prepared = await runtime.prepareAssistantAction(action);
      setPreparedActions((current) => ({
        ...current,
        [action.actionId]: prepared,
      }));
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "操作检查失败。");
    }
  };

  const executeAction = async (actionId: string, confirmLayout: boolean) => {
    if (!runtime) {
      return;
    }
    const result = await runtime
      .executeAssistantAction(actionId, confirmLayout)
      .catch((error) => {
        setStatusMessage(error instanceof Error ? error.message : "命令执行失败。");
        return null;
      });
    if (!result) {
      return;
    }
    if (result.status === "rejected") {
      setPreparedActions((current) => ({
        ...current,
        [actionId]: { status: "unavailable", error: result.error },
      }));
    } else if (result.status === "waiting_approval") {
      setStatusMessage("等待审批，尚未执行。");
    } else {
      setPreparedActions((current) => {
        const next = { ...current };
        delete next[actionId];
        return next;
      });
      setStatusMessage("命令已由 WorkbenchCommandBus 执行。");
    }
  };

  const cancelAction = (actionId: string) => {
    runtime?.cancelAssistantAction(actionId);
    setPreparedActions((current) => {
      const next = { ...current };
      delete next[actionId];
      return next;
    });
    setStatusMessage("操作已取消。");
  };

  const executeSuggestedCommand = async (command: SuggestedCommand) => {
    if (!runtime) {
      setStatusMessage("BLOCKED：WorkbenchCommandBus 尚未接入。");
      return;
    }
    try {
      await runtime.executeSuggestedCommand(command);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "后续操作不可用。");
    }
  };

  const retryMessage = async (messageId: string) => {
    const result = await runtime?.retry(messageId).catch((error) => {
      setStatusMessage(error instanceof Error ? error.message : "重试失败。");
      return null;
    });
    if (result?.status === "rejected") {
      setStatusMessage(`${result.code}：${result.message}`);
    }
  };

  const openCommandSearch = async (mode: "all" | "slash") => {
    if (!runtime) {
      setStatusMessage("BLOCKED：WorkbenchCommandBus 尚未接入。");
      return;
    }
    try {
      await runtime.openCommandSearch(mode);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "命令搜索不可用。");
    }
  };

  return (
    <main
      className="conversation-home"
      aria-label="SceneOps Forge 对话首页"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        void stageSources(readDroppedEntries(event.dataTransfer));
      }}
    >
      <ConversationHomeHeader context={context} availability={availability} />

      <section className="conversation-thread" aria-label="对话记录">
        {messages.length === 0 ? (
          <div className="conversation-empty">
            <p className="conversation-empty__brand">SceneOps Forge</p>
            <h1>今天要把什么做成可玩的版本？</h1>
            <div className="conversation-empty__suggestions" aria-label="建议操作">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={!canSend}
                  onClick={() => void send(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ol className="conversation-messages" aria-live="polite" aria-relevant="additions text">
            {messages.map((message) => (
              <li
                key={message.messageId}
                className={`conversation-message conversation-message--${message.role}`}
              >
                <div className="conversation-message__meta">
                  <span>{message.role === "user" ? "你" : "SceneOps"}</span>
                  {message.role !== "user" && <ModeBadge mode={message.mode} />}
                </div>
                {message.body && <p>{message.body}</p>}
                {message.attachments.length > 0 && (
                  <ul aria-label="消息附件">
                    {message.attachments.map((attachment) => (
                      <li key={attachment.attachmentId}>
                        {attachment.kind === "project" ? "项目" : "文件"}：{attachment.name}
                      </li>
                    ))}
                  </ul>
                )}
                {message.cards.map((card) => (
                  <ConversationCardView
                    key={card.cardId}
                    card={card}
                    preparedAction={preparedActions[
                      getConversationCardAction(card)?.actionId ?? ""
                    ]}
                    onPrepareAction={(action) => void prepareAction(action)}
                    onExecuteAction={(actionId, confirmation) =>
                      void executeAction(actionId, confirmation)
                    }
                    onCancelAction={cancelAction}
                    onRetry={
                      message.status === "failed" || message.status === "cancelled"
                        ? () => void retryMessage(message.messageId)
                        : undefined
                    }
                    onSuggestedCommand={(command) =>
                      void executeSuggestedCommand(command)
                    }
                  />
                ))}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="conversation-composer" aria-label="消息编辑器">
        <ContextChips context={context} />
        {state.pendingAttachments.length > 0 && (
          <ul className="conversation-attachments" aria-label="待发送附件">
            {state.pendingAttachments.map((attachment: ConversationAttachment) => (
              <li key={attachment.attachmentId}>{attachment.name}</li>
            ))}
          </ul>
        )}
        <textarea
          value={state.composerDraft}
          rows={3}
          aria-label="描述需求、导入项目或输入斜杠打开工具"
          placeholder="描述需求、导入项目或输入 / 打开工具…"
          onChange={(event) => updateState({ composerDraft: event.target.value })}
          onKeyDown={(event) => {
            const intent = resolveComposerKeyboardIntent({
              key: event.key,
              value: state.composerDraft,
              shiftKey: event.shiftKey,
              controlKey: event.ctrlKey,
              metaKey: event.metaKey,
              isComposing: event.nativeEvent.isComposing,
              isStreaming,
            });
            if (intent === "send") {
              event.preventDefault();
              void send();
            } else if (intent === "cancel_stream") {
              event.preventDefault();
              runtime?.cancelStream();
            } else if (
              intent === "open_command_search" ||
              intent === "open_slash_commands"
            ) {
              event.preventDefault();
              void openCommandSearch(
                intent === "open_slash_commands" ? "slash" : "all",
              );
            }
          }}
        />
        <div className="conversation-composer__controls">
          <input
            ref={fileInputRef}
            className="conversation-visually-hidden"
            type="file"
            multiple
            aria-label="选择文件或项目"
            onChange={(event) => {
              const sources = Array.from(event.target.files ?? []).map(
                (file): BrowserAttachmentSource => ({
                  entry: {
                    name: file.name,
                    mediaType: file.type || undefined,
                    sizeBytes: file.size,
                    relativePath: file.webkitRelativePath || undefined,
                    isDirectory: Boolean(file.webkitRelativePath),
                  },
                  file,
                }),
              );
              event.target.value = "";
              void stageSources(sources);
            }}
          />
          <button
            type="button"
            disabled={!runtime}
            onClick={() => fileInputRef.current?.click()}
          >
            添加文件/项目
          </button>
          <button
            type="button"
            disabled={!runtime}
            onClick={() => void openCommandSearch("all")}
          >
            命令搜索
          </button>
          {isStreaming ? (
            <button type="button" onClick={() => runtime?.cancelStream()}>
              取消响应
            </button>
          ) : (
            <button type="button" disabled={!canSend} onClick={() => void send()}>
              发送
            </button>
          )}
        </div>
        {!canSend && <p className="conversation-blocked" role="alert">BLOCKED：{serviceMessage}</p>}
        <p className="conversation-status" role="status" aria-live="polite">
          {statusMessage}
        </p>
      </section>

      <ConversationHomeFooter mode={mode} />
    </main>
  );
}
