# Conversation Home

## 统一应用接口（本轮）

即时发送：临时用户消息由 `outgoingConversation` 管理，发送立即清空输入且允许继续写下一条；失败/取消保留原消息供手动重试，不覆盖新草稿。成功更新服务端历史缓存并移除临时消息，取消只表示停止等待，不能保证服务端未保存。临时消息不写数据库。受控请求测试见 `e2e/README.md`，最新记录见根 `INTERACTION_POLISH_VERIFICATION.md`。

聊天视觉进一步简化：无欢迎卡片，中性灰消息区与单层圆角输入框；「＋」选择明确保存的上下文，模型和设置为紧凑工具栏，计划入口移至右上对话选项。`UnifiedModelPicker` / `ModelProviderSettings` 新增可选 `compact` 外观参数，默认仍保留独立使用样式；网络和密钥保存语义不变。键盘提交与按钮统一要求历史已读取。

最新 UI 使用紧凑底部输入：Enter 提交、Shift+Enter 换行，IME composing 不提交；输入自适应高度，失败保留草稿，取消/重试仍由原 API 实现。浏览器失败与取消仅用 Mock 网络响应测试，不实际请求模型。旧 Node 测试 40/42，通过与运行器限制见根 `UI_FUNCTIONAL_VERIFICATION.md`。

`UnifiedConversation({context, onDirtyChange?})` 与 `AIAdvicePanel({context,moduleId,onDirtyChange?})`
由宿主的同一个 QueryClient 和编辑器注册系统承载。统一应用默认 CodeBuddy `cli-default`，
无自动 Mock、推理、工具执行或案例载入。旧编辑器及 transport 保留给独立 lab，以下旧默认 MOCK
描述只适用于旧入口，不适用于统一应用。

公开后端 `create_ai_router(database_path, project_exists=callback, secrets_path=None)` 组合：

- `GET /api/ai/models`：CLI 候选与已配置 compatible 模型目录；只报告本地设置，不探测网络。
- `GET/PUT /api/ai/settings`：全局 provider、模型和 base URL 设置；API Key 只写，响应只返回
  `api_key_configured`，同时保存流式开关与 compatible 接口格式。默认 CodeBuddy CLI，不自动切换
  compatible、接口格式或 Mock。
- `POST /api/ai/provider/models`：使用弹窗当前草稿配置获取模型；compatible 调用 `/models`，CLI
  返回本机候选目录。该操作不会保存草稿配置。
- `POST /api/ai/provider/check`：按当前模型、接口格式和流式开关发送一次最小真实请求；可能计入提供方
  额度，成功也不会保存草稿配置。
- `GET /api/ai/conversation?project_id=...`：按项目查询；省略参数为独立的 pre_project 本地会话。
- `POST /api/ai/chat`：`{project_id,message,context}`，读取已保存历史和明确选择的对象 ID；成功的问答原子保存。
- `POST /api/ai/chat/stream`：返回 `text/event-stream` 的 `status`、`text_delta`、`complete` 或 `error`
  JSON 事件；只有完整成功后才保存问答，中断片段明确标记为未完成、未保存。
- `POST /api/ai/advice`：`{project_id,module_id,prompt,context}`，只返回文字建议，无任何采用/执行端点。

模块只拥有 `conversation_ai_settings`、`conversation_ai_messages` 和
`conversation_ai_model_catalog` 三张 SQLite 表；最后一张只缓存用户主动获取、并按 provider 与完整
服务地址隔离的非敏感模型目录。失败和取消
不追加伪回复；输入仍留在前端供重试。项目切换卸载并取消请求，历史 query 按项目隔离；
输入草稿以 `onDirtyChange` 提醒宿主，非持久面板数据不写数据库。pre_project 也本地持久化，
以本轮用户批准的方案为准。

统一 API 使用 `sceneops_ai_provider.ProviderService`；旧设计/概念 API 继续通过兼容层复用
`sceneops_codebuddy`。调用与密钥边界见 integrations/ai-provider/README.md。
旧 `/api/conversation/*`、独立设计与概念建议端点保留，主 API 不重复注册概念旧 `/api/ai/*`。
概念/设计业务建议语义保留，统一建议标明待人工采用。

