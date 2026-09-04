import {
  restorePlaytestEditorState,
  serializePlaytestEditorState,
} from "./editor-state.ts";
import type {
  EditorDefinition,
  EditorSurfaceState,
  PlaytestEditorProps,
  PlaytestEditorState,
} from "./types.ts";

const supportedStates: EditorSurfaceState[] = [
  "loading",
  "empty",
  "ready",
  "failed",
  "offline",
  "permission_denied",
  "disabled",
];

const common = {
  category: "test" as const,
  minWidth: 320,
  minHeight: 220,
  singleton: false,
  requiredPermissions: ["playtest:read"],
  requiredIntegrations: [],
  optionalIntegrations: ["unity-playtest-runner"],
  serializeState: serializePlaytestEditorState,
  restoreState: restorePlaytestEditorState,
  supportsContextBinding: true as const,
  supportedStates,
};

export const playtestEditors: EditorDefinition<
  PlaytestEditorState,
  PlaytestEditorProps
>[] = [
  {
    ...common,
    id: "playtest.game-view",
    title: "游戏画面",
    icon: "gamepad",
    defaultPlacement: "center",
    minWidth: 480,
    minHeight: 300,
    load: () => import("./editors/GameViewEditor.ts"),
  },
  {
    ...common,
    id: "playtest.agent-monitor",
    title: "代理监控",
    icon: "bot",
    defaultPlacement: "right",
    load: () => import("./editors/AgentMonitorEditor.ts"),
  },
  {
    ...common,
    id: "playtest.trajectory",
    title: "轨迹",
    icon: "route",
    defaultPlacement: "center",
    load: () => import("./editors/TrajectoryEditor.ts"),
  },
  {
    ...common,
    id: "playtest.step-log",
    title: "步骤日志",
    icon: "list",
    defaultPlacement: "bottom",
    load: () => import("./editors/StepLogEditor.ts"),
  },
  {
    ...common,
    id: "playtest.issue-browser",
    title: "问题浏览器",
    icon: "alert-octagon",
    defaultPlacement: "right",
    load: () => import("./editors/IssueBrowserEditor.ts"),
  },
  {
    ...common,
    id: "playtest.regression",
    title: "回归比较",
    icon: "compare",
    defaultPlacement: "center",
    minWidth: 420,
    load: () => import("./editors/RegressionEditor.ts"),
  },
];
