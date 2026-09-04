import React from "react";
import type { ExecutionMode } from "../contracts/executionMode.ts";
import type { WorkbenchContextSummary } from "../conversation/types.ts";
import type { ConversationAvailability } from "../editors/runtime.ts";
import { ModeBadge } from "./ModeBadge.tsx";

const integrationLabels = {
  connected: "已连接",
  disconnected: "已断开",
  blocked: "受阻",
} as const;

export function ConversationHomeHeader({
  context,
  availability,
}: {
  context: WorkbenchContextSummary;
  availability: ConversationAvailability;
}) {
  return (
    <header className="conversation-home__minimal-header">
      <span className="conversation-home__project-name">
        {context.projectName ?? context.projectId ?? "未选择项目"}
      </span>
      <span
        className={`conversation-integration conversation-integration--${availability.state}`}
        aria-label={`对话服务：${integrationLabels[availability.state]}。${availability.message}`}
      >
        <span aria-hidden="true">●</span>
        {integrationLabels[availability.state]}
      </span>
    </header>
  );
}

export function ConversationHomeFooter({ mode }: { mode: ExecutionMode }) {
  return (
    <footer className="conversation-home__minimal-footer">
      <ModeBadge mode={mode} />
      <span>Enter 发送 · Shift+Enter 换行 · ⌘/Ctrl+K 命令</span>
    </footer>
  );
}
