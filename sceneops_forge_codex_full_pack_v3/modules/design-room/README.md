# Design Room

## 卡片对话界面（2026-09-08）

卡片工作流采用紧凑深色侧栏：细线对话图标、对话数量、蓝色选中态及项目上下文说明。正文使用轻分隔表格和统一阅读宽度，输入区保持模型与权限入口；窄屏对话列表横向滚动。新建、切换、删除确认及执行权限沿用原有行为。验证：`journey-ui-smoke.test.tsx` 的 7 项烟测通过；浏览器连接超时，视觉验收尚未完成。

## 2026-09-08：卡片源码精修

卡片内可通过宿主提供的 `development.renderSourceEditor` 打开「架构与源码」；实际目录浏览、文件保存与限域 AI 修改归运行模块。未保存源码纳入宿主 dirty 提示。详见 [卡片源码精修](../ai-agent-runtime/docs/CARD_SOURCE_EDITOR.md)。

## 游戏技术方案与工程创建

正式策划版本之后不再只确认 Three.js。界面分别展示 Web 目标平台、Three.js 引擎／渲染技术和游戏代码架构；用户可手动选择对象／组件式或 ECS · Miniplex，也可让当前 AI 提供方推荐后再采用。确认会通过 Project Intake 创建真实工程，并把完整方案带入制作卡、建模上下文、卡片 worktree 和 Agent 开发任务。旧 `stack: threejs` 只表示渲染路线，不能推断代码架构。实现和验收见根目录 `GAME_CODE_ARCHITECTURE_MILESTONE.md`。

SceneOps 新生成工程在确认架构后创建选择性 Git 基线，方案同时记录策划版本、架构版本和基线提交。副本项目登记为 `existing_unadopted`，现有旅程会显示明确阻断状态，不会自动提交或复制源码。身份恢复与卡片基线规则见根目录 `GAME_PROJECT_IDENTITY_BASELINE_MILESTONE.md`。

制作卡片的代码开发入口会在执行前让用户选择是否授权工程检查、构建、本地预览和依赖准备。发送目标仍只产生授权卡；确认后，Agent 的检查、读取、写入与验证动作作为同一对话里的 Codex 风格流式记录直接展示，不再出现独立任务卡或额外任务历史按钮。构建完成并启动本地预览后，宿主会自动在右侧 Dockview 拉起真实运行页面；后续输入继续面向同一卡片 worktree。见根目录 `GAME_PROJECT_RUNTIME_MILESTONE.md`。

## 精简制作阶段

Three.js 单人原型只在项目页展示四条主制作线：`3D 世界`、`核心玩法`、`成长与反馈`、`完成 Demo`。地图、环境、角色与怪物外观、模型导入和新建、尺度归一化、相机、空间点位及场景搭建全部留在同一个 3D 工作流内，不再拆成十几张实现卡片。敌人类型、武器类型、对象池等属于工作流内部事项，不占用项目级卡片。

重新保存或确认合并后的卡片时，旧卡片集合写入 SQLite 的 `design_journey_card_history`，已有 Git worktree 记录和磁盘目录保持不变。主项目 JSON 继续使用原合同字段，因此正在运行的旧版本后端仍能读取四张新卡。

## 渐进式模型工具

公开 `CurrentModelingTool` 为四边工作区提供当前制作卡片、建模会话和模型产物的专用承载区。它不增加第二个聊天框：模型描述仍由唯一主对话完成，工具区只负责选择卡片或会话、导入、预览、归一化和存入资产库。工具区通过同一 `journeyKey` 读取状态，切换会话仍调用既有 Journey 命令。

