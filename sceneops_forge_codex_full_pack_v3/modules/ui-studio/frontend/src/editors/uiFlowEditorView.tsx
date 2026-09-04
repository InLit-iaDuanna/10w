import type { ReactElement } from "react";

export type UiEditorPhase = "ready" | "loading" | "empty" | "failed" | "offline" | "permission" | "disabled";
export type UiEditorMode = "live" | "cached" | "mock" | "planned" | "blocked";

export interface UiFlowEditorViewProps {
  phase?: UiEditorPhase;
  mode?: UiEditorMode;
  message?: string;
  prompts?: ReadonlyArray<{ id: string; title: string; text: string }>;
  resolutionLabel?: string;
  safeAreaLabel?: string;
  validationStatus?: string;
  onPromptTextChange?: (promptId: string, locale: string, text: string) => void;
}

const phaseCopy: Record<UiEditorPhase, string> = {
  ready: "可编辑", loading: "正在加载 UI 流程…", empty: "尚未创建 UI 流程。",
  failed: "UI 流程加载失败，请重试。", offline: "Unity 未连接；可以继续编辑并生成提议。",
  permission: "没有查看此 UI 流程的权限。", disabled: "UI Studio 已被功能开关禁用。",
};

const heroPrompts = [
  { id: "hud.home", title: "任务 HUD", text: "寻找回家的钥匙" },
  { id: "prompt.key-picked", title: "拾取反馈", text: "获得：家门钥匙" },
  { id: "prompt.door-locked", title: "锁门提示", text: "门锁着，需要找到钥匙。" },
  { id: "prompt.door-unlocked", title: "解锁反馈", text: "钥匙转动，门已解锁。" },
];

/** A dependency-light editor view; command execution remains in the host command bus. */
export default function UiFlowEditorView({
  phase = "ready", mode = "mock", message, prompts = heroPrompts, resolutionLabel = "2532×1170",
  safeAreaLabel = "左/上/右/下：80/30/80/30", validationStatus = "验证通过（mock）", onPromptTextChange,
}: UiFlowEditorViewProps): ReactElement {
  return <section aria-label="UI 流程编辑器" data-phase={phase} data-mode={mode}>
    <header><strong>UI 流程</strong><span>执行模式：{mode.toUpperCase()}</span></header>
    <p role={phase === "failed" ? "alert" : "status"}>{message ?? phaseCopy[phase]}</p>
    {phase === "ready" && <><p>分辨率：{resolutionLabel}；安全区域：{safeAreaLabel}；{validationStatus}</p><ol>{prompts.map((prompt) => <li key={prompt.id}><label><b>{prompt.title}</b><input aria-label={`${prompt.title} 中文文案`} value={prompt.text} onChange={(event) => onPromptTextChange?.(prompt.id, "zh-CN", event.currentTarget.value)} /></label></li>)}</ol></>}
  </section>;
}
