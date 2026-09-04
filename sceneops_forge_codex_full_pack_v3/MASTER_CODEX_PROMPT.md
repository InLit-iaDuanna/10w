# SceneOps Forge — Codex 总开发任务

你是本仓库的 **Principal Engineering Agent、产品架构师、集成负责人和多代理编排者**。你的任务不是只给方案，也不是只搭一个漂亮外壳，而是持续工作，直到仓库形成一套可运行、可测试、可扩展、可演示、可交接的 AI 原生 3D 游戏全链路生产工作台。

你可以并且应该：

- 新开子对话处理边界清楚的任务；
- 调用 Subagent 并行完成探索、实现、测试、审查和文档；
- 按任务难度路由不同模型；
- 使用独立分支或 Git worktree 隔离并行写入；
- 在本机条件允许时调用浏览器、Blender、Unity、ComfyUI、Git、测试和构建工具；
- 在外部工具暂时不可用时先完成严格标注的 Mock/Cached 路径，但不得把它们冒充 Live。

你必须持续推进，不要在完成计划后停下。只有出现真正需要宿主机人工操作、凭证、许可证确认或不可逆审批时，才暂停并给出最小、精确的一步操作。

---

## 0. 必读文件与指令优先级

开始前完整阅读：

1. `AGENTS.md`
2. `product.md`
3. `design.md`
4. `architecture.md`
5. `MODULE_CONTRACT.md`
6. `FRONTEND_INTEGRATION.md`
7. `MODEL_ROUTING.md`
8. `SUBAGENT_ORCHESTRATION.md`
9. `DEFINITION_OF_DONE.md`
10. 当前仓库已有源码、README、配置、测试与文档

若目录内存在更近的 `AGENTS.md`，遵守其模块级规则；根目录的安全、来源追踪、身份链和诚实标记规则不可被覆盖。

开始编码前必须：

- 审计现有仓库；
- 创建或更新 `STATUS.md`；
- 创建或更新 `EXECUTION_PLAN.md`；
- 创建或更新 `docs/decisions.md`；
- 创建或更新 `docs/risk-register.md`；
- 标明每项能力是 `live`、`mock`、`cached`、`planned` 还是 `blocked`；
- 识别可复用代码，禁止重复造轮子；
- 冻结第一版核心合同和模块边界。

不要先重写视觉。不要先接更多外部工具。先让模块运行时、聊天首页、工具窗口和一条纵向生产链成立。

---

# 1. 产品目标

构建：

# SceneOps Forge

**AI 原生 3D 游戏全链路生产工作台**

一句话承诺：

> 从一句需求，到一个经过验证的可玩版本；从玩家问题，到可追溯的修复与发布。

完整生产数字线程：

```text
Project Brief
→ Project Bible / GDD
→ Feature Spec
→ Production Tasks
→ Concept / Asset Spec
→ 3D Asset / Character / Animation
→ World / Level
→ Gameplay Logic / UI / Audio / VFX
→ AI Render / Review
→ Blender / Unity Integration
→ Build
→ AI Playtest
→ Issue Backpin
→ ChangeSet
→ Regression
→ Release / Rollback
```

系统的价值不在于接入多少软件，而在于每一步都具备：

- 结构化输入；
- 明确责任人或 Agent；
- 可执行输出；
- 版本与来源；
- 质量门禁；
- 人工审批；
- 失败、重试与恢复；
- 下一阶段的稳定接口；
- 从玩家反馈回到生产源头的闭环。

核心指标：

1. `Brief-to-Playable Time`
2. `Issue-to-Verified-Fix Time`
3. 新项目接入到首个成功构建的时间
4. 生产链端到端成功率
5. AI测试问题回钉准确率

严禁硬编码或编造指标。

---

# 2. 首页与工作台交互：Chat-First Pull-Out Workspace

首页必须严格满足以下体验：

## 2.1 初始状态只有对话

首次打开或进入 `Home` 工作区时：

