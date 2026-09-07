# SceneOps AI Provider

`sceneops_ai_provider.ProviderService` 是统一应用唯一的文本模型边界。默认服务是本机
CodeBuddy Code CLI；也可由用户明确切换到官方 Codex CLI，或支持 Chat Completions / Responses API
的 OpenAI-compatible 服务。除非用户主动点击获取模型、检查连接或发送消息，否则服务不探测网络；
它不自动切换接口、不重试、不回退 Mock，也不读取其他应用的凭据。

## 公共接口

```python
service = ProviderService(database_path, secrets_path=None)
result = await service.generate(prompt, model=None, schema=None, purpose='chat', on_event=None,
                                instructions=None)
text = await service.complete(prompt, model=None, schema=None, purpose='chat')
value = await service.structured(prompt, schema, model=None, purpose='planning')
settings = service.settings()
models = service.models()
discovered = await service.discover_models(provider, base_url=None, api_key=None)
probe = await service.check_connection(provider, model, base_url=None, api_key=None,
                                       api_protocol='chat-completions', streaming=True)
```

`generate()` 返回独立的 `ProviderCompletion(text, provider, model, latency_ms, usage,
structured)`，不会用共享 `last_result` 串联并发请求。服务端没有使用量时 `usage` 为 `None`，
不伪造 token 或费用。`complete()` 和 `structured()` 是兼容委托。

`purpose` 现在参与可信产品指令选择：聊天、建议和规划保持只读，`agent-action` 允许模型在调用者给出的能力合同中选择下一项应用动作，但模型本身仍没有工具权限。需要叠加角色或按需技能的产品运行时可传入服务端构造的 `instructions`；三种 provider transport 只承载该指令，不从用户消息推断业务身份、授权或预算。

`generate` 可接收异步 `on_event(event)`；事件只有 `type` 与 `text`，类型是
`text_delta`、`reasoning_delta` 或 `status`。逐事件等待回调，调用方可在模型结束前推送到客户端；
取消、超时或回调失败会停止请求。最终返回值仍为权威的完整回复，流中片段不代表成功或结构校验通过。
CodeBuddy 使用本机帮助确认的 `stream-json` / `--include-partial-messages`，只转发实际模型增量；
Codex 0.144.1 JSONL 只有已完成的文字/推理条目，因此按条目显示，不能宣称逐 token 到达。
兼容服务按保存设置使用标准 Chat Completions SSE `delta.content`，或 Responses API
`response.output_text.delta` / `response.completed`，不读取非标准隐藏推理字段。
没有提供方推理事件时不生成、不补写思考内容，也不在提示中索取思维链。
流读取有 4 MiB 上限，不转发 CLI stderr、工具输出、签名、凭据或原始事件对象。
新增确定性分片/错误/字段筛选 fixtures 已维护；本轮运行一个 Responses SSE 增量与完成事件用例，
以及一个模型目录获取/持久缓存用例；未调用真实模型或外部 compatible 服务。

## 设置与密钥

设置元数据与既有聊天设置保存在同一个 SQLite。迁移会保留原 `model`，将它作为 CLI 模型；
切换服务时分别保留 CodeBuddy、Codex 与 compatible 模型选择。公开设置包含 `provider`、`model`、
`base_url`、`api_key_configured`、`api_protocol`、`streaming` 和 `alignment_detail`；不包含密钥值。
`alignment_detail` 为全局对齐偏好：`concise`、`standard`、`deep`，由策划与建模对话解释为
最多 2、4、8 个结构化关键问题；达到上限后必须收束为摘要，而不是继续追问。

API Key 只通过设置写请求进入服务，默认保存为数据库同目录下的
`ai-provider-secrets.json`，文件权限为 `0600`；可通过构造参数传入另一个应用本地路径。
读取时若权限过宽会阻止使用。响应、异常和模型提示词都不包含 Key。不要把密钥文件加入 Git。

密钥按精确的 `base_url` 存入 `endpoints` 映射。更改 URL 不会复用其他地址的 Key；设置事务只在密钥原子写入成功后提交。一次请求使用同一配置快照读取对应 Key 与目标地址。密钥文件是本机敏感数据，不是系统钥匙串或加密保险库。

兼容地址拒绝嵌入用户名/密码、查询参数和片段。外部地址必须使用 HTTPS；`localhost`、
`127.0.0.0/8` 和 `::1` 等回环地址允许 HTTP。Chat Completions 请求发送到
`<base_url>/chat/completions`，Responses 请求发送到 `<base_url>/responses`；模型目录从
`<base_url>/models` 获取。请求使用 Bearer Key 且不跟随重定向。Responses 请求显式使用
`store: false`；结构化结果分别使用 Chat Completions 的 `response_format.json_schema` 或 Responses
的 `text.format`，服务拒绝时不会自动换接口或降级成普通请求。

`discover_models()` 对 compatible 服务执行一次只读模型目录请求；CLI 只返回本机候选目录，不能证明
账户模型权限。成功结果按 provider 与完整服务地址写入本地非敏感目录缓存，供主模型下拉复用；缓存不含
API Key，且不会把该服务设为当前提供方。`check_connection()` 按当前模型、接口格式与流式开关发送一次最小文字请求，可计入提供方
额度；成功意味着本次真实请求完成，启用流式时还必须实际收到文字增量。草稿密钥只参与该次请求，不会
因为检查成功而保存。