`3D 世界`卡片的宽输入框外、紧邻输入框上方直接提供“新建模型”和“搭建世界”两个入口，不要求用户先到右侧资产面板寻找。进入卡片后不再重复显示此前从 idea 到正式策划的过程记录，初始正文保持干净；原卡片式模型来源选择也不再占据对话正文。模型需求已有内容后，输入区旁显示“确认并建模”：点击会把当前会话交给 Asset Factory。右侧仍是原来的“环境场景”面板和上下卡片，只把上方画布切成真实 Three.js 模型预览，把下方卡片切成缩放、前后左右视图、按角度旋转、版本与入库操作。首版生成后，同一会话里的后续描述继续追加该模型的新版本。两条制作流共用当前正式策划版本、技术路线和活动卡片组成的项目记忆，底层分别保存模型会话和环境场景历史。

## 卡片资产来源与建模子对话（增量）

卡片可选择导入或新建。新建进入关联该卡片的需求子对话，仍复用唯一输入框与提供方；默认按轮廓、比例、表面、交互四个大块逐一对齐，而不是连续展示大量细碎问题。全局“对齐详细程度”可设为精简 2 块、标准 4 块、深入 8 块，达到上限后生成摘要；后续仍可直接描述微调。返回卡片、切换来源不会删除另一条记录；从卡片返回主对话会恢复进入前的阅读位置。选择来源本身不调用模型；通用源码任务降为高级入口。

Design Room 只拥有来源选择、问题分块和建模对话；实际文件处理由宿主注入 Asset Factory 的公开 `CardAssetWorkflow`，没有跨模块内部导入。每条新用户回答带稳定消息 ID 交给 Asset Factory；右侧独立 Three.js 面板展示真实执行状态、GLB、尺寸、网格统计和历史版本。模型生成说明与真实资产结果分开，只有 Blender 成功写出并回读的版本才显示为就绪。当前统一入口也连接图片参考上传、GLB/FBX 导入、FBX 导出和另存归一化版本。它不自动提交/合并 Git，也未连接 GLB 压缩或下游场景采用。最小真实 Blender 与 CodeBuddy → Blender 烟测均在隔离临时 Git 工程中通过；不因此宣称完整资产生产链完成。

## Git 分支上下文与修改提案

`select_card` 是用户明确的目录/分支准备动作，先持久化导出意图，再经 workspace 公开接口创建/复用 Git worktree。模型不能产生 Git 权限或命令。`RevisionReply` 返回修改提案，`accept_change` 核对原大纲/卡片后采用，`reject_change` 保留原数据；不自动确认正式版本。历史版本、Git 提交映射和活动卡片是独立字段，避免改写不可变快照。见根 `GIT_CARD_BRANCHES.md`。

### 单题选项与实时正文

`PlanningQuestion` 持有一个问题、2至3个选项和推荐项；用户确认后才提交并产生关联回答。普通策划回复为 Markdown，grill-me 输出为结构化卡片；`command/stream` SSE 通过 ProviderService 的实际回调展示正文/思考（如有）。最终已保存状态替换临时流，不模拟 token。客户端可停止请求。结构化回复的 JSON 解析、必填字段、类型、额外字段和领域约束均在每次调用内校验；失败时，策划服务把失败原因加入同一请求并使用同一提供方和模型自动纠正一次，总计最多两次调用。第二次仍未通过应用结构校验时返回上游回复错误（HTTP 502），不归为用户输入错误；网络等其他错误不自动重试。失败保留输入供手动重试，调用次数如实记录。当前界面保持一个主输入，不启用每步骤独立工作台。

## 单人协作策划（2026-09-06）

新增公开 `PlanningJourneyService`、`create_journey_router` 和前端 `PlanningJourneyGate`，文件夹项目在唯一主对话中按 idea → grill → outline → stack → cards 推进。用户明确触发追问、生成和版本确认，模型不能审批或启动制作。卡片只是策划交接草稿，不创建 Harness 任务。存储通过 workspace 公开固定用途接口完成；不直接写生产文件。大纲/卡片编辑绑定原 revision，导出状态持久化后才写不可变快照；中断不重放模型。详情见根 `PLANNING_JOURNEY_STAGE1.md`。

