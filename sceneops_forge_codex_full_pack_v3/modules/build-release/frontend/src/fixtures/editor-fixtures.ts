import type { EditorSnapshot, ViewState } from "../state/editor-state.ts";

export const deterministicEditorStates: Readonly<Record<ViewState, EditorSnapshot>> = {
  loading: { view: "loading", mode: "mock", headline: "正在读取确定性 fixture" },
  empty: { view: "empty", mode: "planned", headline: "尚无发布候选" },
  ready: { view: "ready", mode: "mock", headline: "QA 候选可供模块测试" },
  failed: {
    view: "failed",
    mode: "mock",
    error: {
      code: "DEPLOYMENT_ADAPTER_FAILED",
      message: "确定性模拟失败",
      requestId: "request.fixture.failure",
      retryable: true,
      suggestedActions: ["release.deploy.retry"],
    },
  },
  offline: {
    view: "offline",
    mode: "blocked",
    integrationId: "artifact-store",
  },
  permission_denied: {
    view: "permission_denied",
    mode: "blocked",
    detail: "缺少 release:deploy 权限。",
  },
};

export const cachedLabelContractFixture = {
  recordMode: "cached" as const,
  fixtureMode: "mock" as const,
  originLiveRunId: "run.prior-live.example",
  note: "This tests presentation and provenance fields only; it is not a cached artifact.",
};
