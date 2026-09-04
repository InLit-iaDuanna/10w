import { playtestCommands } from "./commands/definitions.ts";
import { playtestEditors } from "./editor-definitions.ts";
import { manifest } from "./manifest.ts";
export const loadAIPlaytestWorkbench = () => import("./workbench/AIPlaytestWorkbench.tsx");
export const loadIntegratedWorkbench = () => import('./IntegratedWorkbench');

export { editorStatus, editorStateLabels, executionModeLabels } from "./editor-state.ts";
export { playtestCommands } from "./commands/definitions.ts";
export { playtestEditors } from "./editor-definitions.ts";
export { manifest } from "./manifest.ts";
export type * from "./types.ts";

export const moduleContribution = {
  manifest,
  editors: playtestEditors,
  commands: playtestCommands,
  navigation: playtestEditors.map((editor) => ({
    editorId: editor.id,
    group: "测试与回归",
    keywords: ["AI", "Playtest", "测试", "回归"],
    recommendedEdges: editor.defaultPlacement === "bottom" ? ["bottom"] : ["right"],
  })),
  workspacePresets: [
    {
      id: "playtest",
      title: "Playtest",
      editorIds: [
        "playtest.game-view",
        "playtest.agent-monitor",
        "playtest.trajectory",
        "playtest.issue-browser",
      ],
      userInitiatedOnly: true,
    },
  ],
} as const;