恢复本机项目登记后，首次读取策划旅程会校验项目文件夹内的 `.sceneops/design/draft.json`，并在 Project ID 一致时把完整消息、阶段、版本、制作卡片和子对话同步回本机 SQLite。项目身份不一致或草稿损坏时明确阻止导入，不显示成空白新对话。

读取恢复后的旅程也会核对并补回缺失的设计版本、游戏工程基线和卡片 worktree 登记。只有项目草稿与 Git 快照、标签、提交祖先关系、分支和卡片说明全部吻合时才恢复，因此中断的“进入 Git 分支”可以安全重试，来源不明的标签仍不会被接管。

项目确认移动后，Journey 返回 workspace 当前登记的根目录，并同步修正技术方案中的 scaffold 根路径；项目内旧路径字段不再覆盖当前本机绑定。

普通制作卡片讨论按卡片独立持久化并在该工作流内显示，不再写入主策划记录后被卡片界面隐藏。流式回复完成或失败时会同步清理临时正文与思考状态，已保存回答替换临时展示。

主策划页在项目策划状态中保存进入制作线时的阅读位置；进入任一制作线再返回、刷新或组件重载后都会回到离开前的位置。核心玩法、成长反馈和 Demo 交付三条线共用“普通讨论 → 逐题对齐本轮实现 → 生成有界切片摘要 → 准备 Coding 授权 → 用户确认后执行”的交接。普通回复和历史任务都不能解锁 Coding；开发快照必须包含对应卡片的对齐摘要，每次只实现一个可试玩、可构建、可观察验收的增量切片。

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

## 制作卡片对齐与执行确认

有技术方案的项目首次进入任意制作卡片（包括 3D 世界）时自动提出一个范围问题；重入保留历史，不重新发起对齐。旧讨论继续作为上下文，不清空。用户可在已经讨论后调用 `finish_card_alignment` 提前结束，或在当前详细程度的问题上限收束。两条路径都只生成最小可试玩切片摘要，并询问是否确认执行；Design Room 不创建或授权执行任务。

`card_alignment_summary_ids` 保存摘要消息 ID，开发上下文通过 `card_alignment_id` 暴露该轮身份。后续讨论或重新对齐清除旧摘要及 ID，必须基于新范围重新确认；已有任务授权不会由策划文字自动扩大。没有技术方案的历史项目保留旧讨论入口，需先确认技术方案才能完成实现对齐。

### D4 初版方向入口

初版入口继续由宿主接入 `project-demo-agent`。摘要优先读取已有初版方向、结构化策划字段；没有策划时带入用户对话原文（界面明确为最多 1000 字的摘录），不调用模型进行导航，不使用钥匙门作为默认目标。视角、范围与架构没有可靠来源时保持空白，确认按钮要求用户补齐。已有技术方案的明确架构可以复用；任何带入值仍是可编辑、尚未确认的草稿。编辑后服务刷新不覆盖用户正在填写的摘要。详细策划、大纲版本与四卡入口保留在“高级路径”中。

## 卡片输入区更新

输入区使用紧凑的两层布局：文本区与底部配置区分离，模型／思考强度／权限在左，发送／停止固定在右；窄容器隐藏键盘提示并允许配置换行。发送、停止、权限使用模块自有一致描边 SVG。保留原模型设置、权限选择、IME、发送和取消逻辑；不再用泛化 dirty 状态显示不准确的“保存中”。

`journey-ui-smoke.test.tsx` 的 7 项烟测通过，改动 TSX 语法检查通过。当前浏览器连接超时，未完成最终截图复核。

## 统一项目聊天外观（2026-09-08）

主策划、制作卡片、建模、环境对话与普通项目对话使用 Core UI 的公开 ChatComposer 与 ChatMessageActions；共享 720px 阅读宽度、消息排版、表格、气泡、复制操作、模型工具栏和发送按钮。卡片侧栏与预览面板仍属于工作流布局，消息区不再另设一套外观。输入内容、发送/取消处理、权限及服务端历史仍由原调用方持有。

