# Concept Lab

Concept Lab 把 Project Bible 的风格意图和功能需求整理成可评审、可追溯的概念版本，并在人工批准后编译为 `AssetSpecDraft v1`。它不会生成或发布最终 3D 资产。

## 用户与问题

面向美术、设计、制作人和技术美术。模块解决四个问题：明确资产概念要求；保留导入/生成参考图的来源与许可；让比较、评论、拒绝和批准成为可追溯决策；把批准结果交给 Asset Factory，而不越过其生产职责。

## 功能范围

- `concept.moodboard`：概念参考、变体、执行模式、许可警告和评审状态。
- `concept.style_bible`：展示与 `project_bible_version_id` 绑定的风格约束、禁止元素和风格证据。
- `ConceptSpec`：主题、玩法功能、比例、米制尺寸、材质、必需视图、平台预算、风格约束、禁止元素和参考 ID。
- 导入参考图与 typed 图像生成 adapter；支持多视图与 adapter 声明的 turn-around 能力。
- 概念版本、Concept ChangeSet、评论、比较、批准/拒绝决策和解释性风格检查。
- 只输出 `AssetSpecDraft`，不发布 AssetVersion。

## 公共入口

- 前端：`frontend/src/index.ts`
- 后端：`concept_lab` 包的 `__init__.py`
- OpenAPI：`contracts/openapi/concept-lab.openapi.json`
- 事件与清单 schema：`contracts/events/`、`contracts/manifests/`

其他模块只能使用上述入口、稳定 ID、命令、事件或已发布 schema，不可导入内部 repository/service。

## 公共命令与事件

公开命令见 `module.yaml`。其中 `concept.open` 同时服务于对话动作、任务链接和工具库；它生成同一种 `workbench.open_editor` typed action，并要求在显著改变布局前确认。

事件：

- `concept.version.created@1`
- `concept.variant.recorded@1`
- `concept.variant.reviewed@1`
- `concept.asset_spec_draft.compiled@1`

所有事件包含项目、correlation/causation ID、actor、UTC 时间和真实执行模式。

## 许可与批准

参考图许可有 `cleared`、`warning`、`blocked` 三态。`blocked` 禁止批准；`warning` 要求评审者显式确认。拒绝不会删除变体。批准还要求覆盖全部必需视图并至少存在一条风格检查记录；风格结果本身不会作为“艺术真理”自动替代人工决定。

## 图像生成边界

模块没有供应商 SDK，也不会从 UI 直连外部服务。运行时注入实现 `ConceptGenerationAdapter` 的 adapter。能力报告决定模型、视图和 turn-around 是否可用。

- `mock`：`generation-mock.json` 的确定性测试输出。
- `cached`：合同回放 fixture；明确标为 cached，不代表本次 live 运行。
- `live`：协议、健康检查和结果校验已实现；当前仓库没有供应商 adapter，因此是 `planned`，未配置时运行结果为 `blocked`。
- 无图像生成时：导入拥有来源、许可和 provenance 的概念图，流程仍可完成。

完整边界见 `docs/image-generation-boundary.md`。

## Hero 示例

`backend/src/concept_lab/fixtures/hero-key-concept.json` 定义 “Find My Way Home” 的黄铜钥匙概念。它要求正视和四分之三视图、桌面中端预算、温暖手工黄铜风格，并禁止现代电子钥匙扣。示例可以走 mock/cached 变体，也可以导入项目自有概念图。

## 设置与测试

无需图像生成密钥即可运行本地测试：

```sh
uv run --project modules/concept-lab/backend --extra test pytest -q
npm --prefix modules/concept-lab/frontend test
npm --prefix modules/concept-lab/frontend run typecheck
uv run --project modules/concept-lab/backend python modules/concept-lab/scripts/export_contracts.py --check
```

重新生成 Pydantic/OpenAPI 合同：

```sh
uv run --project modules/concept-lab/backend python modules/concept-lab/scripts/export_contracts.py
```

## 当前集成状态

- 模块本地 backend、schema、workflow、fixtures 和前端贡献：已实现。
- `core-kernel` / `module-runtime` 静态目录注册：`planned`，基线尚不存在。
- Project Bible 查询：`planned`；当前通过 `project_bible_version_id` 保留 typed ID 边界。
- Asset Factory 消费：`planned`；Prompt 07 拥有最终 `AssetSpec`，需由其适配 `AssetSpecDraft v1`。
- 供应商 live 图像生成：`planned`；缺少 adapter 时如实返回 `blocked`。

## 已知限制

- In-memory repository 仅用于独立模块测试；生产 repository 需要在持久化基础设施到位后注入。
- 风格检查聚合提交的证据与置信度，不分析像素，也不宣称客观艺术评分。
- 前端编辑器贡献已实现，但最终 generated API client 与 ModuleRuntime 注册要等待核心模块提供合同。
