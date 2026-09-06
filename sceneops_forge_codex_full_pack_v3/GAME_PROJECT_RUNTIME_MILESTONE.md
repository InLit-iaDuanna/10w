# 游戏工程运行与 Agent 反馈闭环

本里程碑把卡片源码开发从“写入后待人工检查”扩展成可选择授权的真实工程闭环。用户仍从 Design Room 的制作卡片进入代码开发；授权后，产品 Agent 可以读取现有源码、增量写入、准备当前工程依赖、运行 TypeScript 检查与 Vite 构建、根据日志修复，并启动该卡片构建产物的本地预览。原有仅源码流程保留，旧任务和旧授权不会获得新增执行权限。

## 用户操作路径

1. 在已确认技术方案的制作卡片中，将协作方式切换为“高级 · 代码开发授权”。
2. 按需选择“允许 Agent 执行类型检查、构建和本地预览”；依赖尚未准备时，再选择“允许在当前游戏工程内准备依赖”。
3. 输入开发目标。此时只准备授权卡，不运行模型、安装、构建或预览。
4. 审阅授权卡中的卡片、分支、真实 worktree、运行范围和 16 次模型调用上限，再点击确认。
5. Agent 使用同一组类型化能力完成源码与工程操作。任务卡持续显示依赖、检查、构建、预览和最近日志。
6. 用户也可以在任务卡点击“准备依赖”“检查并构建”“启动预览”“停止预览”。这些按钮与 Agent 调用同一个 `GameProjectRuntime`，没有第二套脚本路径。
7. 点击“打开独立预览”会在新标签页打开 `http://127.0.0.1:<随机端口>/`。点击“继续修改同一工程”会回到当前卡片输入框，新任务继续使用相同登记 worktree。

## 运行边界与持久记录

- 每次操作都从 Workspace Repository 重新核验 `(project_id, card_id, branch, worktree_path)`；客户端和模型不能提交工作目录、命令、端口或环境变量。
- 固定工程命令为 `pnpm install --ignore-scripts`、`pnpm exec tsc --noEmit`、`pnpm exec vite build --config <应用自有配置>`。显式应用配置阻止工程注入可执行的 Vite 配置；依赖准备使用隔离 HOME/cache，并且不继承 token、Provider 密钥、代理或用户 npm 配置。
- 预览由应用自有 Python 静态服务器只服务当前 worktree 的 `dist`，只监听 `127.0.0.1` 的随机端口。停止操作只查找该项目和卡片对应的应用子进程；服务关闭会停止所有仍由它持有的预览。
- `game_project_runs` 表保存每次操作的真实状态、退出码、日志、构建目录和预览地址。源码工具成功写入后，先前通过的检查和构建会变成 `stale`，运行中的预览标记为源码已改变；必须重新检查和构建。
- 服务重启时不会相信数据库里的旧 PID 或旧 running 状态。没有当前进程所有权的历史预览被记为 interrupted；应用不会据旧 PID 停止其他进程。
- `agent.finish` 对运行授权任务要求本次有源码写入回读、当前检查和构建通过，并且当前预览仍在运行。结果为 `build_ready / review_required`；浏览器 console 和玩法行为仍明确标为未自动验收。

应用默认数据目录中的任务、操作和日志仍保存在同一 SQLite 数据库；卡片游戏工程位于 Workspace Repository 登记的 `card-worktrees/<project_id>/<card_id>`。本轮保留的验收数据位于 `/Users/isduanna/Documents/10w/.sceneops-acceptance/game-runtime-20260907`，其中 `acceptance-report.json`、`real-agent-sprint.json`、`real-agent-cooldown.json` 和 `browser-behavior.json` 分别记录模板、真实 Agent 与浏览器结果。

## 修改范围

