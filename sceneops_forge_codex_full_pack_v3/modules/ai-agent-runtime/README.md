# 运行专家

游戏试玩区采用紧凑预览栏：一行切换版本、启动／刷新与新窗口打开，画面占据主体，底部运行记录默认折叠。预览未启动时可直接点击中央启动按钮，继续使用原有构建和运行服务。

原生制作的 `code.browser.observe/interact` 对已授权、成功且未失效的本任务截图返回 MCP `image/png` 内容块，模型无需读取工作区外路径。新制作及续改开启截图读图授权，旧授权不追溯修改。截图附件传递与模型实际视觉结论分别记录，文件大小、canvas 数量或成功截图不证明画面正确；不能看到附件时仍需明确报告。

工作台顶栏「启动游戏」或 `⌘/Ctrl + Alt + P` 直接打开当前项目最新任务的游戏。最新构建已运行时直接进入；预览停止时启动；源码已变化时沿用不调用模型的更新流程。正在制作且尚无当前有效预览时显示等待提示，不将旧版本标成最新。键盘快捷键在工作台获得焦点时生效。

## 原生制作内置资产与浏览器环境（2026-09-09）

新制作及续改默认授权内置资产准备；仅“更新作品”的构建操作不新增此授权。原生 MCP 提供 `builtin.assets.list` 和带 `asset_ids` 的 `code.demo_assets.install`，使用已登记项目安装服务，保留已有文件并使旧构建观察失效。未授权任务不显示安装工具，旧任务不追溯扩权；新一轮续改生成新的授权记录。素材安装与实际游戏加载、构建、试玩验证分别记录。

应用根依赖固定 Playwright 1.62.1，运行依赖安装后执行 `pnpm exec playwright install chromium` 准备浏览器。后端 worker 自动解析根依赖和标准浏览器缓存；运行任务时不自动安装。配置后需重新执行观察，历史失败不会自动改成通过。

## 2026-09-08：卡片源码精修

卡片内新增架构目录、源码查看和手动保存、受控文件范围 AI 精修。公开组件 `CardSourceEditor` 与接口、验证范围见 [卡片源码精修](docs/CARD_SOURCE_EDITOR.md)。

S2 当前构建浏览器观察已接入产品 HTTP 入口、TaskTools 和结果面板；授权、部署配置、实测记录及限制见 [S2 浏览器观察](docs/S2_BROWSER_OBSERVATION.md)。

## Harness 批次 A：指令与上下文

类型化单动作入口现在由产品运行时装配公共制作指令、主制作角色和按需技能；卡片代码任务才加载游戏代码技能，基础资产和固定原型只得到各自相关的工具说明。`purpose='agent-action'` 通过提供方服务选择动作决策模式，三种传输只负责承载调用者选定的系统指令，不再替所有业务入口固定成只读顾问身份。讨论、顾问评估和规划入口仍保持只读，不因动作循环而扩大权限。

任务表继续保存完整动作输入与结果。下一轮模型上下文只投影动作状态、效果状态、短结果摘要和 `task-action://...` 引用；`code.file.write` 的旧/新全文不再随每轮历史重复发送。已授权模型可用 `agent.history.read` 从当前任务记录按引用重新读取历史写入正文或完整动作结果（包括文件读取与检查日志），不能跨任务解析引用。短交接摘要只陈述任务身份、最新动作和未解决动作；授权、预算和能力仍由运行时重新读取。

`assigned_role` 仍只是执行记录的领域标签。只有存在独立模型调用及其输入输出记录时，结果才可描述为独立 Agent 或独立评审。

## 游戏工程运行闭环

`card-development` 可由用户在新授权卡中选择 `allow_game_execution` 与 `allow_dependency_install`。前者加入固定 TypeScript 检查、Vite 构建和严格 localhost 预览，后者额外允许对当前登记卡片 worktree 执行禁用安装脚本的 pnpm 依赖准备。依赖准备使用 `--ignore-workspace --no-lockfile`，确保嵌套在 SceneOps 仓库内的卡片 worktree 只获得自己的 `node_modules`，不误装整个宿主工作区或产生锁文件。模型不能提供命令、目录、端口或环境变量；任务按钮调用同一个 `GameProjectRuntime`。源码写入会使旧检查、构建和预览失效，Agent 必须读取真实日志并重新验证。旧任务和未选择运行权限的任务继续以 `code_written` 结束。

