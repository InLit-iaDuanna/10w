import type { LogicEditorState } from "../editors/editorTypes.ts";

export const editorStateFixtures: Record<string, LogicEditorState> = {
  loading: {
    schemaVersion: 1,
    status: "loading",
    mode: "planned",
    contextBinding: { mode: "follow-global" },
    selectedEntityIds: [],
  },
  readyMock: {
    schemaVersion: 1,
    status: "ready",
    mode: "mock",
    contextBinding: {
      mode: "pinned",
      context: { activeFeatureId: "feat_key_door_branch" },
    },
    selectedEntityIds: ["collectible_pickup"],
  },
  failed: {
    schemaVersion: 1,
    status: "failed",
    mode: "blocked",
    contextBinding: { mode: "follow-global" },
    selectedEntityIds: [],
    errorCode: "GRAPH_LOAD_FAILED",
  },
  offline: {
    schemaVersion: 1,
    status: "offline",
    mode: "blocked",
    contextBinding: { mode: "follow-global" },
    selectedEntityIds: [],
  },
};
