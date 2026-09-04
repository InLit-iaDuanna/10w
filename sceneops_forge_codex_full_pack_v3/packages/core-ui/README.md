# Workbench UI contracts

`@sceneops/core-ui` 是编辑器、命令、上下文和停靠布局的 TypeScript 协议。它由原 Forge Shell `contracts.ts` 移动而来，不包含第二套运行时；Forge Shell 公开入口继续转导这些类型，已有消费者可保持原 import。

`conversation-home` 和 Shell 共同使用 `EditorDefinition` / `EditorHostProps`。序列化返回 `JsonValue`；具体编辑器状态通过其 `serializeState/restoreState` 边界处理。网络实体仍由 Pydantic 和生成的 core-contracts 管理，不在此手写复制。
