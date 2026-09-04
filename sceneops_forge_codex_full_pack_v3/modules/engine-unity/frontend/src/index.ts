import {
  restoreUnityEditorState,
  serializeUnityEditorState,
} from "./editor-state.ts";
import { manifest } from "./manifest.ts";
import type { UnityCommandDefinition, UnityEditorDefinition } from "./types.ts";

const inspectorLoader = () => import("./editors/UnityInspectorEditor.ts");
const buildLoader = () => import("./editors/UnityBuildEditor.ts");

export const editorDefinitions: readonly UnityEditorDefinition[] = [
  editor("unity.inspector", "Unity 检查器", "unity", "right", "unity:read", inspectorLoader),
  editor("unity.prefab.inspector", "Prefab 检查器", "prefab", "right", "unity:read", inspectorLoader),
  editor("unity.build.matrix", "构建矩阵", "build", "center", "unity:build", buildLoader),
  editor("unity.build.console", "构建控制台", "console", "bottom", "unity:read", buildLoader),
  editor("unity.profiler", "性能分析", "profiler", "bottom", "unity:execute", buildLoader),
];

export const commandDefinitions: readonly UnityCommandDefinition[] = [
  command("unity.health", "检查 Unity 连接", "unity:read", false, false),
  command("unity.project.scan", "扫描 Unity 项目", "unity:read", false, false),
  command("unity.asset.import", "导入已发布资产", "unity:write", true, true),
  command("unity.identity.map", "映射稳定身份", "unity:write", true, true),
  command("unity.prefab.upsert", "创建或更新 Prefab", "unity:write", true, true),
  command("unity.game_object.inspect", "检查 GameObject", "unity:read", false, false),
  command("unity.component_property.set", "设置组件属性", "unity:write", true, true),
  command("unity.collider.upsert", "创建或更新碰撞体", "unity:write", true, true),
  command("unity.navmesh.run", "运行 NavMesh 操作", "unity:write", true, true),
  command("unity.play.enter", "进入播放模式", "unity:execute", true, false),
  command("unity.play.exit", "退出播放模式", "unity:execute", true, false),
  command("unity.capture", "捕获 Unity 画面", "unity:execute", true, false),
  command("unity.console.read", "读取 Unity 控制台", "unity:read", false, false),
  command("unity.tests.run", "运行 Unity 测试", "unity:execute", false, false),
  command("unity.profiler.snapshot", "捕获性能快照", "unity:execute", false, false),
  command("unity.build.run", "运行 Unity 构建", "unity:build", true, true),
];

export const moduleContribution = {
  manifest,
  editors: editorDefinitions,
  commands: commandDefinitions,
  navigation: editorDefinitions.map((definition) => ({
    editorId: definition.id,
    group: "渲染与引擎",
    keywords: ["Unity", "Prefab", "构建", "性能"],
    recommendedEdges: [
      definition.defaultPlacement === "center" ? "right" : definition.defaultPlacement,
    ],
  })),
} as const;

export { executionModeLabels, integrationState } from "./editor-state.ts";
export type * from "./types.ts";

function editor(
  id: string,
  title: string,
  icon: UnityEditorDefinition["icon"],
  defaultPlacement: UnityEditorDefinition["defaultPlacement"],
  permission: string,
  load: UnityEditorDefinition["load"],
): UnityEditorDefinition {
  return {
    id,
    title,
    icon,
    category: "engine",
    defaultPlacement,
    minWidth: defaultPlacement === "bottom" ? 480 : 340,
    minHeight: defaultPlacement === "bottom" ? 220 : 280,
    singleton: false,
    requiredPermissions: [permission],
    requiredIntegrations: ["unity"],
    load,
    serializeState: serializeUnityEditorState,
    restoreState: restoreUnityEditorState,
  };
}

function command(
  id: string,
  title: string,
  permission: string,
  mutating: boolean,
  approvalRequired: boolean,
): UnityCommandDefinition {
  return {
    id,
    title,
    requiredPermissions: [permission],
    requiredIntegrations: ["unity"],
    mutating,
    approvalRequired,
  };
}
