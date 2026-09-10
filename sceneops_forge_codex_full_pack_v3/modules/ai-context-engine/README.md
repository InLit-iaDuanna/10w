# 项目上下文

V5 AI Harness 垂直模块。公开 Python 包：`sceneops_ai_context`；Pipeline 合同来自 `sceneops_harness`，不另复制网络模型。

默认不执行；由明确用户请求或已授权的类型化 Pipeline 调用。真实外部能力不因本模块存在而变成 Live。遵守项目隔离、取消和预算边界。测试执行状态：not run，仅主代理进行最小烟测。

## 按任务制作准备

`ProductionPreparationService` 在游戏首版或修改、独立建模、场景搭建、专业策划和导出开始前，生成一次可复用的选材记录。普通聊天不应调用此服务。

- 调用方以 `CandidateProvider` 公开接口提供内置资产、当前项目资产、当前项目或共享经验、技能和能力候选。本模块不会读取其他模块数据库，也不会扫描文件系统。
- `current_project` 候选必须与请求的 `project_id` 一致；停用、平台不符、制作类型不符或缺少已声明能力的候选不会进入目录。
- 候选摘要按完整条目计入 24,000 字符预算。放不下的条目整条省略，不截断经验或资产说明。
- 推荐模型使用 AI Provider 的独立 `selector_settings()` 快照和 `generate_for_selector()` 路径，最长 30 秒、最多调用一次且没有重试。主对话模型配置不会被临时切换。
- 模型输出使用严格 Pydantic schema。服务再次校验资产版本、经验修订、技能身份和能力 ID；自由文字仅作为建议保存，绝不作为命令执行。
- `(project_id, request_key)` 是幂等键。第一次结果（包括失败或跳过）会持久化，重复请求复用，不再次调用模型。新用户要求必须使用新的 `request_key`。
- 未配置推荐模型、预算不足、超时、取消或无效输出均保留可读取的候选目录，并明确标记 `skipped` 或 `failed`。未知用量和费用保持 `null`。

公开入口：

```python
from sceneops_ai_context import (
    PreparationRepository,
    ProductionPreparationService,
    create_preparation_router,
)

repository = PreparationRepository(database_path)
service = ProductionPreparationService(
    candidate_providers=[asset_catalog, experience_catalog, skill_catalog],
    recommendation_provider=provider_service,
    repository=repository,
)
router = create_preparation_router(service)
```

HTTP 路由由宿主沿用现有认证后挂载：

- `POST /api/production-preparation/prepare`
- `POST /api/production-preparation/candidates/search`
- `POST /api/production-preparation/candidates/detail`
- `GET /api/production-preparation/results/{request_key}?project_id=...`

候选详情仍会用本次请求重新确认项目范围、制作类型、平台和能力兼容性；返回详情不代表采用、复制、实际引用或运行验证。


### 经验提供记录

组合根可注入 `context_recorder`，将制作准备选中的经验交给经验服务统一限量、快照并补充当前项目记忆。`selected_context` 只提供回调实际返回的正文，不重复携带未限量经验。任务启动阶段使用 `record_memory=False` 保留候选选择；真正发起模型请求时才读取最新修订并保存使用记录，准备完成不等于已经提供给模型。
