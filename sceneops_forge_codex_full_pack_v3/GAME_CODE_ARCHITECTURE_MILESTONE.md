# 游戏代码架构选择与真实工程起点

日期：2026-09-06

## 结果

第一次生成游戏工程代码前，策划对话现在会明确区分目标平台、引擎／渲染技术和游戏代码架构。当前工具链固定使用 Web + Three.js，用户可以直接选择“对象／组件式”或“ECS · Miniplex”，也可以让当前已配置的 AI 提供方根据已确认策划推荐，再由用户采用具体方案。

确认方案会立即在文件夹项目根目录创建真实 Vite + TypeScript + Three.js 工程。对象／组件式工程由 `Game` 驱动 `Player`、`Collectible` 和组件；ECS 工程使用 Miniplex `World`、组件数据和 `inputSystem`、`movementSystem`、`collectionSystem`。两者都包含入口、依赖、键盘移动、收集计分、类型检查、构建和浏览器预览，不是同一模板改目录名。

## 用户操作路径

1. 在“本地项目”创建文件夹项目，完成 idea、grill-me、大纲并确认正式版本。
2. 在“选择游戏工程的代码架构”中直接选择一种方案，或点击“让 AI 根据策划推荐”。
3. 查看推荐理由和取舍；点击“采用推荐并创建工程”，或手动方案下的“选择并创建工程”。
4. 工程创建完成后生成制作卡片，选择卡片进入对应 Git worktree。
5. 在卡片协作中选择“高级 · 代码开发授权”，描述新增功能；Agent 会先读取当前源码和技术方案，在已选架构内增量修改。

AI 推荐失败或尚未返回时，两个手动选择始终可用。选择结果保存在策划 Journey 的 SQLite 状态中，同时写入项目根目录 `.sceneops/game-architecture.json`；刷新和重新打开项目会恢复相同方案。

## 生成工程

工程根目录就是用户创建的文件夹项目，入口为 `src/main.ts`。生成的 `README.md` 提供运行命令，`ARCHITECTURE.md` 约束后续 Agent 延续当前架构。

```bash
cd <用户选择的项目目录>
pnpm install
pnpm check
pnpm dev
```

生产构建使用 `pnpm build`。Vite 打印本机预览地址后，可用 WASD 或方向键移动蓝色玩家，接触黄色物体计分。

本轮保留的临时验收工程：

- 对象／组件式：`/private/var/folders/my/6wlls8751xgdx2cvhq5d7fvh0000gn/T/sceneops-architecture-final-bt3lgoel/object-component`
- ECS：`/private/var/folders/my/6wlls8751xgdx2cvhq5d7fvh0000gn/T/sceneops-architecture-final-bt3lgoel/ecs`
- 真实 Agent 修改后的 ECS 卡片 worktree：`/private/var/folders/my/6wlls8751xgdx2cvhq5d7fvh0000gn/T/sceneops-real-agent-gu4_lt_l/data/card-worktrees/prj_4a9af9eff2c04bcda9ca35a999995d83/sprint`

这些是系统临时目录中的验收样例，操作系统后续可能清理；实际用户工程始终生成在用户选择的项目目录。

## Agent 上下文

技术方案进入三处真实数据路径：

- 制作卡生成提示包含 Web、Three.js、具体代码架构和 ECS 库；
- 卡片 worktree 的 `.sceneops/card-brief.json` 保存完整开发上下文，`.sceneops/game-architecture.json` 保存技术方案；
- `AgentTaskService.prepare()` 将 `technical_plan`、当前卡片、策划版本、实际 worktree 路径和分支写入任务 observations，并要求先读当前源码后增量修改。

缺少技术方案的新卡片开发任务会返回 `GAME_ARCHITECTURE_REQUIRED`，不会根据旧 `stack: threejs` 字段猜测代码架构。

## 旧项目兼容

旧 Journey 缺少 `technical_plan` 和推荐字段时仍可反序列化和打开。确认架构时若项目根目录已有 `package.json`、`index.html` 或 `src`，系统只记录选择，不重建、不覆盖源码，也不提供虚假的初始化命令。

