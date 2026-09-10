# Version and Collaboration

`version-collaboration` 在 Git / Git LFS 之上提供团队评审层：版本检查、四层差异、带版本锚点的评论、分配、决定、经核心服务验证的审批、二进制资产锁、追加式活动历史、发布证据链接，以及必须审批的回滚 ChangeSet。

它不替代 Git，不尝试实时合并 `.blend`、`.glb` 或 Unity 二进制资产，也不在 React 编辑器里运行 Git 命令。

## 用户与场景

- 制作人与评审者：理解文件、场景语义、固定相机画面和玩家行为分别发生了什么变化。
- 美术与技术美术：通过 Git LFS 锁、分支和评审协作二进制资产。
- QA 与发布负责人：把审批、证据、结果提交和 release stable ID 串成可审计链路。
- 开发者：在 stale base、脏工作树、合并冲突、目标删除或 schema 不兼容时获得结构化阻塞状态。

本模块的两个确定性示例覆盖 `Find My Way Home` 的钥匙开门分支和 `Warehouse Escape` 的开关/门碰撞问题。两者只更换项目数据，不更改平台逻辑。

## 公开能力

### Editors

| ID | 用途 | 默认位置 |
|---|---|---|
| `review.version-diff` | 文件、语义、固定相机视觉、行为四层并排检查 | center |
| `review.session` | 评论、分配、决定、审批摘要 | right |
| `review.activity` | 追加式协作活动 | bottom |

三个 editor 都是 lazy load，支持 follow-global 和 pinned review revision。固定模式通过不可变 revision API 读取对应评审与摘要，而不是把当前 revision 重新标记成旧 revision。`review.session.create` 不带 review ID 时创建会话；带 `review_id + expected_previous_revision_id` 时以 compare-and-swap 语义发布下一不可变 revision。`review` workspace 只在用户请求时打开，不改变 chat-only 首屏。

### Commands

```text
review.session.create
review.comment.add
review.assignment.record
review.decision.record
review.approval.record
review.lock.acquire
review.lock.release
review.rollback.propose
review.rollback.execute
review.release.link
```

Shell 按钮、对话和菜单使用同一组 command definitions，消费 composition root 提供的 `VersionCollaborationApi`。独立 lab 的评论与决策复用这些 definitions；lab transport 的操作签名由 Python OpenAPI 生成，不在组件内直接请求网络。

### 独立版本评审工作台

公开入口 `VersionReviewWorkbench`（前端）与 `create_demo_app`（后端）组合为 `apps/labs/version-review`。支持两个演示项目、四层差异、对象锚定评论、决策、MOCK 审批和追加式历史。外部输入全部 MOCK，本地计算和内存 SQLite 实际执行；重启恢复 fixture，未连接真实 Git、锁或回滚。

启动与本轮精确验证记录见 [工作台 README](../../apps/labs/version-review/README.md)。本轮没有运行完整模块测试，也没有接入 AI；以后若需要 AI，应按用户要求使用 codebuddycli 并提供模型选择，不走 bridge/cbridge。

### Events

事件均为 v1、过去式事实：

```text
review.session.created@1
review.revision.published@1
review.comment.added@1
review.assignment.recorded@1
review.decision.recorded@1
review.approval.recorded@1
review.lock.recorded@1
review.rollback.proposed@1
review.rollback.executed@1
review.release.linked@1
```

JSON Schema 位于 `contracts/events/review-events.v1.schema.json`。网络合同由 Pydantic/FastAPI 生成到 `contracts/openapi.json`，TypeScript 类型生成到 `frontend/src/generated/api-types.ts`。

## 数据所有权与不变量

SQLite repository 只拥有本模块表。review revisions、comments、assignment records、decisions、approval observations、lock records、ChangeSet history、activity、rollback proposals/executions 和 release evidence links 都是追加式记录；公开 repository 没有 update/delete API。

- 评论始终绑定 `review_revision_id + diff_bundle_id + Git version + typed target_id`。
- 通用 ChangeSet 和 Approval 仍由 `core-kernel` 所有。本模块通过 `ChangeSetGateway` 创建引用，通过 `ApprovalVerifier` 验证精确绑定，只保存审计 observation。
- Approval 精确绑定 review revision、diff bundle、subject/version 和完整 Git version identity（provider、repository、object format、commit）；记录审批前会重读真实仓库 HEAD，阻断冲突存在时不会批准或链接发布。
- 回滚 proposal 固定绑定 review revision、diff bundle、base 与 dry-run，再创建 core ChangeSet；session 发布新 revision 后旧 proposal 不可执行。执行时必须持有精确审批；Git adapter 创建新的 forward commit，不使用 `reset --hard`，并以 expected HEAD 做原子 compare-and-swap。幂等重试除验证 operation/proposal/approval/base/target trailers、父提交和目标 tree 外，还要求该提交就是当前 HEAD 且 index/worktree 已同步。
- 二进制路径必须持有 Git LFS 外部锁。SQLite 中的 active lock 只是外部锁的审计投影；读取、幂等获取和 destructive unlock 前都会核对远端 ID/path，跨系统写入失败时执行补偿或显式进入 reconciliation-required 状态。

## 四层差异

1. **File**：两个不可变 commit 间的 add/modify/delete/rename、行数、binary 和 LFS pointer metadata。
2. **Semantic**：按 stable entity ID 和 JSON Pointer 属性路径比较；schema/provider/version 不同即 `incompatible`，不会靠名称猜测。
3. **Visual**：只比较 camera pose、尺寸、色彩空间、capture recipe 和 renderer version 完全一致的像素样本；指标是客观像素差，不代表艺术质量。
4. **Behavior**：只比较 test case、protocol、config、start state 和 seed 一致的 playtest evidence；报告 delta，不在没有 acceptance rule 时宣称“提升”。