- 不显示传统 Dashboard；
- 不显示固定左侧导航；
- 不显示固定右侧 Inspector；
- 不显示常驻底部 Console；
- 不使用大面积卡片矩阵；
- 屏幕中央只有对话历史、欢迎语和输入框；
- 屏幕四条边仅保留极轻的可发现拉起热区；
- 必要状态只允许以角落小型状态点或对话中的状态卡出现。

默认 Editor 为：

```text
assistant.conversation
```

对话既是项目入口，也是命令面。用户可以说：

```text
创建一个第三人称探索游戏项目
打开当前场景
拉出资产库
把渲染窗口放到右侧
运行从概念到Unity资产流程
让AI玩家测试寻找钥匙任务
```

Assistant 返回结构化动作卡，用户确认后可：

- 打开工具；
- 拉起边缘抽屉；
- 新建 Workspace；
- 运行工作流；
- 生成 ChangeSet；
- 请求审批；
- 跳转到具体对象、版本、构建或 Issue。

对话不能绕过权限和审批。对话调用的是与按钮相同的 Typed Command。

## 2.2 上下左右拉起工具

四边均支持拖拽拉起：

- 左：工具库、场景树、资产树、项目结构；
- 右：属性、AI上下文、ChangeSet、审核；
- 上：项目切换、命令搜索、Agent状态、工作流启动；
- 下：时间线、日志、构建队列、渲染队列、试玩步骤。

每条边支持：

```text
hidden → peek → pinned
```

交互要求：

- 鼠标进入边缘热区时显示克制的拉手；
- 拖动距离实时决定抽屉尺寸；
- 短拉为 Peek，进一步拉出可 Pin；
- Peek 可覆盖内容；Pinned 必须重排中央区域；
- 必须有按钮、菜单和快捷键替代拖拽；
- Judge Mode 中拉手更明显，避免评委不知道可以拉起。

## 2.3 工具窗口与 Blender 式 Area

工具不是固定页面，而是可组合 Editor：

- 作为标签加入现有 Area；
- 向左、右、上、下拆分；
- 拖回四边抽屉；
- 变成浮动窗口；
- 弹出到另一浏览器窗口；
- 最大化当前 Area；
- 保存为 Workspace 布局；
- 切换 Area 当前 Editor 类型。

使用 `dockview-react` 作为唯一 Docking 引擎。不要自己开发 Dock 系统，不要同时引入多个冲突的布局库。

## 2.4 对话与工具的关系

- 初始只有对话；
- 打开第一个工具后，对话可留在中心、缩成标签或停靠到任意区域；
- 用户随时可以按命令将对话最大化回到首页状态；
- 对话是编排入口，不是所有功能的唯一界面；
- 3D、图谱、资产、渲染、代码、构建和测试必须拥有专业 Editor；
- Assistant 可以建议打开工具，但不得突然重排用户布局，除非用户确认或当前运行的是明确的预置演示流程。

---

# 3. 模块化开发：每个功能一个独立文件夹

整个系统必须采用 **Feature Module Monorepo**。每一项可独立理解、开发、测试和禁用的产品能力都位于独立模块文件夹。

顶层结构：

```text
sceneops-forge/
├─ apps/
│  ├─ web/                    # 只负责启动、全局Provider与静态模块注册
│  └─ desktop-bridge/         # 可选，本地工具桥接外壳
├─ services/
│  ├─ api/                    # 只负责核心启动与模块Router注册
│  └─ orchestrator/           # 工作流运行与Worker协调
├─ packages/
│  ├─ core-contracts/
│  ├─ core-events/
│  ├─ core-auth/
│  ├─ core-storage/
│  ├─ core-ui/
│  ├─ scene-viewer/
│  └─ test-kit/
├─ modules/
│  └─ <module-id>/
├─ integrations/
│  ├─ blender-addon/
│  ├─ unity-package/
│  └─ comfyui-adapter/
├─ examples/
│  ├─ remember-home/
│  └─ warehouse-escape/
├─ .codex/
├─ .agents/
└─ docs/
```

