# AI 真实连通验证与修复

2026-09-05，用户在反馈「CodeBuddy 返回的 JSON 不是结果对象」后，明确授权测试 `glm-5.3-flash` 或 HY4，让 AI 通路真实可用。本记录是追加授权后的验证，不覆盖或改写最初仅空态烟测的历史。

## 修复

1. CLI 2.144.0 的真实 JSON 输出是消息数组。普通请求实际成功，但原适配器只接受字典。现在接受单结果对象或含唯一末尾 `result` 的消息数组；不采用中间消息、推理内容或不完整序列。
2. 本机 CLI `--json-schema` 模式在 GLM/HY4 上出现挂起；允许唯一的 StructuredOutput 工具仍未解决。只读检查本机安装包发现其结构化完成 promise 在部分失败/中断路径未结束，结果渲染继续等待。没有修改本机 CLI。
3. 统一采用无工具单轮请求：应用专用 `--system-prompt`、`--tools ''`、严格空 MCP、默认权限、临时 cwd、不持久 CLI 会话。结构化任务使用后端 schema 提示、严格 JSON 解析及 `jsonschema` Draft 2020-12 校验，再交由模块 Pydantic 验证；不修补、截取或清洗错误回复，也不自动切换模型或 Mock。
4. 普通聊天不信任意外的 `structured_output` 字段；非有限数字不是合法 JSON，明确拒绝。公开错误不回显原始 CLI 输出、推理或凭据。

官方支持 [JSON 非交互输出](https://www.codebuddy.ai/docs/cli/headless) 与 [自定义系统提示/工具限制](https://www.codebuddy.ai/docs/cli/cli-reference)。数组形状与挂起结论来自本机实测/安装包，而不是把文档示例当成验证结果。应用结构校验使用 [jsonschema 官方算法](https://python-jsonschema.readthedocs.io/en/stable/validate/)。

## 已取得的实际结果

| 检查 | 实际结果 |
| --- | --- |
| GLM CLI 文本 | 正常退出，末尾 success，回复「连接正常」 |
| GLM 公开聊天 API | 返回 live 回复，并能从 conversation API 读回相同记录 |
| GLM 模块建议 API | 返回集成运维的真实文字建议 |
| GLM 意图理解与计划 | 实际模型生成结构化对象，通过 schema / Pydantic / Pipeline 验证 |
| GLM 单专家分析 | 实际产生两条建议，step=succeeded、run=completed；没有工具或制作操作 |
| 最终计划专项复查 | 计划 valid；1 次专家调用，25,213 ms，Run completed；读回 5 条持久事件；production_operations=0 |
| 4301 浏览器发送 | 保留原选中的 glm-5.3-flash，发送标注「连接验证（开发助手）」的消息，页面显示并保存 live 回复「连接正常」 |
| 定向离线回归 | CLI 解析/工具边界/结构校验 10 项；Provider 接线 2 项，均通过 |

## 失败与限制

- GLM 复查中发生过非纯 JSON 回复、额外字段导致的 schema 拒绝。均明确失败，没有伪造成成功。之后调整系统提示，明确输出格式由应用合同决定，且将完整 schema 紧跟在任务末尾；没有放宽校验。这说明严格校验的失败路径生效，也说明一次完成不等于结构化生成成功率已评估。
- HY4 的简单文本回复成功，但模块建议请求达到 120 秒超时；不标为稳定可用，不更改用户默认模型。
- CLI 原生结构化模式的诊断请求超时后由适配器停止进程组；没有通过增加文件/命令/MCP 权限绕过。
- 初次隔离验证的应用 Run 已 completed，但验证脚本误把运行终态写成 step 的 succeeded，导致脚本断言失败；已依据内核公开状态修正。不能将该脚本首次退出码当作通过。
- 最终专项调用执行修正后的验证函数，仅加透传的失败诊断观察，没有替换模型或修改模型输出；正常退出 0。此前失败记录全部保留在本节，不把最终一次成功表述为连续稳定性通过。
- token / 金额记账仍可能不完整，Run 保留未知；本次单步骤验证显式限制一次模型调用，不宣称金额预算经过验证。
- 未验证真实 OAI-compatible 服务、完整回归、安全/性能套件、生产构建、Blender、Unity、渲染或 AI playtest。没有运行游戏 demo 或制作案例。模型内容的事实质量需人工审阅。

## 数据与复查命令

API 验证使用短期临时 SQLite 项目，结束自动清理，不写入用户项目。4301 只新增了一组明确标注的连接验证聊天记录，保留原项目和设置。

手动、明确授权时才运行以下命令；不会由 `pnpm dev` 自动调用：

```sh
node scripts/python.mjs integrations/codebuddy-cli/tests/test_output.py
node scripts/python.mjs integrations/ai-provider/tests/test_cli_completion.py
node scripts/python.mjs scripts/smoke-ai-live.py --model glm-5.3-flash --confirm-live
```

最后一条最多发起五次真实请求，`--plan-only` 仅检查计划与单专家步骤（三次请求）；无自动重试。使用临时数据和实际模型，不是 Mock。浏览器证据位于 Git 忽略的 `output/playwright/v5-ai-live-chat.png`。
