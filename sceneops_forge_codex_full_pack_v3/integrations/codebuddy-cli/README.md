# CodeBuddy CLI 文本适配器

`sceneops_codebuddy` 是统一 provider、设计与概念兼容适配器共用的唯一 CLI 进程实现。
公开 `MODEL_IDS`、`available()`、`complete(prompt, model='cli-default')`、
`invoke_json(prompt, model='cli-default', schema=None)` 与 `CodeBuddyFailure`。

安装：应用的统一后端 requirements 包含此本地包；独立模块环境需先安装
`pip install -e integrations/codebuddy-cli`。本机另需安装并登录 `codebuddy`。
模型目录来自本机 2.144.0 帮助已声明的 15 个 ID，不等于账户授权或推理健康检查。

默认模型不传 `--model`，显式选择才传。请求用参数数组及 stdin，输出为 JSON；
120 秒超时，取消或超时终止子进程组，3 秒未退出再强制停止。无自动重试或 Mock 降级。
CLI 从临时空目录启动；禁用工具，启用严格空 MCP，禁止会话持久化；保持默认宿主权限，
不使用 bypass、跳权限参数或 Bridge。使用应用专用 `--system-prompt`，避免默认编码代理提示与纯建议/纯 JSON 回复冲突。

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