每个模块遵循：

```text
modules/<module-id>/
├─ AGENTS.md
├─ README.md
├─ module.yaml
├─ contracts/
├─ frontend/
│  └─ src/
│     ├─ index.ts
│     ├─ manifest.ts
│     ├─ editors/
│     ├─ components/
│     ├─ commands/
│     ├─ hooks/
│     ├─ state/
│     ├─ fixtures/
│     ├─ generated/
│     └─ tests/
├─ backend/
│  └─ src/<python_package>/
│     ├─ __init__.py
│     ├─ router.py
│     ├─ schemas.py
│     ├─ service.py
│     ├─ repository.py
│     ├─ jobs.py
│     └─ tests/
├─ workers/
├─ adapters/
├─ workflows/
├─ e2e/
└─ docs/
```

模块可省略不需要的子目录，但不得将其代码随意放到别的模块。

硬性规则：

- `apps/web` 不包含业务功能；
- `services/api` 不包含模块业务逻辑；
- 模块只能依赖 `packages/core-*` 和 `module.yaml` 中明确声明的公开模块接口；
- 禁止从另一个模块的内部路径导入；
- 跨模块通过 Typed Command、Typed Event、公开服务接口或稳定ID通信；
- 每个模块仅从 `index.ts` / `__init__.py` 暴露公共面；
- 每个模块拥有自己的测试、Fixtures、README和变更说明；
- 每个模块可以通过 Feature Flag 禁用；
- 每个模块可独立运行其测试；
- 不建立过度动态、不可调试的运行时插件系统；模块清单在构建时显式生成并校验。

先实现 `module-runtime`，再开发业务模块。

---

# 4. 必须存在的模块

以下模块均需创建独立文件夹并提供 `module.yaml`、README、测试和至少一个可工作的能力。核心模块需要深度实现；辅助模块至少形成可用纵向路径，不得仅留空白页。

## 4.1 平台核心

1. `core-kernel`
   - 稳定ID、项目上下文、产物、审批、权限、来源、运行模式。
2. `module-runtime`
   - 模块发现、清单校验、Editor/Command/Event/Job注册、依赖检查、Feature Flag。
3. `conversation-home`
   - 只有对话的首页、结构化动作卡、工具打开与工作流启动。
4. `forge-shell`
   - Dockable Workspace、四边拉起、Area、Editor、布局保存、Judge Mode。
5. `integration-center`
   - Blender、Unity、ComfyUI、Git、Artifact Store、LLM、Worker健康状态。
6. `observability`
   - 日志、事件、运行历史、指标、错误关联和追踪。

## 4.2 项目与策划

7. `project-intake`
   - 新项目创建、现有项目扫描、目标平台、目录和团队信息。
8. `design-room`
   - Project Bible、GDD、Feature Spec、设计决策和验收标准。
9. `production-planner`
   - 任务拆解、依赖、里程碑、人员/Agent分配、风险和进度。
10. `concept-lab`
    - Moodboard、Style Bible、概念版本、多视图、资产Brief和审批。

## 4.3 资产与内容生产

11. `asset-library`
    - 模型、材质、动画、贴图、声音、Recipe、来源、搜索、使用关系。
12. `asset-factory`
    - AssetSpec、模型导入/生成、清理、UV、PBR、LOD、Collider、发布。
13. `character-animation`
    - Character Bible、Rig、Skin、动作重定向、动画状态、预览和检查。
14. `world-composer`
    - 场景、灰盒、对象摆放、3D标记、路径、NavMesh、灯光和区域。
15. `logic-studio`
    - Feature到状态机、交互关系、C#变更、对话/任务图、自动测试。
16. `ui-studio`
    - UI Flow、HUD、菜单、Unity UI资产、分辨率、适配和视觉测试。
17. `audio-studio`
    - 音效/配音任务、素材、响度/峰值检查、AudioSource和Mixer配置。
18. `vfx-shader`
    - VFX/Shader Recipe、参数、预览、性能预算和事件绑定。

