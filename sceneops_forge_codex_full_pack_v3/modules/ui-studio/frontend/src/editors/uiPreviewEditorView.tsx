import type { ReactElement } from "react";

export type UiPreviewPhase = "ready" | "loading" | "empty" | "failed" | "offline" | "permission" | "disabled";
export interface UiPreviewEditorViewProps { phase?: UiPreviewPhase; mode?: string; selectedPrompt?: string; resolutionLabel?: string; safeAreaLabel?: string; diffStatus?: string; onSelectPrompt?: (prompt: string) => void; }

const previewCopy: Record<UiPreviewPhase, string> = {
  ready: "安全区域预览（确定性 mock）", loading: "正在准备预览…", empty: "没有可预览的提示。",
  failed: "预览生成失败。", offline: "Unity 未连接；显示本地 mock 预览。",
  permission: "没有预览权限。", disabled: "UI Studio 已禁用。",
};

/** A separate preview surface, deliberately not an alias of the flow editor. */
export default function UiPreviewEditorView({ phase = "ready", mode = "mock", selectedPrompt = "获得：家门钥匙", resolutionLabel = "2532×1170", safeAreaLabel = "80/30/80/30", diffStatus = "结构化视觉回归：通过", onSelectPrompt }: UiPreviewEditorViewProps): ReactElement {
  return <section aria-label="UI 预览" data-phase={phase} data-mode={mode}>
    <header><strong>UI 预览</strong><span>执行模式：{mode.toUpperCase()}</span></header>
    <div role={phase === "failed" ? "alert" : "status"}>{previewCopy[phase]}</div>
    {phase === "ready" && <><p>分辨率：{resolutionLabel}；安全区域：{safeAreaLabel}；{diffStatus}</p><label>预览提示<input aria-label="预览提示" value={selectedPrompt} onChange={(event) => onSelectPrompt?.(event.currentTarget.value)} /></label><div aria-label="安全区域内的提示" data-anchor="safe-bottom-center">{selectedPrompt}</div></>}
  </section>;
}