打开卡片时，Git 已跟踪的文件由 worktree 自然提供；尚未跟踪的普通项目文件会安全复制到新卡片 worktree。复制排除 `.git`、`.sceneops`、隐藏文件、依赖目录和构建目录，并且不覆盖 worktree 中已有文件。根项目内容保持不变。

已有技术方案后选择另一种架构会明确提示需要迁移任务。本轮没有实现一键架构迁移。

## 修改范围

- `modules/project-intake/backend/src/sceneops_project_workspace/game_projects.py`：真实工程模板、初始化记录、旧项目和卡片 worktree 材料化。
- `modules/project-intake/backend/src/sceneops_project_workspace/repository.py` 与 `__init__.py`：公开初始化入口并在卡片创建时接入工程。
- `modules/design-room/backend/src/sceneops_design_ai/journey_models.py`、`journey.py`、`card_modeling.py`：技术方案模型、AI 推荐、手动确认、持久化和下游提示。
- `modules/design-room/frontend/src/PlanningJourney.tsx` 与 `planning-journey.css`：非专业术语说明、方案选择、推荐理由、恢复信息和开发入口约束。
- `modules/ai-agent-runtime/backend/src/sceneops_ai_agents/task_service.py`：实际开发任务上下文和缺失方案拒绝。
- Journey/OpenAPI 生成类型与服务总合同：同步新字段和命令。
- 两个定向测试文件：覆盖两类方案、保存恢复、旧状态、不覆盖、卡片工程和 Agent 上下文。

开始本轮前已经存在的 `EnvironmentScenePreview.tsx`、`EnvironmentSceneWorkflow.tsx` 未提交修改原样保留；本功能没有回退或重写它们。

## 验收证据

模板和模拟 Provider 测试：

- `python -m unittest ...test_journey_smoke ...test_card_git_write_smoke -v`：9 项通过。
- 覆盖 AI 推荐 ECS、手动对象／组件式、选择保存和重开恢复、旧 JSON 缺字段、已有源码不覆盖、已有源码进入卡片 worktree、Agent 任务拿到架构和实际工作区。
- `py_compile` 与 `git diff --check`：通过。
- 统一 Web Vite 生产构建：848 个模块转换完成，构建通过；保留现有的大 chunk 和动态导入提示。

真实工程测试：

- 两个临时工程分别执行 `pnpm install`、`pnpm check`、`pnpm build`，全部通过。
- Playwright 分别打开两份真实 Vite 页面：均有一个 canvas，初始玩家 X 坐标为 `0.000`；按住 D 后对象／组件式变为 `5.667`，ECS 变为 `5.711`；两页控制台错误均为 0。

真实 Agent 验证：

- 使用产品已有 `card-development + typed-tools` 路径和 Codex CLI `gpt-5.6-sol`，共 7 次模型调用。
- Agent 收到 `ecs` 方案和真实 worktree，依次检查工作区，读取 `ARCHITECTURE.md`、`world.ts`、`inputSystem.ts`，只修改 `inputSystem.ts`：按住 Shift 时速度从 5 提升到 8。
- 写入经源码工具回读后进入 `review_required`。随后由验收方在该 worktree 执行 `pnpm check` 和 `pnpm build`，均通过。

## Limitations

- 当前只实现已接通的 Web + Three.js；没有同时铺开 Unity、Godot 或其他引擎。
- 真实 Agent 的受控卡片权限只允许源码读写，不允许 Shell、安装和构建。Agent 写入后的类型检查和构建由本轮验收单独执行，未扩大产品权限。
- 已有但尚未进入 Git 的项目复制最多 2048 个文件、单文件 64 MiB、总计 256 MiB；超过范围时要求先纳入 Git，不会截断或静默漏文件。
- 没有实现架构迁移、自动提交、自动合并、发布或 AI 自动游测。
- Design Room 独立 `node:test` 入口仍有既有 Node ESM 扩展名和 `.tsx` 加载配置失败；根 `tsc --noEmit` 仍有既有跨模块严格类型诊断。本轮使用统一 Web Vite 构建验证了实际集成前端。