## 4.4 渲染、引擎、版本与测试

19. `render-ops`
    - AOV、AI LookDev、材质/灯光方案、镜头、写回、验证渲染和Render Manifest。
20. `engine-unity`
    - Unity扫描、Stable ID映射、导入、Prefab、组件、测试、Profile和构建。
21. `version-collaboration`
    - Git/LFS、评论、指派、审批、文件/语义/视觉/行为Diff、回滚。
22. `ai-playtest`
    - Smoke、Goal-driven、Explorer、Destructive代理，轨迹、Telemetry、Issue Backpin、回归。
23. `build-release`
    - 构建矩阵、Release Candidate、门禁、部署、Patch Notes、回滚和反馈回流。
24. `judge-demo`
    - 一键演示、预置数据、Live/Cached切换、重置、演示脚本、离线路径。

---

# 5. 核心数据与生产数字线程

所有模块必须围绕同一条数据链协作：

```text
Project
→ ProjectBible
→ FeatureSpec
→ ProductionTask
→ ConceptSpec
→ AssetSpec
→ AssetVersion
→ SceneSnapshot
→ SceneObject
→ GameplayComponent
→ RenderJob
→ BuildRun
→ PlaytestRun
→ Issue
→ ChangeSet
→ RegressionComparison
→ Release
```

核心合同必须单一来源，至少包括：

- `Project`
- `ProjectBible`
- `FeatureSpec`
- `AcceptanceCriterion`
- `ProductionTask`
- `ConceptSpec`
- `AssetSpec`
- `AssetVersion`
- `CharacterSpec`
- `AnimationClipSpec`
- `SceneSnapshot`
- `SceneObject`
- `SceneOpsIdentity`
- `SpatialAnnotation`
- `SpatialContextPacket`
- `GameplayGraph`
- `ChangeSet`
- `TypedCommand`
- `Approval`
- `PolicyGate`
- `GateResult`
- `RenderRecipe`
- `RenderJob`
- `BuildRun`
- `TestCase`
- `PlaytestRun`
- `PlaytestStep`
- `Issue`
- `RegressionComparison`
- `Release`
- `Artifact`
- `ArtifactProvenance`
- `IntegrationHealth`
- `PipelineRun`
- `PipelineNodeRun`

网络合同以 Backend Pydantic/OpenAPI 为事实来源，前端类型自动生成。磁盘Manifest使用版本化JSON Schema。不得在前端手工复制相同结构。

---

# 6. Stable Scene ID

所有3D对象必须使用 `sceneops_id`，身份链必须成立：

```text
Blender custom property
→ glTF extras / export manifest
→ Web viewer userData
→ Unity SceneOpsIdentity component
→ Runtime telemetry
→ Playtest Issue
→ Backpin
```

规则：

- 重命名保持ID；
- 复制产生新ID；
- 对象名称、层级路径、文件路径和数组索引不得作为主身份；
- 所有转换、复制、合并和导入行为必须测试；
- 资产ID与场景实例ID分开；
- 一个Unity Prefab实例必须可追溯到源资产版本和Blender对象。

---

# 7. AI修改安全模型

任何AI或用户触发的工程修改都必须先产生 Typed `ChangeSet`：

```text
draft
→ planned
→ awaiting_approval
→ executing
→ validating
→ completed / rejected / failed / rolled_back
```

ChangeSet必须包含：

- 基础版本；
- 目标模块/工具；
- 目标对象；
- 原值；
- 新值；
- 原因；
- 预期结果；
- 影响范围；
- 风险级别；
- 验证计划；
- 回滚计划；
- 需要的审批角色。

禁止在应用运行时暴露任意 Python、C#、Shell 或文件系统执行。Blender、Unity、Git和构建工具仅通过白名单Typed Command工作。

所有外部操作提供：

- dry-run；
- timeout；
- cancellation；
- retry；
- structured logs；
- idempotency key；
- progress；
- rollback或补偿动作；
- Live/Mock/Cached标记。

---

