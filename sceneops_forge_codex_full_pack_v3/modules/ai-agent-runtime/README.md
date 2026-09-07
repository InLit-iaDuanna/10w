# 运行专家

S2 当前构建浏览器观察已接入产品 HTTP 入口、TaskTools 和结果面板；授权、部署配置、实测记录及限制见 [S2 浏览器观察](docs/S2_BROWSER_OBSERVATION.md)。

## Harness 批次 A：指令与上下文

类型化单动作入口现在由产品运行时装配公共制作指令、主制作角色和按需技能；卡片代码任务才加载游戏代码技能，基础资产和固定原型只得到各自相关的工具说明。`purpose='agent-action'` 通过提供方服务选择动作决策模式，三种传输只负责承载调用者选定的系统指令，不再替所有业务入口固定成只读顾问身份。讨论、顾问评估和规划入口仍保持只读，不因动作循环而扩大权限。

任务表继续保存完整动作输入与结果。下一轮模型上下文只投影动作状态、效果状态、短结果摘要和 `task-action://...` 引用；`code.file.write` 的旧/新全文不再随每轮历史重复发送。已授权模型可用 `agent.history.read` 从当前任务记录按引用重新读取历史写入正文或完整动作结果（包括文件读取与检查日志），不能跨任务解析引用。短交接摘要只陈述任务身份、最新动作和未解决动作；授权、预算和能力仍由运行时重新读取。

`assigned_role` 仍只是执行记录的领域标签。只有存在独立模型调用及其输入输出记录时，结果才可描述为独立 Agent 或独立评审。

## 游戏工程运行闭环

`card-development` 可由用户在新授权卡中选择 `allow_game_execution` 与 `allow_dependency_install`。前者加入固定 TypeScript 检查、Vite 构建和严格 localhost 预览，后者额外允许对当前登记卡片 worktree 执行禁用安装脚本的 pnpm 依赖准备。模型不能提供命令、目录、端口或环境变量；任务按钮调用同一个 `GameProjectRuntime`。源码写入会使旧检查、构建和预览失效，Agent 必须读取真实日志并重新验证。旧任务和未选择运行权限的任务继续以 `code_written` 结束。

公开路由 `GET /api/agent/tasks/{task_id}/game` 返回当前依赖、检查、构建、预览及日志状态；`POST` 只接受 `prepare | check | build | preview_start | preview_stop`。预览只服务当前 `dist`，仅监听 `127.0.0.1`，服务关闭时停止。完整实现与真实 Agent/浏览器证据见根目录 `GAME_PROJECT_RUNTIME_MILESTONE.md`。

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

`PrepareAgentTask` 支持 `task_profile='card-development'` 和必需的 `project_id/card_id`，只允许 typed-tools。通过 workspace 公开只读登记接口绑定实际worktree，不接管任意路径。新增 `code.workspace.inspect`、`code.file.read`、`code.file.write`，写入仍经原Harness ChangeSet和授权。源码结果以 `code_written / review_required` 交付，不宣称运行/编译通过。上下文回调由宿主注入，避免模块内部导入。测试和限制见根 `CARD_CODE_DEVELOPMENT.md`。

## Blender 原生资产往返

D4 内容入口增加「用 Blender 编辑」与「保存 Blender 源并同步导出」。旧授权保持原范围；「准备 Blender 编辑授权」通过原有限续授卡显式加入原生编辑和读取能力。Agent 使用相同的 `blender.asset.begin/edit/publish` 类型化动作与 Harness 审批、预算、任务占用；模型不提供文件路径或脚本。默认 Agent 无头、手工入口可见，完成回流后只关闭专用编辑会话。

`.blend` 候选从当前资产版本创建；程序化配方仅首轮转换，后续重开真实源。原配方版本保留，新版本不再显示无损配方编辑控件。导出、不可变文件保存、资产登记和引用应用分别记录。共享引用可按 `object_ids` 指定；部分应用冲突保留已保存源，通过当前场景版本继续应用，不再造资产版本。人工候选不能被模型编辑或发布，未知结果保留占用。

原生源的版本、真实工具与模型、Shell 证据及未完成验收见根目录 `BLENDER_NATIVE_ROUNDTRIP.md`。已有自定义游戏代码需要明确接入文件加载器；不自动改写普通行为源码。