验证：共享输入框单条烟测通过，覆盖草稿保留、模型按钮不触发提交、禁用发送与正常提交；本地策划聊天窄分栏已目视检查。未执行完整测试或真实 AI 请求。

## 项目工具更新

公开 `ProjectPlanningTools`，承载大纲／卡片查看及登记源码卡片选择；源码 UI 通过宿主回调组合，不直接访问文件。

## 对话到制作

新项目主入口使用 discuss_game：模型返回一个关键问题、可审阅 DemoDirectionDraft 或普通讨论；无需手动切换 grill/大纲/卡片步骤。准备好的摘要由“开始制作”沿用 confirm_demo_direction 创建登记工程，再经宿主启动执行。execution_policy 是独立用户字段，set_execution_policy 持久保存 ask/full-access；结构化模型回复禁止携带权限。历史工作流与已有项目数据保留。

定向测试：backend/tests/test_project_discussion.py；frontend/src/tests/project-conversation.test.tsx。

制作摘要现在包含结构化 `camera_mode`。AI 根据玩法选择，不要求用户填写相机参数；模型漏填相机策略时结构校验拒绝，旧项目持久数据允许空值，执行系统从已确认视角判断并说明。该枚举只选择固定系统规则，用户正文不会被拼成高优先级指令。

## 从现有初版进入分项制作（2026-09-09）

主对话和「策划与制作卡片」提供「基于当前版本整理策划」。`organize_production` 通过宿主注入的制作观察端口读取当前原生制作工程、源码登记及近期制作目标，生成结构化大纲与实际源码绑定的卡片。草稿不会自动确认；已有策划采用现有修改提案审阅。每张卡保存 `source_ids`，旅程保存 `production_basis`（原制作记录和工作区）。源码生成的几何体仍显示为源码驱动，不冒充托管模型资产。

确认大纲后进入卡片，共用原游戏和原生会话，不创建旧式卡片 worktree；旧分支卡片继续走原路径。卡片讨论读取当前关联源码，主输入框可确认本轮修改，或在完全访问模式直接发送。执行前核对卡片工作区和实际源码身份；源码被删除、会话缺失或制作仍在运行时给出明确错误。卡片不是独立权限沙箱，原授权继续生效，必要的共享文件改动由 Agent 说明。卡片源码与试玩入口复用运行模块的公开视图。

整项目整理使用公开 ProviderService 的 600 秒请求时限，并保留用户停止操作；普通对话时限不变。首次真实 `test123` 整理曾触发默认 CodeBuddy 短请求超时，原策划未被覆盖。卡片草稿在大纲确认前即可查看，进入制作仍需先确认版本。


### 对话中的项目记忆

策划回复的依据关联 `journey:{project_id}:message:{assistant_message_id}`，生成前分配消息 ID；用户与回复的学习材料归到同一回复，纠正操作仍关联原用户消息。普通讨论、制作卡片与建模对话使用同一机制。

已确认初版方向通过 `project_memory` 公开读取，引用当前策划版本；核心体验、视角风格及初版范围的纠正交回 `confirm_demo_direction` 命令，沿用版本检查、工程架构约束与草稿导出。工程架构和平台显示为只读事实，不能由记忆更新绕开迁移流程。

当前前台响应可提出带原话引用的 `memory_updates`。只有该回合新保存的用户消息可以作为来源；回复先持久保存，再应用修订。关闭自动学习仍允许用户纠正。未经确认的草稿不会被复制成已确认项目决定。
# 2026-09-10：首版续改确认

首版后的修改确认显示在输入框上方、制作记录滚动区之外，避免长制作报告遮住待确认操作。确认后仍通过既有续改入口恢复原制作会话；执行权限规则不变。