# 8. 完整生产工作流

## 8.1 Brief to Playable

```text
对话输入需求
→ Project/Feature Spec
→ AI制作人拆任务
→ 概念与资产Brief
→ 资产工厂
→ Blender处理
→ Unity导入
→ 场景摆放
→ 逻辑/UI/音频/VFX
→ Render Review
→ 测试构建
→ AI试玩
→ Issue与修复
→ 回归
→ Release Candidate
```

## 8.2 Concept to Engine Asset

```text
ConceptSpec
→ AssetSpec
→ 生成/导入基础模型
→ Geometry QA
→ UV/PBR
→ LOD/Collider
→ Turntable/AOV
→ 审批
→ AssetVersion
→ Unity Prefab
```

## 8.3 Character to Playable

```text
Character Bible
→ Model
→ Rig/Skin
→ Animation Clips
→ Retarget
→ Animator State
→ Unity Character Prefab
→ Play Mode Test
```

## 8.4 Scene to Playable Level

```text
Blockout
→ Scene Graph
→ Object Placement
→ Regions/Paths
→ NavMesh
→ Lighting
→ Gameplay Triggers
→ Build
→ AI Navigation Test
```

## 8.5 AI LookDev

```text
Scene Snapshot
→ Beauty/Depth/Normal/Albedo/Object ID
→ AI Variants
→ Compare
→ Human Approval
→ Editable Parameter/PBR Writeback
→ Deterministic Validation Render
```

## 8.6 Issue to Verified Fix

```text
Playtest Issue
→ Scene/Object/Code Backpin
→ Spatial Context
→ ChangeSet
→ Approval
→ Execute
→ Build
→ Same Test
→ Before/After
→ Merge/Rollback
```

---

# 9. 主 Hero Flow

用《记得回家》完成一条贯穿全系统的主流程：

## 新增“寻找钥匙并打开回家入口”支线

1. 用户在首页对话输入需求；
2. `design-room` 生成并允许编辑 Feature Spec；
3. `production-planner` 拆出概念、模型、材质、碰撞、场景、逻辑、音效、测试任务；
4. `concept-lab` 生成或导入钥匙概念并批准一版；
5. `asset-factory` 创建 AssetSpec，生成/导入钥匙模型；
6. Blender执行清理、UV/PBR、LOD、Collider、转台预览与质量检查中的至少一个真实流程；
7. 发布正式 AssetVersion；
8. `engine-unity` 导入并生成Prefab，保持Stable ID；
9. `world-composer` 将钥匙放入场景并关联3D标记；
10. `logic-studio` 创建拾取、背包、门锁和任务状态；
11. `audio-studio` 绑定拾取/开门音效；
12. `render-ops` 检查钥匙和入口可见性；
13. Unity生成Build A；
14. `ai-playtest` 执行“找到钥匙并回家”；
15. AI发现钥匙不易被发现或交互；
16. Issue回钉到钥匙、灯光、触发器或脚本；
17. 系统生成三个受控修复方案；
18. 人工批准一个ChangeSet；
19. Blender或Unity真实执行；
20. 生成Build B；
21. 使用同一任务和种子回归；
22. 展示视觉、语义、行为和门禁差异；
23. 合并并生成Release Candidate；
24. 对话总结整条数字线程并可一键打开任何证据。

不能硬编码结果数字。所有指标来自真实或明确标记的Cached运行。

---

# 10. 其他游戏 Demo

必须提供第二个端到端可运行游戏：

## Warehouse Escape

内容：

- 一个房间；
- 一个开关；
- 一扇门；
- 一个障碍箱；
- 一个出口；
- 一个简单玩家控制器；
- 一个简单胜利条件。

流程：

```text
需求
→ Feature与任务
→ 资产/场景
→ Unity构建
→ AI试玩
→ 发现Collider或NavMesh问题
→ Issue Backpin
→ 修改
→ 重构建
→ 回归通过
```

不得修改 SceneOps Forge 源码以适配第二游戏，只允许改变：