每层独立标记 `succeeded | empty | unavailable | incompatible | failed`，并保留 `live | cached | mock | planned | blocked`。详见 [four-layer-diff.md](docs/four-layer-diff.md)。

## Git / Git LFS adapter

`GitCliAdapter` 只暴露 typed methods。内部 subprocess 使用固定 argv、`shell=False`、project-root allowlist、timeout、cancellation、只读重试、structured logs 和 error mapping。所有 revision 都记录 Git 自身 `object_format`，不会把 Git SHA-1 OID 错称为 artifact SHA-256 checksum。

Git LFS pointer 仅解析已存在的 `oid sha256` metadata；本模块不计算新 hash。Git LFS CLI 或远端锁服务不可用时，锁命令返回 blocked，二进制协作仍可查看 diff，但不能伪造锁或合并成功。

## Setup

后端 composition root 必须提供：

1. `SqliteReviewRepository` 或实现同一 protocol 的持久 repository；
2. 只允许已注册项目目录的 `GitCliAdapter`；
3. core `ChangeSetGateway`；
4. core `ApprovalVerifier`；
5. authenticated `ActionContext`（actor、permissions、correlation/causation ID、mode）；
6. 必需的 event publisher（不能省略成静默 no-op）；
7. project ID 到 project root 的内部映射。

注册 `create_router(...)` 以及 `version_collaboration_exception_handler`。API 永不接受客户端提交的绝对 project root 或 Git argv。

前端 composition root 提供生成客户端实现、React、TanStack Query 和 module registry。导入的唯一公开前端入口是 `frontend/src/index.ts`。

## 测试

从模块目录运行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v
npm --prefix frontend test
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend/src python3 backend/scripts/generate_contracts.py --check
```

Git 集成测试只操作系统临时目录中的独立仓库，并真实验证 status、branch、commit、dirty/conflict、LFS pointer（含删除场景）、stale/dirty rollback、forward commit、原子 expected-HEAD 更新与严格幂等 operation identity。其他跨模块端口使用确定性 `mock`，不会标为 live。

## 执行模式现状

| 能力 | 状态 | 说明 |
|---|---|---|
| Git inspect / compare | `live` | 通过本机 Git CLI 实际执行；有临时仓库集成测试 |
| Git rollback adapter | `live` | 仅在收到 approved typed command 后创建前向提交并原子更新 HEAD；有临时仓库集成测试 |
| Git LFS lock | `blocked` on this host | 当前主机没有 Git LFS CLI；代码路径已实现但未进行远端 live 测试 |
| 四层示例 | `mock` | 两个游戏使用确定性 fixture |
| cached replay | `planned` | mode 与 UI 标签已定义，没有 cache provider，不提供伪 cached 输出 |
| core ChangeSet / Approval | `blocked` for app integration | 当前起点缺少 core 模块；unavailable ports 阻止 live mutation |
| render/playtest/build-release producers | `planned` | 仅通过 stable IDs / typed payloads 集成；当前起点不存在这些模块 |
| shell/module catalog mount | `planned` | 贡献已定义；当前起点没有 module runtime 或 apps/web |

## Known limitations

- 当前仓库起点只有规格，缺少 `core-kernel`、`module-runtime`、`apps/web`、render/playtest/build-release，因此无法在本工作树验证实际 catalog mount、生成共享客户端或完整 hero E2E。
- 当前主机未安装 Git LFS，未对真实远端 LFS lock/unlock 做 live 测试。
- 原子 rollback 目前不会绕过仓库安全策略：检测到 `commit.gpgSign=true` 或可执行 commit hooks 时会明确阻断，等待宿主提供兼容签名/钩子的原子提交端口。
- activity 与事件发布已有强制 publisher，但 repository 与外部 event bus 之间尚无事务型 outbox；宿主应在正式集成前提供可靠发布边界。
- 视觉输入使用 typed pixel samples；生成真实 fixed-camera capture 和 diff image artifact 由 render/scene provider 后续接入。
- 行为层不自行运行 AI playtest；它比较 `ai-playtest` 提供的稳定 evidence snapshots。
- 异步 HTTP/持久化协作已实现；presence 和实时评论同步未实现，且不影响追加式审计。

统一应用现公开 `loadIntegratedWorkbench()`；空态、自有草稿、样例边界与验证限制见 [统一编辑器说明](docs/unified-workbench.md)。

### 可视化版本管理

统一入口新增简洁的自上而下项目 Git 树：项目根、真实提交和每个本地分支末端都直接显示在主画布中。支持分支高亮、合并关系、HEAD 定位、拖动/缩放、提交文件详情，以及预览确认后创建/切换本地分支。评审表单默认折叠。真实策划阶段与已确认版本来自宿主公开服务；数据与限制见 [版本树说明](docs/unified-workbench.md#可视化版本树2026-09-06)。

### 项目进度总览（2026-09-08）

统一版本入口默认展示整个项目：当前策划阶段、已确认策划版本、全部制作卡片、依赖与验收目标，并将卡片关联到本地分支和提交历史。卡片可展开并按分支关联筛选；里程碑和变更入口进入原版本历史，分支操作仍使用原预览与确认机制。15 秒刷新项目快照，支持手动重试。布局适应窄分栏，交互使用短过渡并遵循减少动态效果设置。

`TreeProgress` 通过宿主公开策划服务新增可选标题、cards 与 versions 投影；旧响应兼容空数组。计划和已建立分支不表示制作已完成；构建、验证和发布尚未在此聚合执行证据，不显示推测完成率。已执行项目进度单条 smoke（关联保留、旧字段兼容、无效卡片拒绝）及本地页面主路径检查；完整测试未运行。