- `modules/ai-agent-runtime/backend/src/sceneops_ai_agents/game_runtime.py`：固定依赖、检查、构建、预览与 SQLite 运行记录。
- `modules/ai-agent-runtime/backend/src/sceneops_ai_agents/preview_server.py`：严格 localhost 的单一构建目录服务器。
- `task_models.py`、`task_service.py`、`task_tools.py`、`task_loop.py`、`task_repository.py`、`code_workspace.py`：授权、能力、ChangeSet、状态失效、Agent 观测和终态核验。
- `task_router.py`、OpenAPI 和生成 TypeScript 类型：`GET/POST /api/agent/tasks/{task_id}/game`。
- `AgentTaskWorkbench.tsx` 与 `client.ts`：任务内运行面板、日志、独立预览和继续修改入口。
- `PlanningJourney.tsx` 与 Shell 组合：用户在准备任务前明确选择运行与依赖范围。
- `test_game_project_runtime_smoke.py`：失败修复、旧语义、共享操作、预览所有权、失效与重启测试。

## 已执行验证

模板与产品入口：

- 通过 `SqliteWorkspaceRepository.initialize_game_project` 和 `open_card_worktree` 创建对象／组件式与 ECS · Miniplex 两个“移动—收集—计分”工程。
- 两个工程均由 `AgentTaskService.game_operation` 完成依赖准备、检查、构建、预览启动、HTTP 200 读取、重复启动去重和停止；所有命令退出码均为 0。
- 对象工程包含 `Game.ts` 且无 Miniplex；ECS 工程包含 `world.ts` 且唯一 ECS 依赖为 Miniplex。

确定性 fixture：

- `test_game_project_runtime_smoke.py` 共 5 项通过。覆盖旧 source-only 授权、TS2322 日志驱动修复、当前源码失效、同卡重复启动、跨卡停止隔离、服务重启不信任旧预览，以及链接到卡片外的构建目录拒绝。
- `test_card_development_smoke.py` 与 `test_card_git_write_smoke.py` 继续通过，确认原源码任务与真实 Git worktree 行为未回归。

真实 Agent：

- 使用产品 `card-development + typed-tools` 路径和 Codex CLI `gpt-5.6-sol`。第一次 12 次预算试跑完成写入、检查和构建，但在启动预览前耗尽；该失败作为真实任务记录保留，据此把完整闭环授权调整为 16 次。
- 新卡片 `codex/card-agent-loop` 的冲刺任务使用 14/16 次调用：Agent 读取 ECS 架构与现有系统，增量修改，自己准备依赖、检查、构建、启动预览并 finish。
- 第二个冷却任务继续同一 worktree，使用 14/16 次调用；读取已有冲刺实现后只修改 `src/game/systems/inputSystem.ts`，再次自行检查、构建、启动预览并 finish。两个任务均为 `review_required`，检查与构建通过。

浏览器与宿主：

- Playwright 打开第二个任务的产品预览：1 个 canvas、0 条 console error。300 ms 普通移动为 1.545，冲刺为 2.470，冷却期间按 Shift 为 1.588；等待 2.1 秒后 `data-sprint-ready=true`，再次冲刺为 2.476。
- 统一 Web 执行 `pnpm exec vite build --config apps/web/vite.config.ts`，848 个模块转换并构建成功。
- `pnpm generate:agent`、Python `compileall` 和 `git diff --check` 通过。

## Limitations

- 当前固定运行配方只支持本项目已接通的 Web + Three.js + TypeScript + Vite 工程；没有增加其他引擎或任意 package script 执行。
- `browser_errors_verified` 与 `gameplay_verified` 仍由人工或单独 Playwright 验收设置为事实，本轮没有把开发 Agent 的自述升级成自动玩法通过。
- 依赖准备允许访问包仓库，但只属于当前生成工程，安装脚本禁用；没有扩大 Harness 全局依赖或 Shell 权限。
- 本轮没有实现架构迁移、自动提交、自动合并、发布或外网预览。服务关闭后本地预览结束，用户可从保留的成功构建重新启动。
- 根 `tsc --noEmit` 仍报告仓库既有的重复测试文件、跨模块严格类型和 WebGPU 声明冲突；本轮修改相关文件没有新增诊断，统一 Web 的真实 Vite 构建通过。
