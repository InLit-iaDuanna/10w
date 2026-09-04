# Production Planner

Production Planner 把一个稳定引用的 Feature Spec 转成可编辑、可审阅、默认未确认的生产任务图。它聚焦游戏功能生产，不试图成为通用企业项目管理系统，也不会直接执行 Blender、Unity、渲染、构建或测试工具。

## 解决的问题

- 将功能拆成设计、概念、资产、动画、世界、逻辑、UI、音频、VFX、渲染、构建和测试任务；
- 为每个任务记录负责人类型、输入、输出、验收关联、风险、审批要求和预测估算；
- 检测依赖循环、缺失任务或输出、以及不可能成立的里程碑状态；
- 展示关键路径、阻断项、人工/代理分配、里程碑准备度和预测/实测估算来源；
- 将真实运行耗时作为 `measured` 记录追加，保留原始 `predicted` 估算；
- 通过稳定引用关联外部评论、审批、ChangeSet、产物和验收证据；
- 为未来聊天入口和按钮准备同一份 `production.plan.create` 调用函数；在 core command registry 缺失时不注册；
- 为未来任务打开动作准备 typed `workbench.open_editor` payload；在 shell contract 缺失时不执行。

主要用户是制作人、游戏设计师、各专业负责人、QA 和负责受控代理编排的团队成员。

## 当前实现范围

模块内已实现并独立验证：

- Pydantic v2 领域与 API 合同；
- 薄 FastAPI router；
- 注入式 Feature Spec、可信命令上下文、run evidence、Approval 和 versioned repository 端口；
- 确定性的任务生成、DAG 校验、关键路径和里程碑准备度；
- 带乐观版本检查的任务编辑、分配、状态转换、评论引用、交付物与证据关联；
- 由 provider 验证的计划与任务审批引用门禁；
- create-if-absent 语义，同一 Feature 修订重复创建不会覆盖人工编辑或已审批计划；
- 由 verified run timing 推导 measured 工时，调用方不能直接提交小时数或自报 live/cached；
- Feature Spec 修订影响分析；
- 中文图视图模型、权限/停用/断连/失败状态，以及明确 blocked 的未来 editor/command descriptors；
- 后端生成 OpenAPI、JSON Schema 和 TypeScript DTO；
- “Find My Way Home” 钥匙与家门的确定性 mock 示例。

生产组合根、真实 design-room 来源、共享审批/ChangeSet、共享 API client 和 Dockview/React shell 均尚不存在，因此对应集成明确为 **Blocked**，没有用 mock 冒充。

## 公共入口

后端公共包：

```text
sceneops_production_planner
```

公开内容包括 planner service、Feature Spec/context/run/approval/repository 注入端口、创建计划请求/响应、Feature Spec 稳定引用与 planner 投影，以及 `create_router`。

前端公共入口：

```text
frontend/src/index.ts
```

它导出一个没有活动 editors/commands/event handlers 的 `moduleContribution`、`blockedFrontendContributions` 规划描述、图视图/持久化函数、注入端口和由 Pydantic schema 生成的 DTO。模块没有 `fetch`、鉴权、base URL 或独立 transport，也没有把普通对象冒充 React component。

## 编辑器

| Editor ID | 用途 | 当前状态 |
|---|---|---|
| `production.plan` | 任务图、关键路径、阻断项、里程碑和分配概览 | 图视图模型已测试；React/shell contribution Blocked |
| `production.task` | 单任务输入、输出、验收、估算和状态摘要 | 领域数据已实现；React/shell contribution Blocked |

图视图模型覆盖 loading、empty、ready、failed、disconnected、permission denied 和 module disabled 状态。局部缩放、平移、选中任务与 follow/pinned context 可以序列化。真正可渲染的 React graph editor 尚未实现，因此 manifest 不注册 editor。

## 命令与事件

| ID | 行为 |
|---|---|
| `production.plan.create` | 已实现同 handler/API seam；Workbench command 注册 Blocked |
| `production.task.open` | 已实现 shell payload builder；Workbench command 注册 Blocked |
| `production.plan.drafted@1` | planner payload schema 已实现；core event contribution Blocked |
| `production.plan.approved@1` | planner payload schema 已实现；core event contribution Blocked |

模块测试证明聊天别名 `/创建生产计划` 与按钮 wrapper 共享同一个函数对象。真实 chat/command registry 尚不存在，所以没有宣称该入口已可在产品中使用。

## 数据所有权

本模块拥有：

- `ProductionPlan`、`ProductionTask`、`TaskDependency` 和 `Milestone`；
- planner 当前 Assignment 投影、Estimate、Risk 和结构性 Blocker；
- 任务到验收标准、证据、产物和下游 editor 的关联。

本模块不拥有：

- Feature Spec 正文或 design-room 持久化；
- actor 目录、评论正文和评论线程历史；
- ChangeSet、Approval 或 artifact provenance 的共享记录；
- workspace、命令 envelope、事件 envelope 或外部工具执行。

