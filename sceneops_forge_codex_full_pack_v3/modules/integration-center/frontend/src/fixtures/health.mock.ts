import type { IntegrationHealthView, LogSummaryView, WorkerView } from "../types.ts";

export const mockHealth: IntegrationHealthView[] = [
  {
    integrationId: "blender",
    displayName: "Blender",
    state: "connected",
    toolVersion: "4.3.2",
    adapterVersion: "0.1.0",
    capabilityIds: ["scene.scan", "asset.export"],
    lastSeenAt: "2026-09-04T00:00:00Z",
    queue: { depth: 0, running: 0 },
    mode: "mock",
    isCurrent: true,
    liveActionsEnabled: false,
    recommendedActions: [
      { commandId: "integration.health.refresh", label: "重新探测", available: true },
      { commandId: "integration.open_logs", label: "查看关联日志", available: true },
    ],
  },
  {
    integrationId: "unity",
    displayName: "Unity",
    state: "incompatible",
    toolVersion: "2022.3.1",
    adapterVersion: "0.1.0",
    capabilityIds: ["project.scan"],
    queue: { depth: 1, running: 0 },
    reason: "缺少能力：build.run。",
    mode: "blocked",
    isCurrent: true,
    liveActionsEnabled: false,
    recommendedActions: [
      {
        commandId: "job.retry",
        label: "重试构建",
        available: false,
        unavailableReason: "工具版本或能力不兼容。",
      },
    ],
  },
];
export const mockLogs: LogSummaryView[] = [
  {
    eventId: "log_health_mock_01",
    integrationId: "unity",
    level: "error",
    message: "Mock capability mismatch",
    correlationId: "corr_mock_01",
    artifactIds: ["art_diag_mock_01"],
    mode: "mock",
  },
];

export const mockWorkers: WorkerView[] = [
  {
    workerId: "worker_unity_mock_01",
    integrationId: "unity",
    displayName: "Unity Worker Mock 01",
    lifecycle: "online",
    healthState: "busy",
    observedAt: "2026-09-04T00:00:00Z",
    expiresAt: "2026-09-04T00:05:00Z",
    isCurrent: false,
    lastHeartbeatAt: "2026-09-04T00:00:00Z",
    workerVersion: "0.1.0",
    capabilityIds: ["build.run"],
    currentJob: {
      jobId: "job_mock_01",
      runId: "run_mock_01",
      correlationId: "corr_mock_01",
      title: "Mock build",
      state: "timed_out",
      progress: 0.6,
      retrySafety: "non_idempotent",
      resumeTokenAvailable: true,
      completedStepIds: ["project.scan"],
    },
    queue: { depth: 1, running: 0 },
    mode: "mock",
    recommendedActions: [
      { commandId: "worker.restart.guidance", label: "查看安全重启说明", available: true },
    ],
  },
];