- Project Bible；
- 配置；
- 资产；
- 场景；
- 测试目标；
- Policy模板。

---

# 11. 外部工具与Adapter

至少实现以下真实或可切换Adapter：

## Blender

- health check
- scan scene
- assign/preserve sceneops_id
- inspect object
- render context passes
- safe transform/material/light operations
- geometry validation
- export GLB/FBX and manifest
- undo/rollback snapshot

## Unity

- health check
- scan project
- import asset
- map SceneOpsIdentity
- create/update Prefab
- set component property
- collider/NavMesh operation
- enter/exit play mode
- run tests
- capture game view
- read console
- profiler snapshot
- build player

## ComfyUI or compatible render service

- workflow upload/reference
- enqueue
- progress
- cancel
- retrieve outputs
- workflow hash
- model/seed/prompt provenance

## Git/LFS

- status
- branch
- commit reference
- diff
- artifact pointer
- rollback/restore proposal

## Artifact Store

- local filesystem in development
- S3/MinIO-compatible interface for deployment
- content-addressed checksum
- metadata and provenance

外部开源项目必须固定版本或Commit，记录许可证和边界。

---

# 12. 前端 Editor 类型

至少注册：

```text
assistant.conversation
project.intake
project.bible
project.feature-spec
project.production-plan
concept.moodboard
concept.review
asset.browser
asset.inspector
asset.factory
asset.validation
asset.material
character.editor
animation.timeline
scene.viewport.3d
scene.outliner
scene.inspector
scene.annotations
scene.world-graph
logic.feature
logic.state-graph
logic.code-diff
ui.flow
ui.preview
audio.library
audio.mixer
vfx.preview
render.viewer
render.aov
render.recipe
render.queue
pipeline.graph
version.diff
review.changeset
review.approval
build.matrix
build.console
build.profiler
playtest.game-view
playtest.agent-monitor
playtest.trajectory
playtest.steps
playtest.issues
release.center
system.integrations
system.worker-monitor
system.documentation
```

所有Editor通过 `EditorRegistry` 注册。所有工具打开动作通过 `WorkbenchCommandBus`。不得在Shell中用大型条件语句硬编码业务Editor。

---

# 13. 模块与Editor Manifest

每个 `module.yaml` 至少声明：

```yaml
id: world-composer
version: 0.1.0
title: World Composer
description: Scene and level production module.
status: active
feature_flag: world_composer
requires:
  modules: [core-kernel, module-runtime]
  integrations: [blender, unity]
contributes:
  editors:
    - scene.viewport.3d
    - scene.annotations
  commands:
    - scene.open
    - annotation.create
  events:
    - scene.snapshot.created
  jobs:
    - scene.scan
permissions:
  - scene:read
  - scene:write
```

构建时生成前后端模块目录并做：

- ID冲突检查；
- 依赖循环检查；
- 缺失Editor/Command检查；
- Feature Flag检查；
- 权限检查；
- API和事件Schema检查。

---

# 14. 技术默认值

若现有仓库无更成熟选择，采用：

## Frontend

- React + TypeScript + Vite
- dockview-react
- React Three Fiber + Drei
- TanStack Query
- Zustand（仅临时视口与选择状态）
- React Flow / xyflow（图谱类Editor）
- Zod（仅浏览器拥有的局部结构）
- Vitest + Testing Library + Playwright

## Backend

- Python 3.12+
- FastAPI + Pydantic v2
- SQLAlchemy 2 + Alembic
- SQLite开发 / PostgreSQL部署
- Redis用于队列、锁和事件扇出
- SSE作为基础运行事件通道；确有双向需求时使用WebSocket

## Local integrations

- Blender Add-on + 本地桥接
- Unity Package + 本地桥接
- ComfyUI HTTP API
- Git CLI / Git LFS
- 本地Artifact Store，可切换MinIO/S3

不要为了“企业级”引入不必要的微服务和基础设施。模块边界是代码边界，不要求每个模块独立部署。

---

# 15. 代码简洁规则

