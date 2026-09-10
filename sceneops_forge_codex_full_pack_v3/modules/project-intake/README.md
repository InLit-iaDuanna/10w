# Project Intake

## 项目移除与本地删除（2026-09-09）

最近项目右侧按钮打开两种操作的确认页：默认“从最近项目移除”保留文件夹与 Git 历史，调用原有 DELETE 接口；“删除本地项目文件”要求输入完整登记路径，永久删除该文件夹并移除登记，不进入废纸篓。无效目录仅提供移除登记。失败保留确认页并显示服务端错误。

新增 `POST /api/workspace/folder-projects/{project_id}/delete-files`，请求为 `FolderProjectDeleteFiles`（`confirmed_root_path` 与必须为 true 的 `confirm_permanent_delete`），成功返回 204。服务端核对登记路径与磁盘项目身份，拒绝符号链接目录、应用/用户主目录、嵌套登记项目及外置 Git 工作区关联；已有制作任务执行时拒绝删除。目录内部符号链接只删除链接本身。删除失败保留登记并提示可能部分删除；该操作不清理项目根目录以外的应用历史数据。

验证：共享 JSON 请求 2 项、项目窗口 3 项与临时目录删除/失效登记移除 2 项定向烟测通过；真实 4300 代理调用临时项目，验证永久删除、保留同级文件、失效目录移除及列表更新。未删除用户项目文件；未运行完整测试或构建。

## 游戏工程初始化

公开 `initialize_game_project` 根据 Design Room 已确认的技术方案创建真实 Web + Three.js 工程。对象／组件式和 ECS · Miniplex 使用不同源码组织和更新循环，均包含启动入口、最小移动—收集—计分交互、类型检查、构建和预览命令。架构记录写入 `.sceneops/game-architecture.json`；重复同方案为幂等操作，改选架构要求明确迁移任务。

检测到已有 `package.json`、`index.html` 或 `src` 时只记录选择，不覆盖或自动提交源码，并把项目标记为 `existing_unadopted`。完整采用已有工程属于后续里程碑。SceneOps 新生成的 scaffold 会形成选择性 Git 基线，卡片 worktree 只从 Git 历史继承文件，不再复制主目录中的未跟踪文件。详细行为见根目录 `GAME_CODE_ARCHITECTURE_MILESTONE.md` 和 `GAME_PROJECT_IDENTITY_BASELINE_MILESTONE.md`。

## 内置演示资产

两种新工程架构均直接使用 `src/game/sceneops-demo-assets.ts`，默认可以移动、收集黄色宝石并计分，无需上传素材。资产是原创的 Three.js 可编辑基础几何：玩家、敌人、NPC、队友共用同一人物轮廓，分别使用蓝、红、黄、绿配色；另含小屋、树、木箱、岩石和宝石。示例村落中的其他角色目前仅作展示，不表示战斗或对话已实现。坐标采用米、Y 向上，角色朝向 +Z。

公开 `demo_asset_files()` 返回固定路径和源码；`install_demo_assets(project_id, card_id)` 只向实际登记并校验通过的卡片 worktree 安装该固定模块，返回 pack/version、安装与保留文件清单、工作区和导入说明。调用方负责先核对任务授权并记录执行动作。已有文件无论内容是否相同都保留，符号链接和非普通文件拒绝写入；安装不修改游戏入口或用户资产，后续任务读取模块后再接入。已提交工程再次确认同一技术方案时继续使用原基线和源码，不用新版模板覆盖用户工程。

局部验证：两个架构的真实临时 Git 初始化／安装／保留／符号链接拒绝检查、Three.js 几何实例的统一轮廓和配色检查，以及对象／组件式模板 TypeScript 检查。上述检查不调用外部 AI 或 Blender。

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

项目作用域错误由公开 `ProjectNotFound` 和 `FolderProjectRequired` 表达：项目 ID 不存在返回 404，已存在项目未绑定文件夹而调用文件夹能力返回 409。统一 API 返回对应 `PROJECT_NOT_FOUND`／`FOLDER_PROJECT_REQUIRED` 与 `retryable: false`；这些错误不会混入通用服务器异常。`ProjectNotFound` 保持原 `KeyError` 类型兼容，但 HTTP 边界只捕获明确的领域类型。

本地 API 可通过 `GET /api/workspace/folders?path=` 浏览真实目录。省略 `path` 时从当前用户主目录开始；符号链接只显示为不可选项。`POST /api/workspace/folder-projects` 接收 `parent_path` 和单段 `name`，仅在已存在的父目录下排他创建全新子目录、身份文件和独立 Git，然后登记 workspace Project ID。`GET /api/workspace/folder-projects` 和 `GET /api/workspace/folder-projects/{id}` 用于持久列出和重新打开；`POST /api/workspace/folder-projects/inspect` 和 `/recover` 提供显式身份恢复。

本地项目界面采用 Codex 式入口层级：主界面直接提供“新建项目”和“打开项目”，空工作区突出唯一的新建主动作；新建面板只要求项目名称并显示最终路径，保存位置在需要时单独选择。“打开项目”进入文件夹选择和身份检查，恢复、移动与副本处理只在检测到对应状态后显示。创建或打开成功后，本地项目区域自动关闭并回到主对话。最近项目、独立对话与旧版无文件夹入口继续保留。

