# CodeBuddy CLI 文本适配器

`sceneops_codebuddy` 是统一 provider、设计与概念兼容适配器共用的唯一 CLI 进程实现。
公开 `MODEL_IDS`、`available()`、`complete(prompt, model='cli-default')`、
`invoke_json(prompt, model='cli-default', schema=None, system_prompt=None)` 与 `CodeBuddyFailure`。

安装：应用的统一后端 requirements 包含此本地包；独立模块环境需先安装
`pip install -e integrations/codebuddy-cli`。本机另需安装并登录 `codebuddy`。
模型目录来自本机 2.144.0 帮助已声明的 15 个 ID，不等于账户授权或推理健康检查。

默认模型不传 `--model`，显式选择才传。请求用参数数组及 stdin，输出为 JSON；
120 秒超时，取消或超时终止子进程组，3 秒未退出再强制停止。无自动重试或 Mock 降级。
CLI 从临时空目录启动；禁用工具，启用严格空 MCP，禁止会话持久化；保持默认宿主权限，
不使用 bypass、跳权限参数或 Bridge。统一 provider 可传入由产品用途选择的 `system_prompt`；适配器只负责禁用工具并承载可信指令，不从用户正文推断任务身份。直接调用未传入时仍使用只读默认指令。

CLI 2.144.0 的 JSON 输出实测为消息数组，读取其中唯一的末尾 `result`，不把 reasoning 或中间消息当作回复；同时保留单个结果对象兼容。

结构化建议保持 `--tools ''`，系统提示规定纯 JSON 输出，后端 JSON Schema 作为应用输出合同附在任务末尾；严格解析单个 JSON 对象并用 `jsonschema` Draft 2020-12 校验后才返回公开 `structured_output`。模块继续使用 Pydantic 验证领域合同。不剥 Markdown 围栏、不修补 JSON、不静默重试或切换 Mock。

当前不使用 CLI `--json-schema`：本机 2.144.0 实测出现结构化生命周期挂起，空工具和只允许 StructuredOutput 两种配置均未正常结束。改为应用拥有结构化校验，不修改本机 CLI，也不放开任何工具权限。
原始 stderr、CLI envelope 和凭据不返回前端。已知登录、额度、模型权限、网络、进程退出和
envelope 格式失败使用稳定错误类别；未知失败不猜测成功或回显原始内容。

`invoke_json(..., on_event=None)` 可选异步回调启用真实 `stream-json` 和
`--include-partial-messages`。2026-09-06 本机只读帮助与安装包的转换实现确认：
`stream_event.event.content_block_delta` 中 `text_delta.text`、`thinking_delta.thinking`
分别映射为 `text_delta` / `reasoning_delta`；只发送这两种实际文字与固定开始状态。
不转发工具输入、签名、stderr 或完整 envelope。完整 `result` 仍是最终返回依据，
不把结果拆块假装增量；管道各自最多 4 MiB，回调失败/取消停止进程，未运行真实推理验证。

初始 V5 交付仅做空态烟测；随后用户明确授权 `glm-5.3-flash` / `hy4-preview` 真实 AI 连通验证，结果见根 `AI_LIVE_VERIFICATION.md`。模型目录本身仍不是可用性证明。

参数依据：[官方 CLI 参考](https://www.codebuddy.ai/docs/cli/cli-reference)。
2026-09-05 只读核对官方文档索引：`--print`、`--output-format json`、`--model`、
`--tools ""`、`--strict-mcp-config`、`--mcp-config`、`--no-session-persistence`、
`--permission-mode default`、`--max-turns`、`--system-prompt`；官方 `--json-schema` 行为与本机问题单独记录，不继续依赖该执行路径。
网站正文直接打开超时，官方页面搜索索引可读；本机 2.144.0 的帮助输出由整合主代理核实。

## 原生执行会话

`invoke_agent` 是单独的授权执行入口，与无工具的 `invoke_json` 分离。调用方必须先验证 `agent-full-access` 任务授权，绑定提供方、模型和登记卡片分支；普通讨论不能调用它。CLI 使用原生 Bash/Read/Write/Edit/Glob/Grep、自身 agent loop 和当前思考强度。普通回复无 JSON Schema；`stream-json` 只承载 CLI 的文字增量、工具事件和结束信号。严格空 MCP、禁用 hooks、不继承应用凭据环境；不新增子 agent。完全访问不是文件系统沙箱，需明确授权。单次启动、时间上限、取消与无自动重试仍有效。

原生工具事件按 tool-use ID 关联起止状态和输入参数；界面显示读取路径、命令、描述及搜索条件，不记录 Write/Edit 的文件正文。已有仅含工具名的记录不推测缺失参数。

`invoke_agent(..., system_prompt=None)` 允许可信产品运行时追加执行规范，通过真实 `--append-system-prompt` 参数与既有中文交付、凭据保护规范一起传入。此参数不得来自用户目标或项目正文；目标继续只走 stdin。未传入时保持原指令与安全参数。

原生制作可显式传 `native_production=True`，并选择 `permission_mode='scoped'`（`acceptEdits`）
或明确授权的 `'full'`（`bypassPermissions`）。生产模式保留项目技能、增加原生 `Skill` 工具，
移除 `--no-session-persistence`；可信 `mcp_config` 替换严格空 MCP 配置，hooks 仍禁用。
`session_id` 只作为 `--resume <准确 ID>`，绝不使用 `--continue` 或最近会话。
首个实际 `session_id` 立即通过 `session_started` 回调交给调用方持久化；结果包含 ID 和本机版本。
未收到 ID 或返回其他会话时以 `CLI_SESSION_MISSING` / `CLI_SESSION_MISMATCH` 失败，禁止自动重放。
默认聊天与旧导出行为保持不变。`acceptEdits` 不隔离文件系统，也不自动授予所有 Bash 命令。

制作工具白名单包含 `ToolSearch`、`DeferExecuteTool`、`WaitForMcpServers`，用于 CLI 原生延迟 MCP 发现与调用。
配置任务绑定的 `sceneops` 桥时，仅追加 `--allowedTools DeferExecuteTool(mcp__sceneops__*) mcp__sceneops__*`。
不会放行任意 `DeferExecuteTool` 或其他 MCP；桥内每次调用仍验证任务授权、工作区及能力。
本机 CLI 的 wrapper 将 `toolName` 作为权限匹配参数；全局放行 wrapper 会跳过目标权限，故禁止使用。