公开路由 `GET /api/agent/tasks/{task_id}/game` 返回当前依赖、检查、构建、预览及日志状态；`POST` 只接受 `prepare | check | build | preview_start | preview_stop`。预览只服务当前 `dist`，仅监听 `127.0.0.1`，服务关闭时停止。完整实现与真实 Agent/浏览器证据见根目录 `GAME_PROJECT_RUNTIME_MILESTONE.md`。

制作卡片内嵌采用项目级 SSE 快照直接刷新 Agent 执行动作。卡片界面按 Codex 对话流展示检查、读取、写入、构建和预览，不再把每轮执行包装成独立任务卡，也不显示“查看执行记录”或“重新准备独立任务”入口；授权、项目占用和持久任务记录仍由服务端保留。最新一轮产生新鲜的运行中预览地址时，宿主收到回调并在右侧 Dockview `运行预览` 编辑器内自动打开实际页面。

本次增加 `ProductionStore` 与公开 `create_production_router(service)`：项目级一致性快照、持久序号 SSE、生产步骤及产物版本。任务和工作台共享此状态，不创建另一套执行引擎。每项目可准备多任务；工程写入由事务占用串行化，不确定写入需核查，不能自动释放后重放。产物复制到应用数据目录，限 512 MB、拒绝越界/符号链接/隐藏文件，HTML/SVG 不内联。受控 Blender/Unity 跨任务重绑定仍未接入，已有非空工程的受控续作会明确拒绝；Codex 可在应用登记工程中接受新的独立授权。详情见根 `SINGLE_AGENT_WORKBENCH_HANDOFF.md`，不能据状态底座实现宣称全流程可用。

最新追加：`PrepareAgentTask.execution_mode='codex-full-access'` 是用户明确要求的原生 CLI 执行权限，默认仍 `typed-tools`。必须选择 `codexcli`，以新授权卡和 `accept_full_access=true` 确认，不升级旧 grant。使用原 Harness 高风险任务级 ChangeSet/真实空目录记录/审批；一次 CLI 启动、20 分钟、low 思考，内部模型次数和费用未知，不自动重试。默认不加载用户全局 MCP/插件；完全权限不是 OS 沙箱，工作目录外访问技术上可行，范围约束作为 developer 指令传入。CLI 成功为 `review_required`，实际产物仍需审阅。完整说明与真实文件烟测证据见根 `CODEX_PROVIDER_HANDOFF.md`；下文 8 次模型及立方体限制仅适用于 `typed-tools`。

V5 AI Harness 垂直模块。公开 Python 包：`sceneops_ai_agents`；Pipeline 合同来自 `sceneops_harness`，不另复制网络模型。

默认不执行；由明确用户请求或已授权的类型化 Pipeline 调用。真实外部能力不因本模块存在而变成 Live。遵守项目隔离、取消和预算边界。当前 `test_agent_tasks.py` 的 14 个注入定向测试已通过；真实联合验收由主代理单独完成。

## 有界 Agent 任务

公开 `AgentTaskService(database_path, workspace_repository, data_dir, *, provider=None, blender_factory=None, unity_factory=None, card_context=None)` 与 `create_agent_task_router(service)`。`router(None)` 只用于 OpenAPI 导出，调用时返回未启用。主应用必须保留现有 loopback、同源请求及身份认证中间件；任务接口不接受客户端自报权限。

`execution_status() -> Literal['running','connected','idle']` 供组合根健康接口读取：活动任务、连接检查或清理中为 running；持有已启动且尚未成功停止的本地会话为 connected；其余为 idle。查询不启动或探测 DCC。该状态表示服务端已观测的生命周期，外部手动关闭编辑器要在后续实际读回时才能确认；成功 stop 会清除会话缓存。

接口：

