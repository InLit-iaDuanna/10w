import React from "react";
import {
  presentExecutionMode,
  type ExecutionMode,
} from "../contracts/executionMode.ts";

export interface ModeBadgeProps {
  mode: ExecutionMode;
}

export function ModeBadge({ mode }: ModeBadgeProps) {
  const presentation = presentExecutionMode(mode);
  return (
    <span
      className={`conversation-mode conversation-mode--${mode}`}
      aria-label={`执行模式：${presentation.label}。${presentation.description}`}
      title={presentation.description}
    >
      <span aria-hidden="true">{presentation.symbol}</span>
      {presentation.label}
    </span>
  );
}