跨模块只使用公开 repository 方法：

- `read_design_draft(project_id)`：安全读取绑定项目内的 `.sceneops/design/draft.json`，供本机索引恢复后重新同步策划状态；不存在时返回空，不接受符号链接或非 JSON 对象；
- `restore_design_git_state(project_id, versions, card_branches, baseline)`：只在设计快照、标签提交、工程基线祖先关系、卡片分支、worktree 身份和卡片说明全部与项目草稿一致时，恢复本机 Git 登记；允许继续使用来自旧 SceneOps 数据目录的已验证卡片 worktree；
- `write_design_draft(project_id, payload)` 原子写入绑定根目录中的 `.sceneops/design/draft.json`；
- `create_design_snapshot(project_id, payload, version)` 排他创建 `.sceneops/design/snapshots/vN.json`。同版本、同结构化 JSON 的重试返回已有快照，不同内容会冲突且绝不覆盖。

调用方不能提供相对路径。存储拒绝相对目录、目录链上的符号链接、已有项目子目录和不安全的 SceneOps 元数据目录；不会改写所选父目录中的任意已有内容。

确认项目移动时，若项目已有外置卡片 Git worktree，恢复流程会先使用 Git 的 worktree repair 修复 linked-worktree 指针并逐一验证，再更新项目根目录登记。任何卡片工作区不可读时不会把移动报告为已完成。

## Blender GLB Demo 运行合同

新对象／组件式与 ECS 模板通过 `createDemoAsset` 异步加载 `runtime_artifacts` 中 render 文件，路径为 `public/...glb`。文件源不会退回 DoorRecipe。GLB 采用米、Y 向上，节点 extras 保留稳定 `sceneops_id` 与 `sceneops_role`（frame、leaf、hinge）；唯一 hinge 必须包含 leaf，frame 不得属于铰链子树。场景实例身份保存在外层 Group，不覆盖源节点身份。开门只旋转铰链；碰撞按各 Mesh 变换后的几何包围盒计算，门框保持阻挡，不会把整个门框空洞作为一个实心盒子。

加载错误显示“模型加载失败”，旧的配方专用用户工程在物化文件资产前返回 `LEGACY_RUNTIME_REQUIRES_EDIT`，需通过代码任务接入加载器；物化器不覆盖用户行为文件。`demo_content_glb_smoke.mjs` 用实际二进制 GLB 验证加载、偏置铰链、固定门框和碰撞；该确定性几何夹具不是 Blender 或浏览器实测证据。

旧生成工程现在可调用公开仓库服务 `preview_demo_runtime_upgrade(project_id, workspace_id)`，再在有效的源码写入授权下调用 `apply_demo_runtime_upgrade(project_id, workspace_id, preview)`。预览返回 `migration_version`、`architecture`、`status`（ready/current/conflict）、`files`（path/previous/proposed）及 `conflicts`；应用成功返回 applied/current。这里只迁移登记工作区内固定的消费者源码，随后仍需物化当前 Demo 内容以提供 GLB 加载模块。调用方负责将预览纳入现有 ChangeSet 与授权审计。

`runtime_v1_sources.json` 是 Git 版本 514648b 中两个生成模板的迁移祖先源码，不是校验基线。Git 三方合并保留不重叠的用户修改；重叠修改返回冲突供代码任务解决。预览不写工程；应用重新计算预览，拒绝过时或篡改提案和符号链接，不覆盖冲突。该路径不依赖用户工程存在初始化提交，也不会创建提交。升级与后续 Demo 物化是独立步骤，调用方须完成二者后再启动游戏验证。

迁移目标同样作为 `runtime_v1_targets.json` 保存，来自 abb0f41 的消费者源码，因此以后新工程模板的变化不会改变此迁移版本。写入每个文件前重新核对原文；失败补偿只恢复仍等于本次写入结果的文件，保留执行期间其他编辑者的新内容。

## 项目悬浮窗口（2026-09-08）

`WorkspaceProjects({projectId, onSelect, onClose})` 使用原生模态 dialog，在窗口中央承载最近项目、新建表单和目录选择。同一时刻只显示一个步骤；Escape 返回上一步，列表页关闭后恢复入口焦点。创建页自动聚焦名称，空名称禁用提交，失败保留表单并显示错误。保存位置仅在“使用此位置”后改变，取消浏览保留原位置。最近项目的移除图标仍保留确认，不删除项目文件。

统一宿主所有项目入口打开这个窗口，不再创建 Dockview 分栏。历史 `workspace.projects` 栏位加载时转为窗口并关闭旧栏位；切换项目仍沿用原有未保存修改确认。

验证：4301 本地页面启动、项目窗口及新建表单的键盘打开、名称自动聚焦、目录选择和 Escape 返回及视觉检查已完成。新增组件用例覆盖步骤返回、焦点、空名称和创建失败；完整组件测试与构建本次未运行。