10 个工作台组各自有业务建议提示词；`concept-assets` 与 `project-planning` 复用概念/设计
提示词并扩展资产交接/制作规划。模块建议默认不传草稿，必须勾选“附带当前已保存草稿”。
主聊天默认“不附带草稿”，只有手动选择模块后才读取该项目的已保存草稿并随下一次发送附带；
不读取项目文件，不包含未保存编辑内容，不因选择草稿自动请求模型。

网络合同：安装本地 `integrations/ai-provider` 后运行 `backend/export_unified_contracts.py` 导出 `contracts/unified-ai.openapi.json`，
再用根 `openapi-typescript` 生成 `frontend/src/generated/unified-ai-api.ts`，不要手抄类型。
`backend/tests/test_unified_ai.py` 覆盖空态、隔离、持久化、默认模型、禁工具、失败不泄漏 stderr、取消；
本轮 **未运行**。真实 CLI 推理、完整类型检查、构建、测试套件均未运行。

真实 `assistant.conversation` 编辑器，包含对话记录、草稿、取消/重试、结构化动作卡、布局预览确认、上下文和执行模式。独立 Web 运行方式见 [Shell 工作台](../../apps/labs/shell/README.md)。

## 公共接口

只导入 `frontend/src/index.ts`：ModuleContribution、assistantConversationEditor、ConversationController/Repository、createConversationEditorRuntime、AssistantActionCoordinator、transport 和 action 类型/validator。UI 协议来自 `@sceneops/core-ui`；manifest 由 module-runtime 从 module.yaml 生成。

### V5 production harness UI

当前视觉刷新以紧凑欢迎区、文档式回复和单一输入面板为主；模型、提供方、已选上下文在输入下方。提供方仍为原生模态弹窗，兼容服务字段只在明确选择时显示；配置不因打开弹窗或更换未保存选项而生效。窄区域重排控件，错误、取消和重试逻辑保持原样。最新 UI 烟测见根 `UI_REFRESH_SMOKE.md`。

`UnifiedConversation` 可选接收 `onOpenPipeline?: () => void`。它只在宿主提供回调时显示“生产计划”入口；
入口仅打开宿主拥有的计划编辑器，不会从聊天中创建、执行或声称存在生产计划。首页文案明确为“目标 → 计划 → 人工审批”。
Provider 设置支持 CodeBuddy CLI、Codex CLI 和 OpenAI 兼容服务，并提供精简、标准、深入三档对齐详细程度。每个 CLI provider 的 `cli-default` 与模型选择由服务端独立记忆；切换 provider 时前端不携带上一个 provider 的模型。兼容服务必须明确填写 URL 和模型 ID，可选择 Chat Completions 或 Responses API。只有用户主动点击“获取模型”或“检查连接”时才会用未保存草稿探测；连接检查会明确提示可能计费。成功获取的模型目录按 provider 与服务地址缓存在本地；当前已保存连接会立即刷新主输入区的“当前模型”下拉，新连接则在保存后显示。兼容服务的密钥按 URL 配置：更换 URL 而不输入密钥时会显示为未配置。CLI 不显示 API Key 字段。API key 绝不写入 query cache、localStorage、模型目录或 UI 日志，提交成功或关闭弹窗后立即清空输入框。

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

提供方设置扩展另完成 OpenAPI 生成、Python 语法/导入检查、Responses SSE 与模型目录缓存各一个
确定性用例，以及 903×788 浏览器弹窗验收；未由自动验证点击真实“获取模型”或“检查连接”，未调用外部模型。

## Limitations

当前 CLI adapter 每次仅发送当前消息，不复用 CLI 会话；Codex CLI 当前只能按其 JSONL 完成条目输出，
不能宣称逐 token。compatible 服务可按标准 Chat Completions 或 Responses SSE 显示真实文字增量，但是否
支持相应接口与模型取决于目标服务，应用不会自动回退。真实 provider、生产审批、项目/工作流/产物等
handler 由其他模块提供。当前 lab 仅注册 Shell 工具，外部业务不可冒充成功。
