# SceneOps AI Provider

`sceneops_ai_provider.ProviderService` 是统一应用唯一的文本模型边界。默认服务是本机
CodeBuddy Code CLI；也可由用户明确切换到 OpenAI-compatible Chat Completions 服务。
服务不探测网络、不自动切换服务、不重试、不回退 Mock，也不读取其他应用的凭据。

## 公共接口

```python
service = ProviderService(database_path, secrets_path=None)
result = await service.generate(prompt, model=None, schema=None, purpose='chat')
text = await service.complete(prompt, model=None, schema=None, purpose='chat')
value = await service.structured(prompt, schema, model=None, purpose='planning')
settings = service.settings()
models = service.models()
```

`generate()` 返回独立的 `ProviderCompletion(text, provider, model, latency_ms, usage,
structured)`，不会用共享 `last_result` 串联并发请求。服务端没有使用量时 `usage` 为 `None`，
不伪造 token 或费用。`complete()` 和 `structured()` 是兼容委托。

## 设置与密钥

设置元数据与既有聊天设置保存在同一个 SQLite。迁移会保留原 `model`，将它作为 CLI 模型；
切换服务时分别保留 CLI 与 compatible 模型选择。公开设置只包含 `provider`、`model`、
`base_url` 和 `api_key_configured`。

API Key 只通过设置写请求进入服务，默认保存为数据库同目录下的
`ai-provider-secrets.json`，文件权限为 `0600`；可通过构造参数传入另一个应用本地路径。
读取时若权限过宽会阻止使用。响应、异常和模型提示词都不包含 Key。不要把密钥文件加入 Git。

密钥按精确的 `base_url` 存入 `endpoints` 映射。更改 URL 不会复用其他地址的 Key；设置事务只在密钥原子写入成功后提交。一次请求使用同一配置快照读取对应 Key 与目标地址。密钥文件是本机敏感数据，不是系统钥匙串或加密保险库。

兼容地址拒绝嵌入用户名/密码、查询参数和片段。外部地址必须使用 HTTPS；`localhost`、
`127.0.0.0/8` 和 `::1` 等回环地址允许 HTTP。请求固定发送到
`<base_url>/chat/completions`，使用 Bearer Key、`messages` 和所选 `model`；不跟随重定向。
响应只读取 `choices[0].message.content`。明确传入 schema 时发送 Chat Completions
`json_schema` response format，不会在服务不支持时盲目改成普通请求。

## CodeBuddy 约束

CLI 调用仍使用 `--tools ''`、严格空 MCP、`--no-session-persistence`、默认权限模式和临时空目录，
不使用 bypass、continue、resume 或 Bridge。取消和超时会结束进程组。JSON envelope、退出码、
登录、额度、模型权限及网络错误会归一化成有限的安全错误，不回传原 stdout/stderr。

模型目录只是建议项，不能证明 CLI 登录或 compatible 服务的模型权限。真实能力在用户发送时验证。
初始 V5 组合应用只做启动与只读空态烟测；用户随后明确授权 CLI 模型验证，见根 `AI_LIVE_VERIFICATION.md`。CLI 结构化回复由共享适配器严格 JSON Schema 校验，保持无工具权限；OAI-compatible 的 schema 参数保持原实现。本轮未配置或请求真实 compatible 服务，不能据 CLI 通过推断 OAI 已验证。
