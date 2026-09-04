import type { StructuredLogView } from "../types.ts";

export const mockLog: StructuredLogView = {
  eventId: "log_mock_frontend_01",
  emittedAt: "2026-09-04T00:00:00Z",
  level: "warning",
  sourceModule: "engine-unity",
  sourceTool: "unity",
  workerId: "worker_unity_mock_01",
  message: "Mock worker heartbeat delayed",
  context: {
    projectId: "prj_mock",
    runId: "run_mock",
    jobId: "job_mock",
    correlationId: "corr_mock",
    causationId: "evt_mock",
  },
  fields: { code: "HEARTBEAT_DELAYED", duration_ms: 12000 },
  artifactLinks: [{ artifactId: "art_mock_log_01", label: "Mock worker report" }],
  mode: "mock",
};
