export const manifest = {
  schemaVersion: 1,
  id: "ai-playtest",
  version: "0.1.0",
  title: "AI Playtest",
  featureFlag: "ai_playtest",
  optionalIntegrations: ["unity-playtest-runner", "artifact-store", "llm-provider"],
} as const;
