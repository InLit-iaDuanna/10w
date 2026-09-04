import {
  restoreEditorState,
  serializeEditorState,
  type EditorId,
} from "../state/editor-state.ts";

const editor = (
  id: EditorId,
  title: string,
  icon: string,
  loader: () => Promise<unknown>,
  minWidth: number,
  minHeight: number,
) => ({
  id,
  title,
  icon,
  category: id.startsWith("build.") ? "build" : "release",
  load: loader,
  defaultPlacement: "center",
  minWidth,
  minHeight,
  singleton: false,
  requiredPermissions: [id.startsWith("build.") ? "build:read" : "release:read"],
  requiredIntegrations: [],
  optionalIntegrations: ["artifact-store", "git", "unity", "build-runner"],
  serializeState: serializeEditorState,
  restoreState: restoreEditorState,
});

export const editorDefinitions = [
  editor(
    "build.matrix",
    "构建矩阵",
    "grid",
    () => import("./BuildMatrixEditor.tsx"),
    520,
    300,
  ),
  editor(
    "build.console",
    "构建控制台",
    "terminal",
    () => import("./BuildConsoleEditor.tsx"),
    520,
    240,
  ),
  editor(
    "release.gates",
    "发布门禁",
    "shield-check",
    () => import("./ReleaseGatesEditor.tsx"),
    420,
    280,
  ),
  editor(
    "release.center",
    "发布中心",
    "package-check",
    () => import("./ReleaseCenterEditor.tsx"),
    560,
    320,
  ),
  editor(
    "release.patch-notes",
    "补丁说明",
    "file-text",
    () => import("./PatchNotesEditor.tsx"),
    440,
    300,
  ),
] as const;