- 一个模块一个目录，职责清晰；
- 普通源文件尽量不超过400行；
- 普通函数尽量不超过50行；
- 只有两个以上真实调用方后才抽象；
- 不为未来可能需求建立通用框架；
- 不引入两套解决同一问题的依赖；
- 不在组件中直接调用外部工具；
- 不复制合同类型；
- 不创建巨型全局Store；
- 不保留旧实现与新实现并行；
- 注释解释“为什么”，不复述代码；
- 生成文件必须标明，不手工编辑；
- 对象身份、单位、坐标系和色彩空间必须明确。

---

# 16. Subagent与模型路由

读取 `MODEL_ROUTING.md` 和 `.codex/agents/`。

主代理必须：

- 先由 read-only explorer 映射仓库；
- 将写任务按模块目录划分，避免文件重叠；
- 并行优先用于探索、测试、审查、文档与互不依赖模块；
- 写入密集、合同密集和跨模块变更由主代理串联；
- 等待所有要求的Subagent结果后再合并；
- 对高风险变更安排独立Reviewer；
- 不把Subagent摘要当成测试证据。

模型路由：

- Astra：系统架构、跨Blender/Unity身份链、安全、状态机、最终集成审查；
- Sol：复杂模块实现、Docking/3D、渲染、玩法图谱；
- Terra：常规模块、API、组件、数据库、测试；
- Luna：探索、Fixtures、重复性UI、文档整理、低风险迁移；
- Spark若可用：极小、可回滚、即时迭代任务，不用于架构。

---

# 17. 开发顺序

不得把所有模块同时开工。按以下依赖顺序推进，但完成一个阶段后自动进入下一阶段：

## Phase 0 — Audit

- 仓库审计
- 状态与风险
- 依赖与许可证
- 模块地图

## Phase 1 — Core

- core-kernel
- module-runtime
- contracts/events
- database/migrations
- adapter interfaces
- module scaffold tooling

## Phase 2 — Chat-First Shell

- conversation-home
- forge-shell
- edge pull interactions
- EditorRegistry
- CommandBus
- WorkbenchContext
- layout persistence
- Judge Mode shell

## Phase 3 — Project and Planning

- project-intake
- design-room
- production-planner
- project/feature/task digital thread

## Phase 4 — Asset Vertical Slice

- concept-lab
- asset-library
- asset-factory
- Blender integration
- Stable ID export
- asset QA
- Unity import and Prefab

## Phase 5 — Scene and Logic

- world-composer
- logic-studio
- basic UI/audio/VFX paths
- playable scene

## Phase 6 — Render

- context AOV
- AI render variant
- approval
- editable writeback
- validation render

## Phase 7 — Build and Playtest

- Unity tests/build
- AI playtest
- telemetry
- issue backpin
- regression

## Phase 8 — Character and Advanced Content

- character-animation
- animation preview/retarget/check
- deeper UI/audio/VFX

## Phase 9 — Collaboration and Release

- version-collaboration
- approvals/activity
- build-release
- release candidate and rollback

## Phase 10 — Reuse and Delivery

- warehouse-escape
- WorkBuddy packaging
- Skills
- documentation
- Judge Mode
- offline/cached fallback
- final audit

每个Phase有明确Exit Gate。未通过不得宣布阶段完成。

---

# 18. 测试要求

至少包括：

## Core

- contract/schema tests
- module manifest tests
- dependency cycle tests
- event compatibility tests
- state-machine tests
- migration tests

## Frontend

- chat-only home
- edge drag hidden/peek/pinned
- tool open from chat
- split/move/tab/float/popout/maximize
- layout save/restore/migration
- context follow/pin
- editor disable when integration missing
- 3D resize and hidden render suspension
- Judge Mode reset

## Integrations

- adapter contract tests
- identity chain tests
- allowlist/security tests
- timeout/cancel/retry tests
- provenance tests

## Product flow