- POST `/api/agent/tasks`：`{goal, project_id?}`，返回 AgentTaskRecord 授权卡。不选项目时只创建新的本地项目元数据；此时没有模型或 DCC 调用。
- GET `/api/agent/tasks?project_id=...`：返回 `{tasks}`，最近 20 项。GET `/{task_id}` 读取完整记录。
- POST `/{task_id}/authorize`：`{authorization_card_id, accept_unknown_cost:true}`。只批准当前服务端卡片，不接受客户端修改目录、能力或预算。
- POST `/{task_id}/cancel`：撤销 grant、取消当前 Harness run、停止任务专有会话；保留已有文件和记录。
- GET `/{task_id}/events?after=0`：返回 `{events,next_cursor}`，每页最多 200 个真实事件。
- POST `/{task_id}/resume`：只恢复工具启动前的连接阻断，先检查原工具，成功后继续原 action/request ID，不先调用模型。有效 grant 内才能继续；过期明确返回 GRANT_EXPIRED，需用户重新准备独立任务。

默认授权为一个独立空项目下的一个新立方体，尺寸每轴 0.001–100 米；模型总调用 8 次（包含规划、恢复和格式重试），20 分钟、每动作最多 2 次尝试。工具读取、FBX 导出、Unity 导入/场景放置均为注册的类型能力；不提供脚本、任意文件路径、覆盖已有对象、构建、渲染或游测动作。

主目录固定为 `data_dir/agent-workspaces/<project_id>`；工具状态放在独立的 `data_dir/agent-tool-state/<task_id>/<tool>`。模型只提出结构化 action，不能决定 grant、ChangeSet 审批人或授权范围。每个模型决定和生产动作均创建现有 Harness 单步 run；小型 `agent_tasks/agent_task_events` 表仅维护跨 run 的任务、授权及动作日志，不另造执行引擎。

ChangeSet 记录 agent 创建者；用户 grant 派生的审批通过原 Harness 审批机制记录，包含 grant/action/change_set/approval 引用。动作按能力标记现有专家角色：Blender 专家、Unity 工程师和最终审阅者。这些是有界任务分工记录，不声称启动了额外并行模型会话。

所有模型调用在开始前持久化占用次数，失败和取消不会退还。未知 usage/cost 保持未知；8 次请求是调用上限，不是美元或 token 硬限额。模型请求明确使用卡片准备时的模型，并校验实际 provider/model 响应；改变配置需要重新审阅授权。

终态完成需新鲜 Blender 与 Unity 读回：唯一 asset_id/sceneops_id、名称、尺寸、导出关联及 Unity console 无错误。Blender 为 Z-up，Unity 为 Y-up；目标尺寸按 `[x,z,y]` 变换检查。只有 Blender 成功、Unity 许可缺失时保持 blocked，显示真实原因并保留 Blender 产物。服务不代用户激活或申请 Unity 许可。

后端重启导致会话缓存缺失时，finish 先确认本任务已成功导出和导入的持久记录，再按原未过期 grant 恢复专有会话并进行两端新鲜读回，不重放 create/export/import，不增加模型调用。连接检查期间死亡的 owner 可清除并保留 blocked 与原授权，之后必须显式 resume；真实写入执行中的进程中断仍是 interrupted，需要人工检查，不自动重放或延长授权。

## 已执行验证

主代理报告真实任务 `task_ef6745aaba5543a19ff645cbfe38dd3a` 已完成 CodeBuddy → Blender → Unity 联合验收：使用 4/8 次模型调用，finish 在后端重启后重新连接 Blender，并通过两端当前读回。此结果只覆盖该有界立方体链，不代表构建、渲染、游测或完整 V5 已验证。

本模块的注入回归命令：

```sh
PYTHONPATH=modules/ai-agent-runtime/backend/src:modules/ai-model-router/backend/src:packages/harness-kernel/src:packages/core-contracts/src:integrations/ai-provider/src:integrations/codebuddy-cli/src .venv/bin/python -m unittest discover -s modules/ai-agent-runtime/backend/tests -p test_agent_tasks.py
```

结果：14 tests，1.388 秒，OK。包含授权前零调用、授权/路径边界、预算、路由匹配、去重、取消、顺序修复、许可恢复、过期授权、会话缓存丢失恢复、blocked owner 恢复和只读健康状态。全部模型和会话均为测试注入；此次回归没有实际模型、Blender、Unity、构建或案例调用。首次未设置源码 PYTHONPATH 时命中了虚拟环境旧安装包，导入失败；上述命令使用当前源码后通过。其他测试套件未在本轮执行。

## Limitations

