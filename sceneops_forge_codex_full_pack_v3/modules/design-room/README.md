# Design Room

## 游戏技术方案与工程创建

正式策划版本之后不再只确认 Three.js。界面分别展示 Web 目标平台、Three.js 引擎／渲染技术和游戏代码架构；用户可手动选择对象／组件式或 ECS · Miniplex，也可让当前 AI 提供方推荐后再采用。确认会通过 Project Intake 创建真实工程，并把完整方案带入制作卡、建模上下文、卡片 worktree 和 Agent 开发任务。旧 `stack: threejs` 只表示渲染路线，不能推断代码架构。实现和验收见根目录 `GAME_CODE_ARCHITECTURE_MILESTONE.md`。

制作卡片的高级代码开发入口现在会在准备任务前让用户选择是否授权工程检查、构建、本地预览和依赖准备。发送目标仍只产生授权卡；确认后，Agent 与任务卡按钮共用运行能力，并可从任务卡回到同一 worktree 继续修改。见根目录 `GAME_PROJECT_RUNTIME_MILESTONE.md`。

## 精简制作阶段

Three.js 单人原型只在项目页展示四条主制作线：`3D 世界`、`核心玩法`、`成长与反馈`、`完成 Demo`。地图、环境、角色与怪物外观、模型导入和新建、尺度归一化、相机、空间点位及场景搭建全部留在同一个 3D 工作流内，不再拆成十几张实现卡片。敌人类型、武器类型、对象池等属于工作流内部事项，不占用项目级卡片。

重新保存或确认合并后的卡片时，旧卡片集合写入 SQLite 的 `design_journey_card_history`，已有 Git worktree 记录和磁盘目录保持不变。主项目 JSON 继续使用原合同字段，因此正在运行的旧版本后端仍能读取四张新卡。

## 渐进式模型工具

公开 `CurrentModelingTool` 为四边工作区提供当前制作卡片、建模会话和模型产物的专用承载区。它不增加第二个聊天框：模型描述仍由唯一主对话完成，工具区只负责选择卡片或会话、导入、预览、归一化和存入资产库。工具区通过同一 `journeyKey` 读取状态，切换会话仍调用既有 Journey 命令。

## 卡片资产来源与建模子对话（增量）

卡片可选择导入或新建。新建进入关联该卡片的需求子对话，仍复用唯一输入框与提供方；默认按轮廓、比例、表面、交互四个大块逐一对齐，而不是连续展示大量细碎问题。全局“对齐详细程度”可设为精简 2 块、标准 4 块、深入 8 块，达到上限后生成摘要；后续仍可直接描述微调。返回卡片、切换来源不会删除另一条记录。选择来源本身不调用模型；通用源码任务降为高级入口。

Design Room 只拥有来源选择、问题分块和建模对话；实际文件处理由宿主注入 Asset Factory 的公开 `CardAssetWorkflow`，没有跨模块内部导入。每条新用户回答带稳定消息 ID 交给 Asset Factory；右侧独立 Three.js 面板展示真实执行状态、GLB、尺寸、网格统计和历史版本。模型生成说明与真实资产结果分开，只有 Blender 成功写出并回读的版本才显示为就绪。当前统一入口也连接图片参考上传、GLB/FBX 导入、FBX 导出和另存归一化版本。它不自动提交/合并 Git，也未连接 GLB 压缩或下游场景采用。最小真实 Blender 与 CodeBuddy → Blender 烟测均在隔离临时 Git 工程中通过；不因此宣称完整资产生产链完成。

## Git 分支上下文与修改提案

`select_card` 是用户明确的目录/分支准备动作，先持久化导出意图，再经 workspace 公开接口创建/复用 Git worktree。模型不能产生 Git 权限或命令。`RevisionReply` 返回修改提案，`accept_change` 核对原大纲/卡片后采用，`reject_change` 保留原数据；不自动确认正式版本。历史版本、Git 提交映射和活动卡片是独立字段，避免改写不可变快照。见根 `GIT_CARD_BRANCHES.md`。

### 单题选项与实时正文

`PlanningQuestion` 持有一个问题、2至3个选项和推荐项；用户确认后才提交并产生关联回答。普通策划回复为 Markdown，grill-me 输出为结构化卡片；`command/stream` SSE 通过 ProviderService 的实际回调展示正文/思考（如有）。最终已保存状态替换临时流，不模拟 token。客户端可停止请求，失败保留输入供手动重试。当前界面保持一个主输入，不启用每步骤独立工作台。

## 单人协作策划（2026-09-06）

新增公开 `PlanningJourneyService`、`create_journey_router` 和前端 `PlanningJourneyGate`，文件夹项目在唯一主对话中按 idea → grill → outline → stack → cards 推进。用户明确触发追问、生成和版本确认，模型不能审批或启动制作。卡片只是策划交接草稿，不创建 Harness 任务。存储通过 workspace 公开固定用途接口完成；不直接写生产文件。大纲/卡片编辑绑定原 revision，导出状态持久化后才写不可变快照；中断不重放模型。详情见根 `PLANNING_JOURNEY_STAGE1.md`。

