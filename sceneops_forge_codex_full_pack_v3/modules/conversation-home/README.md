# Conversation Home

真实 `assistant.conversation` 编辑器，包含对话记录、草稿、取消/重试、结构化动作卡、布局预览确认、上下文和执行模式。独立 Web 运行方式见 [Shell 工作台](../../apps/labs/shell/README.md)。

## 公共接口

只导入 `frontend/src/index.ts`：ModuleContribution、assistantConversationEditor、ConversationController/Repository、createConversationEditorRuntime、AssistantActionCoordinator、transport 和 action 类型/validator。UI 协议来自 `@sceneops/core-ui`；manifest 由 module-runtime 从 module.yaml 生成。

`ConversationTransport` 是可替换的端口。`LocalConversationTransport` 是明确标注的固定 MOCK；`CodeBuddyConversationTransport` 提供选择模型后的本地 API 请求。`ConversationEditor` 接收可选 modelTransport，模型目录由 TanStack Query 管理；请求/响应类型由 Pydantic/OpenAPI 生成。后端只通过公开 `conversation_home.router` 组合。

默认 `{ mode: 'tab' }` placement；Home preset 决定对话独占画布，四边拉手归 Forge Shell。对话不注册第二套命令总线。

## 行为与安全

- 输入“打开工具库”/“打开命令搜索”只在 MOCK 下产生结构化提案；总是先预览、明确确认，再转交真实 WorkbenchCommandBus handler。
- 真实 CodeBuddy 回复仅为文本；不将自由文本解释成工具命令。CLI 使用空工具列表、空严格 MCP 配置、默认宿主权限规则，不使用 bypass 参数。
- 项目对话由持久存储管理，pre_project 由 sessionStorage 管理；布局只存编辑器草稿和附件元数据。
- 附件 adapter 未接入时显示 blocked；React 不读取生产项目或执行 CLI。
- 默认 MOCK、选中真实模型但未发送为 planned、实际 CLI 完成才 live；失败显示 blocked 且允许重试，无静默降级。

## 验证

本轮仅公共导入、API/浏览器启动检查，以及“MOCK 提案→预览→确认→右侧真实工具库”这一条本地路径。`frontend/src/tests/local-transport.test.ts` 已维护成功与失败案例，**not run / pending approval**；原完整单元/组件/E2E/类型检查亦未运行。CodeBuddy 推理未运行，不能把可执行文件存在/模型目录成功当成登录成功。

## Limitations

当前 CLI adapter 每次仅发送当前消息，不复用 CLI 会话；JSON 完整结果尚未转换成 token 级流。真实 provider、生产审批、项目/工作流/产物等 handler 由其他模块提供。当前 lab 仅注册 Shell 工具，外部业务不可冒充成功。