当前自动修复仅在这些注册动作内：重新选择顺序、补检查/导出/导入、修正尚未执行的参数。已发送写入后的未知结果和越界修改需要人工检查，不自动重放。过期 grant 不延长，旧工作区不作为新空项目接管。工具适配器负责操作系统隔离、真实工具进程与固定命令；工具许可和环境状态不会切换到 Mock。

合成会话测试不能替代工具适配器的真实隔离、取消和文件恢复验证；真实 running 写入中断后仍须人工核对外部状态。
# 卡片源码开发增量

主对话执行展示使用紧凑活动行：动作说明、输入和结果默认折叠，失败原因直接可见；原生消息保留正常正文层级。主对话移除旧受控任务的用量与权限统计区，后台预算、到期校验及必要的阻断提示仍保留。原生任务默认不设总时限与内部请求次数上限，旧任务不会因切换模型而自动升级权限。

新项目制作及后续轮次按提供方选择原生执行。`ask` 只准备原生授权卡，用户确认后才执行；`full-access` 沿用发送即授权。两者不再因确认方式不同而选择不同执行引擎。已准备的旧受控授权卡保持原范围，需要重新准备才能使用新原生流程。

`PrepareAgentTask` 支持 `task_profile='card-development'` 和必需的 `project_id/card_id`，只允许 typed-tools。通过 workspace 公开只读登记接口绑定实际worktree，不接管任意路径。新增 `code.workspace.inspect`、`code.file.read`、`code.file.write`，写入仍经原Harness ChangeSet和授权。源码结果以 `code_written / review_required` 交付，不宣称运行/编译通过。上下文回调由宿主注入，避免模块内部导入。测试和限制见根 `CARD_CODE_DEVELOPMENT.md`。

公开前端 `moduleContribution` 使用生成 manifest；该模块没有独立 editor/command 贡献，现有任务视图继续由宿主嵌入。

## 对齐后的 Demo 授权

`PrepareAgentTask` 可为 `card-development` 显式设置 `include_demo_assets=true`，同时必须开启 `allow_game_execution`。完整当前卡片权限仍由独立的 `allow_dependency_install` 与 `allow_browser_observation` 声明；不会自动更换提供方、模型或进入 Codex 完全权限。

自动准备请求传入 Design Room 返回的 `alignment_id`。服务端核对当前卡片总结 ID，并使用该 ID 的确定性任务主键：刷新或重复请求返回同一授权卡及结果，取消后也不会自动生成另一个执行任务。同一总结的目标或权限变化返回冲突；总结改变后旧授权卡不能再获授权。准备只持久化任务，不安装素材、不请求模型、不运行工程。

用户确认授权后，系统先通过正式 Harness 动作 `code.demo_assets.install` 将 Project Intake 内置素材包放入当前登记卡片工作区，记录 ChangeSet、审批引用、run 和安装结果。动作没有调用方路径或程序输入；已有素材文件保持原样并记录成功的无变更结果。随后 Agent 读取实际模块路径与导出函数，在既有架构内完成目标。类型检查、构建和本地预览必须通过已有 `finish_game` 验证，不能用素材安装成功冒充 Demo 完成。

聚焦测试：`node scripts/python.mjs -m pytest -q modules/ai-agent-runtime/backend/tests/test_demo_task_authorization.py`。这些用例使用临时真实 Git 工作区与确定性动作，不调用模型或游戏命令。

## 卡片原生 Agent 会话

卡片可明确授权 `agent-full-access`：绑定已登记分支、目标、当前提供方和模型，使用 Codex 或 CodeBuddy 原生 CLI 会话。前端只展示持久化的 `observations.native_conversation` 文字与工具活动，经已有项目 SSE 推送刷新，不再驱动固定动作 JSON 循环。普通文字结束不表示独立验收；状态为 `review_required`。旧 `typed-tools` 授权与历史保持原语义，不能自动升级。每次原生任务只启动一次 CLI，结束撤销本次授权，失败/取消保留已收到内容与文件。CLI 事件协议仍为结构化传输，模型正文没有格式要求。

原生会话达到时限后，上一轮未知写入仍保留 `UNKNOWN`，不会被重放或伪装成已验收。如果工作进程已经停止、授权已撤销、清理没有不确定项且 Git 变更快照可读，同一 `conversation_id`、卡片、分支和工作目录上的下一次明确授权会原子接管项目占用，并要求新会话先检查现有改动再增量继续。其他对话、卡片或分支仍按并发写入处理并拒绝。

