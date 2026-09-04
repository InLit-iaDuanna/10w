export const manifest = {
  schemaVersion: 1,
  id: "conversation-home",
  version: "0.1.0",
  title: "Conversation Home",
  description:
    "Provides the chat-only initial workbench and typed assistant action handoff.",
  status: "active",
  featureFlag: "conversation_home",
  requires: {
    modules: ["core-kernel", "module-runtime"],
    integrations: [],
    optionalIntegrations: ["llm-provider"],
  },
  permissions: ["conversation:read", "conversation:write"],
} as const;