这些对象只以稳定 ID 引用。完整边界见 [集成说明](docs/integration.md)。

## 任务与里程碑规则

生成计划具有以下约束：

1. 计划状态为 `draft_unconfirmed`，所有任务和建议分配的 `confirmed` 均为 false。
2. Approval provider 验证 plan approval 引用后，只有没有前置任务的草稿任务进入 `ready`。
3. 任务只能沿显式状态机推进；上游未完成时不能 ready/start/complete。
4. 完成任务必须为每条关联验收标准提供通过证据；live 计划不接受 mock 证据。
5. 需要人工审批的任务还必须提供由 Approval provider 验证的 task approval 引用。
6. 编辑任务、分配、依赖或里程碑会使计划重新进入未确认状态。
7. dependency cycle、缺失任务/输出或伪造的 ready/completed 里程碑会形成结构性阻断；运行时任务 blocker 必须有原因和解决引用。
8. 进行中或终态任务不能原地改写；结构变更在已有任务开始后必须进入新的 Feature/计划修订。
9. 同一 Feature revision 的重复 create 返回既有计划（`created=false`），不会覆盖编辑、证据或审批。

详细状态机见 [领域与状态机](docs/domain-and-state.md)。

## 钥匙与家门示例

fixture 位于：

- `contracts/examples/key-door-feature-planning-snapshot.json`
- `contracts/examples/key-door-production-plan.mock.json`（生成文件）

它稳定生成 12 个专业任务、21 条依赖和 6 个里程碑。当前预测关键路径为 60 小时；这是带明确 `predicted` 标签的模板规划值，不是生产率承诺或真实测量。

示例输出模式为 `mock`。所有下游资产、动画、场景修改、构建和测试输出仍是 `planned`，并未执行。

## 合同生成

Pydantic 是网络合同源。以下文件由脚本生成，不应手改：

- `contracts/openapi.json`；
- `contracts/manifests/*.schema.json`；
- `contracts/events/*.schema.json`；
- `contracts/examples/key-door-production-plan.mock.json`；
- `frontend/src/generated/contracts.ts`。

生成或检查：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend/src python3 backend/scripts/export_contracts.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend/src python3 backend/scripts/export_contracts.py --check
```

## 测试

在 `modules/production-planner` 目录运行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend/src python3 -m unittest discover -s backend/src/sceneops_production_planner/tests -v
node --experimental-strip-types --test frontend/src/tests/*.test.ts
```

覆盖 task fixture、cycle、missing prerequisite、impossible milestone、状态转换、人工/代理分配、predicted/measured、证据门禁、Feature 修订影响、API 成功/失败、聊天/按钮一致性、editor states、context 持久化和 typed editor handoff。

## 执行真实性

| 模式 | 当前事实 |
|---|---|
| `live` | 创建路径主动阻断；必须等可信 core context 与真实 design-room provider |
| `mock` | 钥匙与家门 fixture、内存 repository、测试 provider 和测试 app 已验证 |
| `cached` | 创建路径主动阻断；measured 仅在 provider 证明 originating live run 时允许 cached timing |
| `planned` | 生成的下游生产工作与预测估算均明确为尚未执行 |
| `blocked` | design-room provider、core envelope/approval、module runtime、shared client、shell 和 E2E |

## Limitations

- 默认 FastAPI app 先使用 `UnavailableExecutionContextProvider` 返回 `CORE_CONTEXT_UNAVAILABLE`；注入可信 context 后，缺失 design-room 会返回 `FEATURE_SOURCE_UNAVAILABLE`。两者均为 mode=`blocked`。
- 内存 repository 仅用于 mock/test，不是生产持久化。
- 前端当前仅有可测试的图视图模型和 blocked descriptors；真实 React/Dockview component、Zod command schema 与 TypeScript compiler 集成均未宣称完成。
- create/get/graph 是当前公开 API；编辑、状态、审批回调、证据与依赖变更目前仅是经过测试的 backend domain API，用户级 typed routes/commands 在可信 core mutation context 可用前保持 Blocked。
- 推荐 editor ID 依据书面产品合同配置，尚不能在缺失模块中做注册表验证。
- 官方 module catalog、feature flag 组合、生成式 shared API client 和跨模块 E2E 需在 00/01/03/04 任务完成后验证。
- 根 `STATUS.md` 与 `EXECUTION_PLAN.md` 在本任务起点不存在，且不属于本模块写入边界。


## 独立 Web 工作台（本轮新增）

现在可从应用根运行 `pnpm --dir apps/labs/project-planning dev`，访问 http://127.0.0.1:4311。
首次依赖安装、运行事实、手动路径及限制见 [工作台说明](../../apps/labs/project-planning/README.md)。
公开 `loadPlanningPanel()` 返回真实 React 懒加载组件；旧 headless view model 与命令保持兼容。

以上旧文中的 React/跨模块规划 blocked 描述仅适用于原始模块交付；本轮独立工作台已连通。
正式 Shell 注册、统一身份与生产级持久化仍未接入，不能将独立 lab 当作已接入完整 Shell。