## Blender 原生资产往返

D4 内容入口增加「用 Blender 编辑」与「保存 Blender 源并同步导出」。旧授权保持原范围；「准备 Blender 编辑授权」通过原有限续授卡显式加入原生编辑和读取能力。Agent 使用相同的 `blender.asset.begin/edit/publish` 类型化动作与 Harness 审批、预算、任务占用；模型不提供文件路径或脚本。默认 Agent 无头、手工入口可见，完成回流后只关闭专用编辑会话。

`.blend` 候选从当前资产版本创建；程序化配方仅首轮转换，后续重开真实源。原配方版本保留，新版本不再显示无损配方编辑控件。导出、不可变文件保存、资产登记和引用应用分别记录。共享引用可按 `object_ids` 指定；部分应用冲突保留已保存源，通过当前场景版本继续应用，不再造资产版本。人工候选不能被模型编辑或发布，未知结果保留占用。

原生源的版本、真实工具与模型、Shell 证据及未完成验收见根目录 `BLENDER_NATIVE_ROUNDTRIP.md`。已有自定义游戏代码需要明确接入文件加载器；不自动改写普通行为源码。

## 项目工具更新

公开 `ProjectGameTool` 与 `ProjectProgressTool`，复用现有任务和运行操作。`CardSourceEditor` 的 embedded 模式用于工具面板。只读 source_index 使用已登记卡片工程说明，不调用执行对齐检查；实际修改保留原有检查。

## 主对话项目原生制作

`project-demo-agent` 现在可显式选择 `execution_mode='agent-full-access'`，不需要生产卡片。仍须提供 `project_id`、当前已确认的 `alignment_id`、`include_demo_assets=true` 和 `allow_game_execution=true`；工作目录只来自项目登记。当前提供方必须是 Codex 或 CodeBuddy CLI，授权请求必须带 `accept_full_access=true`。准备不会调用模型或安装素材。

每次原生准备返回新的 `_native_<uuid>` 任务，支持同一已确认方向的后续目标；每项均需新的明确授权，不延长或升级旧 grant。`typed-tools` 保持原方向 ID 去重与受控执行。项目模板已经包含基础 Demo 素材；原生任务复用一次 CLI 生命周期、原 Harness 审批与项目写入占用；上下文包含当前方向和技术方案。输出通过 `observations.native_conversation` 显示，结束仍是 `review_required`，不将模型自述视为构建验收。

原生 CLI 返回后，运行时在本次授权仍有效时自动执行工程检查、构建和 localhost 预览；缺依赖时仅在 `allow_dependency_install=true` 下先准备依赖。每步使用既有 GameProjectRuntime，保存真实状态与日志；失败停止后续步骤，不自动重试模型。授权时限与取消仍有效，最终撤销原生授权。前端读取现有 game 状态即可自动打开真实预览，无需用户逐步点击。模型自述不作为运行器证据。浏览器观察能力没有自动扩展；不确定写入仍按现有项目占用规则阻止新任务接管。

聚焦准备/授权测试：`node scripts/python.mjs -m pytest -q modules/ai-agent-runtime/backend/tests/test_project_native_authorization.py`。测试使用临时登记工作区，替换执行循环，不调用模型、安装、构建或预览。

## 游戏系统提示词

`game_execution_prompt.py` 是产品拥有的游戏工程提示词。根据已确认的 `camera_mode` 选择一屏取景、玩家跟随、第一人称或横向跟随要求，同时加入世界尺寸、DPR/CSS 画布尺寸、宿主 resize、HUD、失焦输入和真实视觉验证要求。原生任务把完整生成文本记录为 `native_system_instructions`，通过 ProviderService 的 `execution_instructions` 送入 CLI 系统/开发者通道，不混入用户目标，也不扩大 grant。类型化游戏执行使用同一规则。

## 本地运行服务管理

新增只读 TCP 服务列表和明确选择后的单进程 SIGTERM 停止入口；当前工作台、系统与未知类型进程保持只读，停止前核对 PID、开始时间、所属用户与端口集合。接口与限制见 [本地运行服务](docs/LOCAL_SERVERS.md)。

## 导出对话