Design Room 把项目意图组织成 Project Bible、结构化 GDD 和可执行的 Feature Spec。三者都使用显式字段、稳定 ID 和状态，而 Bible 与 Feature Spec 另外提供版本与结构 diff；它们都不是不可检查的 Markdown 大字段。

## 公开编辑器

- `project.bible`：游戏目标、目标玩家、核心循环、视听/交互/命名规则、平台预算、禁止修改项和已批准决策。
- `design.gdd`：设计支柱、玩家体验目标、结构化玩法系统、进程、世界结构、经济、失败恢复和依赖。
- `design.feature_spec`：目标、输入/输出、依赖、边界情况、验收标准，以及资产、场景、脚本、UI、音频、VFX、测试需求。

## 命令与安全

对话命令 `design.feature_spec.draft_from_conversation` 只创建草稿，并把模型推断放入 `assumptions`，初始状态一律 `unconfirmed`。它返回统一的 `workbench.open_editor` 动作，不创建生产任务。

AI 修改已有 Bible 或 Feature Spec 时先通过 `design.change.propose` 产生 `DesignChangeSet`，其中包含 base version、前后值、理由、影响、风险、验证与回滚计划以及审批要求。只有持有 `design:approve` 权限的 `design.change.approve` 才能应用；base version 已变化时拒绝应用。

Feature Spec 通过项目入口、内容完整性和未确认假设检查后，才会发出 `design.feature_spec.marked_ready@1`。该 event 是给 Production Planner 的数据边界，本模块不复制排期、任务拆分或里程碑逻辑。

## 公开合同

- Commands：见 `module.yaml`
- Events：`design.project_bible.versioned@1`、`design.feature_spec.versioned@1`、`design.feature_spec.marked_ready@1`、`design.decision.recorded@1`
- 权限：`design:read`、`design:write`、`design:approve`
- 依赖：只使用 `project-intake` 公开入口；不引用其内部文件

## 版本、diff 与决策

Bible 和 Feature Spec 每次保存产生不可变版本快照。diff 使用 JSON Pointer 路径返回 `added`、`removed`、`changed`，顺序确定。决策记录要求先逐项拒绝未选方案并写理由，再接受唯一方案；结果保留所有 alternatives 的处置与理由。

## 测试

```bash
cd modules/design-room/frontend
npm test
```

fixtures 包含 Find My Way Home 的钥匙开门分支，以及 Warehouse Escape 的开关/门/出口规格。JSON 合同示例位于 `contracts/examples/`。

## 当前集成状态

模块逻辑、mock fixtures 和独立测试可运行。由于起点尚无 core runtime、API persistence、ForgeShell 和 Production Planner，真实 React/Dockview 渲染、生成 catalog、服务端持久化和 planner 消费当前是 **planned/blocked by prerequisites**。本文不把它们描述为 live。


## 独立 Web 工作台（本轮新增）

现在可从应用根运行 `pnpm --dir apps/labs/project-planning dev`，访问 http://127.0.0.1:4311。
首次依赖安装、运行事实、手动路径及限制见 [工作台说明](../../apps/labs/project-planning/README.md)。
公开 `loadDesignPanel()` 返回真实 React 懒加载组件；旧 headless view model 与命令保持兼容。

以上旧文中的 React/跨模块规划 blocked 描述仅适用于原始模块交付；本轮独立工作台已连通。
正式 Shell 注册、统一身份与生产级持久化仍未接入，不能将独立 lab 当作已接入完整 Shell。

## CodeBuddy AI 与模型选择

独立工作台设计页新增 CodeBuddy 模型下拉框，模型来自本机 `codebuddy --help` 当前声明列表。点击生成才发起 AI 请求；不自动选模型、不自动切换备用模型。API 使用 `codebuddy --print --model <id> --output-format json --json-schema ...`，通过 stdin 传 brief 和当前六个设计字段。

后端公开包 `sceneops_design_ai` 注册 `/v1/design-ai/models` 和 `/suggest`。Pydantic 拒绝无效结构化结果；CLI 缺失、模型不可用、退出失败和超时均有明确错误。CLI 从隔离空目录启动，内置工具禁用、MCP 为空、会话不持久化，不启用 bypassPermissions 或修改宿主权限。

AI 建议记录 provider/model/request ID/live 来源，先通过原 `design.change.propose` 生成可查看前后差异的 ChangeSet；点击“批准并应用建议”才调用 `design.change.approve`，保留 base version 检查。批准后假设仍未确认，需要人工确认才能规划。设计/规划整体仍为隔离 mock，AI 来源的 live 不代表生产执行完成。

验证：CLI 帮助导入及模型发现成功；一条本地适配器烟测通过（mock CLI transport，确认所选模型传入 argv 并验证结构化结果）；没有调用真实 AI 推理，其他测试 not run / pending approval。