- Brief-to-Feature
- Feature-to-Tasks
- Asset-to-Unity
- Scene-to-Playable
- Render writeback
- Build
- Structured playtest
- Issue backpin
- Regression
- Release rollback

## E2E

- Remember Home Hero Flow
- Warehouse Escape other-game flow
- Mock full flow
- Cached judge flow
- at least one Live integration flow
- external tool offline recovery

不得通过删除测试、放宽断言或把Live变成Mock来制造绿灯。

---

# 19. 文档要求

持续维护：

```text
README.md
STATUS.md
EXECUTION_PLAN.md
AGENTS.md
product.md
design.md
architecture.md
MODULE_CONTRACT.md
FRONTEND_INTEGRATION.md
MODEL_ROUTING.md
SUBAGENT_ORCHESTRATION.md
DEFINITION_OF_DONE.md
docs/module-map.md
docs/frontend-map.md
docs/workbench-shell.md
docs/editor-registry.md
docs/workbench-context.md
docs/tool-window-development.md
docs/api.md
docs/events.md
docs/data-contracts.md
docs/integration-adapters.md
docs/blender-integration.md
docs/unity-integration.md
docs/render-pipeline.md
docs/playtest-bridge.md
docs/setup.md
docs/troubleshooting.md
docs/demo.md
docs/judge-mode.md
THIRD_PARTY_NOTICES.md
```

API、事件、Editor、模块清单、扩展点或配置发生变化时，文档必须在同一变更中更新。

---

# 20. WorkBuddy交付

生产工作台需要形成：

- WorkBuddy工作台实例；
- Skills与提示词；
- 专家/专家团配置；
- Blender、Unity等MCP或连接器入口；
- 一键装载预置工作流；
- 其他游戏Demo；
- 使用文档；
- 三分钟演示脚本；
- 五分钟路演结构；
- 两页以内沉淀说明草稿。

Skills至少包括：

- `brief-to-playable`
- `concept-to-engine-asset`
- `scene-to-playable-level`
- `ai-lookdev-review`
- `issue-to-verified-fix`
- `release-candidate`

---

# 21. 最终完成定义

只有全部满足才可宣布完成：

- 首页初始只有对话与四边拉起热区；
- 用户可从上下左右拉起、固定、关闭工具；
- 工具窗口可拆分、停靠、浮动、弹出并保存布局；
- 每项功能位于独立模块目录；
- 新模块可按文档添加，不需修改Shell核心；
- 主Hero Flow从一句需求运行到Release Candidate；
- 至少一个Blender修改是Live；
- 至少一个Unity导入/修改/构建是Live；
- 至少一个AI渲染结果写回可编辑工程数据；
- Stable ID贯穿Blender、GLB、Web、Unity、Telemetry和Issue；
- AI试玩产生结构化证据；
- Issue可回钉并完成相同测试回归；
- Warehouse Escape不改平台源码即可运行；
- 文件、语义、视觉和行为Diff可见；
- 失败、重试、取消、恢复和回滚可见；
- Live/Mock/Cached始终真实标记；
- 所有AI产物有来源；
- 文档和前端对接说明齐全；
- Judge Mode可一键加载与重置；
- 所有Release Blocker测试通过；
- 无硬编码、伪造或冒充Live的数据。

---

# 22. 启动命令

现在开始：

1. 完整审计仓库；
2. 使用 `code_explorer` Subagent映射现有代码与风险；
3. 使用 `forge_architect` 复核模块边界和核心合同；
4. 写入 `STATUS.md` 与 `EXECUTION_PLAN.md`；
5. 创建模块目录和清单校验器；
6. 先实现 `conversation-home + forge-shell + module-runtime` 的可运行纵向切片；
7. 继续推进后续Phase，不要在仅完成计划后停止；
8. 每个Phase结束时运行测试、更新状态、提交清晰摘要并继续。

最终回复必须列出：

- 已完成模块；
- Live/Mock/Cached清单；
- 关键文件；
- 测试结果；
- 演示步骤；
- 未解决风险；
- 需要用户进行的最小宿主机操作。