公开 `ExportAgent` 复用当前提供方，一条消息至多一次模型调用，返回受限的配置／继续／取消／开发建议；Build Release 执行并持久化调用输入输出和用量。不会授权模型修改源码、下载权限或执行任意命令。四项注入提供方定向测试通过，真实模型调用未执行。

## 导出技能知识包（2026-09-08）

导出对话按目标平台加载产品自有系统提示词、环境补齐与平台技能，记录实际 loaded_skills；原生任务得到按需可读取的技能目录。知识以 Capawesome skills、Electron Builder、Fastlane 官方项目为参考，保留来源。独立原生导出执行链仍未接通，不以提示词宣称电脑操作能力。见 [说明](../../EXPORT_AGENT_SKILLS.md)。

### 原生导出执行

`AgentTaskService` 接受服务端 `export_context(project_id, export_id)` 解析器，使用独立的
`project-export-agent` profile。`prepare_export_task` 创建新轮次，`run_export_task` 在明确的导出执行
请求下复用既有授权、执行、事件、取消与恢复流程。原生模型必须为 Codex CLI 或 CodeBuddy CLI。
导出环境技能在系统通道加载；允许可信来源工具与 SDK 安装、构建环境配置，不包含玩法源码修改或公开发布。
产物通过导出工作区 `sceneops-export-result.json` 交给 build-release 独立检查登记；CLI 完成仅为待审阅，
不是设备验证通过。失败续作创建新任务并核查已有状态，不自动重放未知操作。

## 任务记录归档（2026-09-08）

制作进度的每条记录提供「归档」，通过「查看已归档」查看并恢复。`PUT /api/agent/tasks/{task_id}/archive` 接收 `archived` 布尔值，列表可使用同名查询参数筛选。归档元数据独立持久化，不删除记录、改变执行状态或释放项目占用；排队、运行、停止中或仍有执行进程的任务不能归档。恢复后任务回到原项目的记录列表。归档列表保留全部历史记录。


## 2026-09-09：中转 GPT 原生执行

完全访问下，OpenAI 兼容中转 GPT 使用 Codex CLI 原生执行，向保存服务的 Responses 接口发送请求。每次独立临时 HOME/CODEX_HOME；真实上游 Key 留在后端，CLI 使用固定目标与模型的临时本地凭据，Shell 不继承该凭据。默认不设总时限、内部模型请求与动作次数不限，可随时停止。

所有项目 Agent 直接显示实际文字、命令、文件与状态。旧 typed 任务保留历史和源码；在相同方向、工作区且无未决写入时，新原生授权可原子接管。未将旧任务改成已成功。

本机 Codex CLI 加本地 Responses 夹具完成真实命令写文件、事件输出与凭据/配置清理；前端原生路由、旧任务交接、对话静态渲染定向冒烟通过。没有调用用户的真实中转模型或构建游戏。组件测试运行器因已有 picomatch 错误未启动。细节见根目录 NATIVE_API_EXECUTION.md。


### 每轮任务依据

类型化模型请求、原生任务请求和原生制作会话使用统一经验服务，按 `task:{task_id}:call:{request_identity}` 记录实际提供的版本，聚合到 `task:{task_id}`。每次请求重读已选经验的最新有效版本和当前项目记忆，保留过去请求的快照；停用及被替代经验不继续注入。制作准备的缓存经验正文从旧观察中移除，以免同一经验出现两份。当前项目决定不会扩展原有授权，制作简报仍保留其确认时语义。

任务来源由公开 `memory_source(project_id, source_id)` 核对并读取；运行状态、原生模型自述及未知执行结果仍使用各自证据等级，不能据此标为采用或行为验证通过。
# 2026-09-10：画布与相机要求传递

原生制作首轮与续改保留运行时组装的 `execution_instructions`，不再在调用提供方时清空。显示要求包含宿主与 canvas CSS 尺寸一致、高分屏 drawing buffer 分离、准星与渲染中心一致，以及第一人称水平出生视角；诊断先测量布局，再判断相机。已有游戏须通过后续修改重新构建，提示词更新不改变历史候选。


## 七领域项目联通（2026-09-10）

新增同一项目原生 Agent 的 production.entities.read、production.entity.proposal、production.entity.organize、production.entity.adopt，以及 production.document.read。沿用任务授权、占用与版本检查；实体采用验证节点、材质与已采用动画身份。专业工具配置通过原对话交接。