## CodeBuddy 约束

CLI 调用仍使用 `--tools ''`、严格空 MCP、`--no-session-persistence`、默认权限模式和临时空目录，
不使用 bypass、continue、resume 或 Bridge。取消和超时会结束进程组。JSON envelope、退出码、
登录、额度、模型权限及网络错误会归一化成有限的安全错误，不回传原 stdout/stderr。

## Codex 约束

提供方 ID `codexcli`，执行本机官方 `codex exec --json`，支持 `cli-default` 或显式 `--model`，以 stdin 传入应用保存的上下文。CLI 自行复用终端登录，应用不读取或复制认证文件。CodeBuddy 的模型目录不会传入 Codex；自定义模型可在设置输入，不代表账户已有权限。

本轮核实版本为 `codex-cli 0.144.1`。用 `--ignore-user-config`、`--ignore-rules` 和 `CODEX_EXEC_SERVER_URL=none` 创建无执行/文件环境，另禁用 Shell、MCP、技能、插件、应用、浏览器及子代理能力。保留只读 sandbox；不使用 bypass 或第三方 Bridge、不修改全局配置。确切版本的源码证据在 `codex_cli.py` 文件头；不同版本会明确拒绝，需复核隔离合同后再支持。内部 `update_plan` 仍可能存在，但不能操作工程，不能宣称工具列表完全为空。

JSONL 仅取完成的 assistant 文字与 usage；结构化动作继续经应用 JSON Schema 验证。输出有界、超时与取消停止进程组；错误不暴露原始输出和凭据，不自动重试/换提供方。官方流程参考 [非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)。

新增 transport 主路径与 provider 往返切换各运行一个替身烟测；实际 CLI 参数通过无认证/无模型执行的配置解析检查。随后用户授权完整权限及真实测试，`gpt-5.6-sol / low` 最小文件创建/读回通过。其他新增边界用例仅维护、未全套运行。详见根 `CODEX_PROVIDER_HANDOFF.md`。

`ProviderService.execute_task(goal, workspace_root, model, authorized_scope, timeout)` 是仅供任务授权服务调用的升权接口，普通 generate/chat 不会调用。其 Codex `invoke_agent` 显式启用原生文件/Shell，保留全局外部集成禁用；服务端范围单独作为 developer 指令传入，用户目标不能覆盖。`danger-full-access` 不限制目录外访问，调用者必须在卡片说明并取得明确同意。一次 CLI 调用可能包含多次模型请求，不宣称原 8 次预算仍适用；失败不自动重试，退出只标待审阅而非验收。

该升权接口新增可选 `on_event: Callable[[dict], Awaitable[None]]` 与 `allow_image_generation=False`。
`on_event` 在进程仍运行时按 JSONL 顺序调用并等待调用方持久化；不等待完整回复后才发事件。
事件仅包含 CLI 生成的 `item_id`、类型、阶段、有限状态，以及标为 `reported` 的计划步骤序号/完成报告。
不转发命令、工具 stdout/stderr、推理或任意计划正文。`file_change` 的候选文件必须在当前任务根内真实存在，
拒绝符号链接、隐藏文件及越界路径；只发送相对路径和存在事实，不表示文件可用或业务验收通过。
调用方须在读取候选文件时再次验证边界和存在性。回调异常、取消和超时都会停止 CLI；不自动重试。

图像生成只有在服务端任务授权明确包含图像权限且传入 `allow_image_generation=True` 时启用 Codex 原生
`features.image_generation`，继续使用 CLI 登录，不读取 API Key、不加载全局插件、不切换其他服务。
账户或模型不支持时保留实际失败，不做 API 回退。模型被要求将真正生成的图片复制到任务目录，保留原图。
0.144.1 的 `exec --json` 不输出原生图像条目或图像字节，因此适配器不伪造图像事件或解码猜测字段；
图片候选只能来自真实现存的任务文件，运行时可另行执行受授权的目录产物核验。
依据：[固定版本 JSONL 合同](https://github.com/openai/codex/blob/rust-v0.144.1/codex-rs/exec/src/exec_events.rs#L104)、
[条目映射](https://github.com/openai/codex/blob/rust-v0.144.1/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L141)。
本次仅运行一个分片流事件替身烟测，确认进程结束前收到脱敏事件；未追加真实 AI 或图像生成调用。

模型目录只是建议项，不能证明 CLI 登录或 compatible 服务的模型权限。真实能力在用户发送时验证。
初始 V5 组合应用只做启动与只读空态烟测；用户随后明确授权 CLI 模型验证，见根 `AI_LIVE_VERIFICATION.md`。CLI 结构化回复由共享适配器严格 JSON Schema 校验，保持无工具权限；OAI-compatible 的 schema 参数保持原实现。本轮未配置或请求真实 compatible 服务，不能据 CLI 或确定性协议 fixture 通过推断外部服务已验证。
