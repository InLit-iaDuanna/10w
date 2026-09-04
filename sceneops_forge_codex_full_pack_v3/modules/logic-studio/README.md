# Logic Studio

Logic Studio 把已批准 Feature Spec 转成可检查、可版本化、可验证的玩法图，并在
必须修改 C# 时生成受审批和回滚保护的 ChangeSet。它面向游戏设计师、关卡设计师、
Unity 工程师和测试负责人。

## 已完成范围

- `GameplayGraph` v1：状态变量、事件、条件、效果、交互关系、任务、对话、反馈、
  结局、验收标准和生成测试引用；
- 确定性序列化、版本检查、语义差异和图运行时；
- 不可达节点、死支路、无出口循环、缺失引用、非法条件/效果、冲突效果和未满足
  验收标准诊断；
- 数据驱动的钥匙—背包—锁门—任务—反馈—结局模板，以及 Warehouse Escape
  开关—门模板；
- Edit Mode、Play Mode、结构化行为测试计划；
- C# proposal → dry-run ChangeSet → 明确批准 → apply → compile/tests → rollback；
- 六个懒加载编辑器贡献及完整可见状态；
- FastAPI 路由、作业定义、版本化 JSON Schema、事件合同和模块工作流。

## 编辑器

| ID | 中文标题 | 作用 |
|---|---|---|
| `logic.feature` | 功能规格 | 查看已批准 Feature Spec 与验收条件 |
| `logic.state_graph` | 玩法状态图 | 检查状态、节点、边和验证结果 |
| `logic.interaction_graph` | 交互关系图 | 检查稳定对象 ID 与关系模板 |
| `logic.quest_dialogue` | 任务与对话图 | 检查任务推进、台词和选择分支 |
| `logic.code_diff` | 代码差异 | 审阅 C# ChangeSet、批准和回滚状态 |
| `logic.test_cases` | 测试用例 | 查看 Edit/Play Mode 与行为测试引用 |

`logic.editor.open` 同时服务于聊天、按钮、菜单和快捷入口，并输出需要布局确认的
`workbench.open_editor` 动作。

## 公开命令与事件

命令：`logic.editor.open`、`logic.graph.validate`、
`logic.interaction.compile`、`logic.test_plan.generate`、
`logic.code_change.propose`、`logic.code_change.approve`、
`logic.code_change.apply`、`logic.code_change.rollback`。

事件：`logic.graph.validated@1`、`logic.test_plan.generated@1`、
`logic.code_change.proposed@1`、`logic.code_change.rolled_back@1`。

## 数据与依赖

本模块拥有玩法图、交互模板、生成测试计划和代码变更提案合同。它只保存其他域的
稳定 ID，不读取其他模块私表。必需模块为 `core-kernel` 与 `module-runtime`；Unity
是可选集成。缺少 Unity 时，图编辑、验证、差异和测试计划仍可用，C# apply 与
Play Mode 执行为明确的离线/阻塞状态。

## 执行真实性

| 能力 | 当前状态 | 说明 |
|---|---|---|
| 图编译、验证、差异、模拟、测试计划 | `live` | 模块本地确定性代码在当前进程实际执行 |
| Hero/Warehouse 示例 | `mock` | 固定绑定和确定性模板，无外部工具 |
| C# 提案及待审批 ChangeSet | `planned` | 尚未触碰 Unity 项目 |
| Unity 适配器合同测试 | `mock` | 仅内存收据、失败与回滚路径 |
| ForgeShell/生成客户端挂载 | `blocked` | 基线缺少 core 与 shell 实现 |
| Unity apply/compile/Edit/Play Mode | `blocked` | 基线缺少 `engine-unity` live 适配器 |
| Cached real-run replay | `planned` | 当前没有任何先前真实运行产物 |

没有结果会把 `mock`、`planned` 或 `blocked` 标成 `live`。

## 运行测试

后端（Python 3.9+，依赖见 `backend/pyproject.toml`）：

```bash
cd modules/logic-studio/backend
PYTHONPYCACHEPREFIX=/tmp/logic-studio-pycache PYTHONPATH=src \
  python3 -m unittest discover -s src/logic_studio/tests -t src -v
```

前端定义和视图模型（Node 22.6+，不下载依赖）：

```bash
cd modules/logic-studio/frontend
npm test
```

## 示例

- `contracts/examples/hero-key-door.binding.json`
- `contracts/examples/warehouse-switch-door.binding.json`
- `workflows/interaction-templates.v1.json`

更多合同规则见 `docs/graph-contract.md`，C# 安全流程见
`docs/unity-code-change-flow.md`，宿主接入见 `docs/integration.md`。

## 已知限制

- 基线没有共享模块运行时，因此尚不能在真实 Dockview/React 工作区中手工验收。
- 基线没有 Unity 工程或适配器，因此没有 live 编译、Edit Mode、Play Mode 或构建。
- 当前服务为无持久化领域服务；ChangeSet 存储与并发版本检查应由控制平面接入。
- 模型解释不在本模块验证路径中；未来可作为非权威说明层接入。

## 2026-09-05：独立 Web 整合更新

原 10 基线中的“没有真实 React 工作台”的限制现已解决：应用根运行 `pnpm --dir apps/labs/world-logic dev`，详见 [启动与本次验证](../../apps/labs/world-logic/README.md)。该入口使用公开 lazy loader 组合 UI；原 headless API 保留，实际 UI 使用它的 loading/ready/failed 状态模型。

- `loadLogicWorkbench()`：状态图、节点与对象绑定、关系编辑、图 JSON、C# diff、原服务验证与本地状态预览。
- `loadProposalReview()`：核心 ChangeSet / 原 CodeChangeSet 的审批要求、语义差异、前后值和导出。
- `LogicWorkbenchApi`、`WorldLogicApiPaths`、`WorldLogicApiComponents`：注入接口及 Pydantic/OpenAPI 生成网络类型。
- `logic_studio.workbench_router`：隔离样例、验证、预览、玩法图提案、代码提案；不会挂载旧 approve/apply 流程。
- 新样例 `contracts/examples/world-workbench.binding.json` 对齐 `sobj_player_spawn`、`sobj_home_key`、`sobj_home_entrance`，原样例保留。

玩法图请求始终校验固定场景对象目录，图草稿不可通过修改目录伪造对象；图提案以服务器内的原始图为 before，要求 version + 1。API 无生产写回端点。Python 服务依赖原公共 `sceneops-core-contracts`；独立启动器从同一源目录导入。

本次仅 smoke 到拾取成功和待审批图提案；新增 `test_workbench.py` 的成功/失败回归及完整模块测试均未运行。没有执行 Unity 编译、Edit/Play Mode、构建或 AI playtest。若以后加入 AI，使用 codebuddycli 并提供前端模型选择，当前确定性路径无需 AI。
