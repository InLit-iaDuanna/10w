import React from "react";
import type { WorkbenchContextSummary } from "../conversation/types.ts";
import { buildContextChips } from "./contextChips.ts";

export { buildContextChips } from "./contextChips.ts";

export function ContextChips({ context }: { context: WorkbenchContextSummary }) {
  const chips = buildContextChips(context);
  if (chips.length === 0) {
    return <span className="conversation-context-empty">未选择项目</span>;
  }

  return (
    <ul className="conversation-context" aria-label="当前工作上下文">
      {chips.map((chip) => (
        <li key={chip.id} className="conversation-context__chip">
          <span>{chip.label}</span>
          <strong>{chip.value}</strong>
        </li>
      ))}
    </ul>
  );
}
