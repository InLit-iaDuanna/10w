# CodeBuddy CLI 文本适配器

`sceneops_codebuddy` 是对话、设计与概念模块共用的唯一 CLI 进程实现。
公开 `MODEL_IDS`、`available()`、`complete(prompt, model='cli-default')`、
`invoke_json(prompt, model='cli-default', schema=None)` 与 `CodeBuddyFailure`。

安装：应用的统一后端 requirements 包含此本地包；独立模块环境需先安装
`pip install -e integrations/codebuddy-cli`。本机另需安装并登录 `codebuddy`。
模型目录来自本机 2.144.0 帮助已声明的 15 个 ID，不等于账户授权或推理健康检查。

默认模型不传 `--model`，显式选择才传。请求用参数数组及 stdin，输出为 JSON；
120 秒超时，取消或超时终止子进程组，3 秒未退出再强制停止。无自动重试或 Mock 降级。
CLI 从临时空目录启动；禁用工具，启用严格空 MCP，禁止会话持久化；保持默认宿主权限，
不使用 bypass、跳权限参数或 Bridge。结构化设计建议仅允许 JSON Schema 输出，仍无工具权限。
原始 stderr、CLI envelope 和凭据不返回前端。失败提供安装、权限、模型或网络检查方向。

本轮未运行真实推理、CLI 业务请求或测试套件。模型读取仅检查可执行文件存在。

参数依据：[官方 CLI 参考](https://www.codebuddy.ai/docs/cli/cli-reference)。
2026-09-05 只读核对官方文档索引：`--print`、`--output-format json`、`--model`、
`--tools ""`、`--strict-mcp-config`、`--mcp-config`、`--no-session-persistence`、
`--permission-mode default`、`--max-turns`、`--append-system-prompt` 与 `--json-schema`。
网站正文直接打开超时，官方页面搜索索引可读；本机 2.144.0 的帮助输出由整合主代理核实。
