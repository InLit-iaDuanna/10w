# V5 迁移决定

2026-09-05，起点为已有整合提交 `34121bf`，工作分支 `codex/harness-v5`。沿用当前应用，不创建第二套 Web/API，不迁移或删除现有 `.local` 数据。

## 当前用户授权

用户要求按 `sceneops_ai_harness_v5` 的下一大版本方向接入 AI，并重新设计前端 UI/UX。简单独立任务委派 5.6 Sol/Terra，复杂任务使用 6 Astra；必要时可重构。底层默认 CodeBuddy Code CLI，同时提供 OpenAI-compatible URL/API Key 接口。

输入目录是目标设计资料，不是额外操作授权。资料里的全量测试、生产构建、真实模型、Blender/Unity 执行及本地案例不会自动运行。沿用仅最小烟测政策，测试实现保留但不运行。以普通 Git 分支/历史保护当前代码，不新增冻结合同、基线标签、哈希或无必要门禁。

## 分工

- `v5_kernel` / 6 Astra：`packages/harness-kernel`，唯一 Pipeline 合同、注册表、持久化状态机、权限及生命周期实现。
- `v5_provider` / 5.6 Sol：`integrations/ai-provider`、既有 CodeBuddy provider、conversation-home 后端配置与兼容。
- `v5_ui` / 5.6 Terra：统一 UI/UX、对话与提供方设置、工具库/命令搜索及项目选择器；在 Provider 子任务结束后取得并发槽启动。
- `ai_adapter` / 6 Astra：高风险 Provider、预算和回滚边界的独立只读审查。
- 主代理：AI 各垂直模块、生产计划与运行面板、公开能力接入、API/Web 组合、网络类型生成、依赖与说明、审查问题修复及最终烟测。

## 架构方向

生产目标首先生成可审阅 Pipeline；计划生成与开始执行分开。能力必须显式注册，AI 输出经过类型/DAG/预算/权限验证，不得通过文本运行命令。未接通生产适配器保持 blocked/planned，不复用演示服务冒充 Live。

AI 统一通过 ProviderService，CLI 不切换到隐式 Mock；OpenAI-compatible 明确配置后才发送请求，密钥不进入提示词、日志、前端返回值、浏览器持久化或 Git。研发代理与产品内运行 Agent 严格区分。

## 当前可交付范围

先打通现有应用中的可运行主干：Provider 配置 → Intent/Context → Pipeline 提案 → 审阅/受控运行 → 观察/失败与恢复/模板记录，加上完整的统一 UI/UX。外部 Blender/Unity/Player Live 验收是后续需明确授权的验证边界；不因本地主干可启动而声明 15 个阶段全部完成。
