# Project Intake

## 游戏工程初始化

公开 `initialize_game_project` 根据 Design Room 已确认的技术方案创建真实 Web + Three.js 工程。对象／组件式和 ECS · Miniplex 使用不同源码组织和更新循环，均包含启动入口、最小移动—收集—计分交互、类型检查、构建和预览命令。架构记录写入 `.sceneops/game-architecture.json`；重复同方案为幂等操作，改选架构要求明确迁移任务。

检测到已有 `package.json`、`index.html` 或 `src` 时只记录选择，不覆盖或自动提交源码，并把项目标记为 `existing_unadopted`。完整采用已有工程属于后续里程碑。SceneOps 新生成的 scaffold 会形成选择性 Git 基线，卡片 worktree 只从 Git 历史继承文件，不再复制主目录中的未跟踪文件。详细行为见根目录 `GAME_CODE_ARCHITECTURE_MILESTONE.md` 和 `GAME_PROJECT_IDENTITY_BASELINE_MILESTONE.md`。

## Git 文件夹项目

新增公开 `ensure_project_git`、`commit_design_version`、`open_card_worktree`，仅操作应用绑定的根目录。新建目录先写 `.sceneops/project.json` 并验证独立 Git，再登记 SQLite；中断目录可通过 `inspect_folder_project` 和 `recover_folder_project` 显式恢复、移动或登记为副本。正式版本和工程基线都不夹带用户暂存文件；新卡是从当前有效 `codex/integration` HEAD 懒创建的实际 Git 分支和独立 worktree，旧卡保持原 base。全部 Git 调用禁用 hooks、签名和配置的 checkout filters，不修改全局配置、不自动联网。

Project Intake 把“一句项目想法”或“扫描现有项目”的结果转换为可检查、可确认的项目入口记录。它不接触生产文件；扫描器必须先通过公开的 `ProjectScanAdapter` 把 Unity、Blender 或其他工具的数据归一化。

## 用户与数据

面向制作人、游戏设计师和技术负责人。模块拥有项目入口草稿、字段来源/确认状态、扫描摘要和准备度问题。它记录：目标平台、引擎、DCC、项目根目录、团队角色、风格目标、性能预算和集成需求。

关键字段 `targetPlatforms`、`projectRoots` 只有用户明确输入或执行确认命令后才是 `confirmed`。对话提取和扫描检测到的值都是 `inferred`；没有值则是 `missing`。

## 公开能力

- Editor：`project.intake`
- Commands：`project.intake.create_new_draft`、`project.intake.draft_from_conversation`、`project.intake.scan_existing`、`project.intake.confirm_field`
- Events：`project.intake.drafted@1`、`project.intake.field_confirmed@1`
- 公开入口：`frontend/src/index.ts`
- Backend：`sceneops_project_workspace.create_folder_router(repository)` 提供应用内目录浏览和文件夹项目创建/重开；`SqliteWorkspaceRepository` 是公开持久化实现。
- 磁盘合同：`contracts/manifests/project-identity.v1.schema.json` 定义 `.sceneops/project.json`。
- 权限：读取 `project:read`；新建/确认 `project:write`；扫描还需 `project:scan`

对话命令返回结构化 `workbench.open_editor` 动作。它创建的只是应用内草稿，不会改写项目文件，也不会启动生产任务。

## 扫描与降级状态

扫描 adapter 必须报告健康状态和真实执行模式：`live`、`cached`、`mock`、`planned` 或 `blocked`。离线、缺权限、模块关闭、路径无效和 adapter 失败都有中文可见状态。fixture adapter 是确定性的 `mock`，绝不标记为 live。

当前规格起点没有 `core-kernel`、`module-runtime`、ForgeShell 或生成式模块目录，因此本模块提供可独立测试的公开贡献对象和无框架 editor view model。接入真实 Dockview/React editor、生成 catalog 与统一命令总线属于前置模块恢复后的 **planned** 集成，不在这里伪造。

## 运行测试

```bash
cd modules/project-intake/frontend
npm test
```

fixtures：`findMyWayHomeNewProject` 覆盖新项目；`warehouseEscapeScanReport` 覆盖现有项目的部分扫描。JSON 合同示例位于 `contracts/examples/`。

## 已知限制

- 仓库尚无持久化/API 组合根，当前 repository 是可替换的内存实现。
- 本模块不实现 Unity/Blender 扫描；真实扫描由后续 integration adapter 实现公开协议。
- 本模块不创建生产任务，准备完成后仅发出 typed event 供 `production-planner` 消费。


## 独立 Web 工作台（本轮新增）

现在可从应用根运行 `pnpm --dir apps/labs/project-planning dev`，访问 http://127.0.0.1:4311。
首次依赖安装、运行事实、手动路径及限制见 [工作台说明](../../apps/labs/project-planning/README.md)。
公开 `loadIntakePanel()` 返回真实 React 懒加载组件；旧 headless view model 与命令保持兼容。

以上旧文中的 React/跨模块规划 blocked 描述仅适用于原始模块交付；本轮独立工作台已连通。
正式 Shell 注册、统一身份与生产级持久化仍未接入，不能将独立 lab 当作已接入完整 Shell。

## 文件夹项目与设计存储

本地 API 可通过 `GET /api/workspace/folders?path=` 浏览真实目录。省略 `path` 时从当前用户主目录开始；符号链接只显示为不可选项。`POST /api/workspace/folder-projects` 接收 `parent_path` 和单段 `name`，仅在已存在的父目录下排他创建全新子目录、身份文件和独立 Git，然后登记 workspace Project ID。`GET /api/workspace/folder-projects` 和 `GET /api/workspace/folder-projects/{id}` 用于持久列出和重新打开；`POST /api/workspace/folder-projects/inspect` 和 `/recover` 提供显式身份恢复。

本地项目界面采用 Codex 式入口层级：主界面直接提供“新建项目”和“打开项目”，空工作区突出唯一的新建主动作；新建面板只要求项目名称并显示最终路径，保存位置在需要时单独选择。“打开项目”进入文件夹选择和身份检查，恢复、移动与副本处理只在检测到对应状态后显示。最近项目、独立对话与旧版无文件夹入口继续保留。

跨模块只使用公开 repository 方法：

- `write_design_draft(project_id, payload)` 原子写入绑定根目录中的 `.sceneops/design/draft.json`；
- `create_design_snapshot(project_id, payload, version)` 排他创建 `.sceneops/design/snapshots/vN.json`。同版本、同结构化 JSON 的重试返回已有快照，不同内容会冲突且绝不覆盖。

调用方不能提供相对路径。存储拒绝相对目录、目录链上的符号链接、已有项目子目录和不安全的 SceneOps 元数据目录；不会改写所选父目录中的任意已有内容。
