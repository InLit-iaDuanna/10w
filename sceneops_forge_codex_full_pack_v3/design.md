# SceneOps Forge Design Specification

当前新制作主线（2026-09-09）：**SceneOps 对齐目标 → 确认可编辑制作简报与权限 → Codex／CodeBuddy 原生制作 → 工作台接回实际文件、资产和试玩候选 → 准确会话续改**。新工程使用轻量 Three.js / TypeScript / Vite / pnpm 起点。历史任务与编辑服务继续保留；本轮不接 App Server、SDK 或多 Agent 编排。接口、配置与故障处理见 [原生 CLI 制作](modules/ai-agent-runtime/docs/native-cli-production.md)，实际验收见 [验收报告](NATIVE_CLI_PRODUCTION_ACCEPTANCE.md)。

首次配置补充（2026-09-08）：初访显示可跳过的三步原生模态向导，沿用中性灰主题，选择工具、安装环境、登录与连接各占一步；与边缘工具教学顺序展示。关闭后恢复单主对话，右上角和 AI 设置保留入口。真实状态决定按钮可用性，安装存在与连接验证分别呈现，不以安装成功代替账号授权。

Version: 3.0
Direction: **Chat-First Pull-Out Spatial Workbench**  
Visual direction: **compact graphite workbench, readable conversation, blue interaction accent**

## 当前界面统一规范（2026-09-08）

当前主应用以 `apps/web/src/app/workbench.css` 的中性炭灰变量为唯一配色来源。
Core UI 聊天、模型菜单、AI 设置、制作卡片侧栏和策划工具消费同一套 canvas、surface、text、border 和 focus 变量，不再单独写入蓝灰底色或浅蓝选中色。
消息正文保持清晰的文字层级，输入框使用 20px 圆角；按钮和选择项使用灰阶悬停、边框与焦点反馈。红色错误、黄色警告、绿色成功等语义状态继续保留。
以下历史蓝紫视觉说明不覆盖此规范。工作流、设置保存和执行授权行为不变。

## Current V5 UI refresh (2026-09-05)

当前统一应用采用渐进式工具发布。四边拉起和区域标题的功能选择器只列出已经接通当前用户旅程的「模型与资产」「环境场景」；旧工作台继续注册以兼容历史布局，但不出现在当前目录，也不再由生产事件自动弹出。后续工具必须随用户旅程逐项加入，不能因为模块已注册就一次性展示。

Latest user revision supersedes global-drawer appearance/behavior below: the unified application
uses nested native grid regions. Pull within the current editor to split that editor only; both
regions can select and host a function. Legacy edge groups migrate without dropping tabs. Shared
surfaces now use the chat's neutral charcoal palette (#1b1b1b canvas, #222/#292929 surfaces), with
semantic errors/warnings retained. The tool library is a game-production node tree, not a tile wall.
See `NESTED_REGION_VERIFICATION.md`.

Current chat appearance supersedes the welcome/composer notes below: no marketing welcome or
suggestion cards; a neutral charcoal conversation canvas, compact thread title, flat assistant
messages, subtle user bubbles and one 20px-radius composer. Context is selected through the plus
menu; model and provider settings share the bottom toolbar with send/cancel. The plan editor stays
available in the thread options menu. Dockview's outer canvas uses overflow clip so focus cannot
scroll the whole workbench; actual editors retain their own scroll containers.

Latest interaction refinement: the tool picker starts immediately with its toolbar and choices,
not an introductory section. Only choices scroll; short drawers compact descriptions and open at
least 180px. Chat uses a compact growing input with Enter to submit, Shift+Enter for newline and
IME protection. See `UI_FUNCTIONAL_VERIFICATION.md`; this supersedes earlier picker-placement copy.

The user explicitly relaxed the earlier visual constraints while retaining interaction logic. This
section supersedes conflicting appearance rules below; older feature lists remain design targets,
not evidence that those capabilities have shipped.

- A 48px application bar keeps the local-project entry available without adding a sidebar.
- A compact welcome replaces the marketing-scale hero. Text input comes first; model, provider,
  selected context and send/cancel controls share one composer beneath it.
- Area headers are 36px: the title selects a function, quick actions use labelled icons, and the
  remaining existing actions live in the More menu. Dockview retains native tabs and edge geometry.
- Tool selection has search, Chinese production groups and short descriptions. It replaces its own
  area by default; other placements require an explicit choice in location options.
- The unified host does not show a global “布局” menu; users split the current area with its
  four edge pull handles.
- Root tokens and application chrome live in `apps/web/src/app/workbench.css`; picker styles live
  in the Forge Shell module's `tool-picker.css`; conversation/provider styles remain module-owned.
- Existing layouts, context binding, dirty prompts, data and AI request boundaries are unchanged.
- Visual smoke covers 1280×720 and 776×673, including a narrow split pane. See `UI_REFRESH_SMOKE.md`.

## V5 harness visual principles

V5 keeps the conversation-only first screen and four-edge workspace. Its visual language makes the
production harness legible without turning the home screen into a dashboard:

- graphite surfaces hold the work area; blue identifies selection and deliberate interaction;
- blue marks focus and spatial interaction; violet is reserved for AI/provider configuration;
- the compact conversation welcome describes the truthful sequence: goal, plan, then human approval;
- no counters, simulated progress, or execution claims appear before an actual pipeline result exists;
- provider configuration is compact by default. Advanced compatible-provider fields live in an explicit
  settings surface, and API keys are write-only UI values that are cleared after save.

At 1280×720 the composer remains fully usable, hero suggestions wrap, and edge controls retain their
hot zones. At 1920×1080 the conversation remains deliberately constrained to a readable central column.

---

## 1. Design intent

SceneOps Forge should feel like a serious 3D production environment that starts with the calm simplicity of a conversation.

The first impression is not “many functions.” It is:

> Tell the workbench what you are trying to make. Pull in the tools only when you need them.

The interface must be:

- professional rather than promotional;
- spatial rather than dashboard-led;
- flexible rather than page-bound;
- warm rather than cyberpunk;
- precise rather than noisy;
- inspectable rather than magical;
- efficient for experts while discoverable for first-time judges.

Do not visually clone Blender. Borrow its composable area/editor interaction model and build a distinct SceneOps identity.

---

## 2. The initial screen: only conversation

### 2.1 Required appearance

On a fresh launch, after project context is resolved, the entire screen contains:

- one full-canvas background;
- a centered conversation thread or focused welcome state;
- one composer;
- subtle pull handles on the four screen edges;
- optional tiny status indicators in corners;
- no permanent navigation sidebar;
- no permanent inspector;
- no permanent timeline or console;
- no dashboard cards;
- no module grid;
- no visible toolbar ribbon.

The default editor is:

```text
assistant.conversation
```

Suggested empty state:

```text
SceneOps Forge

今天要把什么做成可玩的版本？

[ 描述需求、导入项目或输入 / 打开工具… ]
```

Below the composer, show at most three low-emphasis suggestions:

```text
扫描一个现有Unity项目
从一句创意创建项目
继续上次的构建与测试
```

These suggestions are commands, not decorative cards.

### 2.2 Minimal chrome

Allowed on the initial screen:

- top-left: project name or “未选择项目,” under 160px width;
- top-right: one integration-health dot and user menu;
- bottom-left: execution mode label when not live;
- bottom-right: keyboard help hint;
- four edge handles.

Everything else must be summoned.

### 2.3 Conversation behavior

The conversation editor supports:

- streaming messages;
- file/project drops;
- structured action cards;
- approval cards;
- run progress cards;
- artifact previews;
- “open in tool” actions;
- compact context chips for project, scene, object, feature, build, or issue;
- slash commands and command search;
- undo of layout-affecting assistant actions.

Assistant actions must be typed. A natural-language response may explain the action, but execution uses the same command system as buttons and menus.

Example action card:

```text
打开工具
3D Scene View
位置：右侧拆分
上下文：HomeHallway / Door_01

[预览布局] [打开] [取消]
```

The assistant may never silently rearrange a customized workspace.

---

## 3. Four-edge pull interaction

### 3.1 Edge anatomy

Each screen edge has:

- 8–12px pointer hot zone;
- 2px visual reveal line on hover;
- a compact handle that appears after 120ms;
- a text/icon hint in Judge Mode;
- touch-independent keyboard and menu alternatives.

### 3.2 States

```text
hidden
peek
pinned
```

- `hidden`: only the hot zone exists.
- `peek`: drawer overlays the current workspace and auto-closes on Esc or explicit dismiss.
- `pinned`: drawer consumes layout space and remains open.

### 3.3 Drag thresholds

Recommended behavior, adjustable in tokens/config:

- pointer down in hot zone;
- 12px movement starts reveal;
- 80–180px creates Peek;
- beyond 220px shows Pin affordance;
- release in Pin zone makes it pinned;
- reverse drag below 48px hides it;
- double-click handle toggles last open size;
- Shift-drag opens directly pinned;
- Alt-drag opens as floating group.

Do not rely on invisible corner tricks.

### 3.4 Default drawer contents

| Edge | Default tools |
|---|---|
| Left | Tool Library, Project/Scene Tree, Asset Browser |
| Right | Inspector, AI Context, ChangeSet, Approval |
| Top | Project switcher, Command Search, Workflow Launcher, Agent Status |
| Bottom | Timeline, Pipeline Runs, Logs, Build Queue, Render Queue, Playtest Steps |

Drawers can host tabs and can accept dragged editors.

---

## 4. Workspace, Area, Editor, Region

Use these terms consistently.

### Workspace

A saved arrangement of areas, editors, drawers, pinned contexts, and floating groups.

### Area

A resizable rectangular region managed by Dockview.

### Editor

A tool type hosted by an Area.

### Region

A local subdrawer inside an Editor, such as 3D tools or local properties.

### Floating Group

A draggable window containing one or more editor tabs.

### Popout Window

A group moved into another browser window or monitor.

Structure:

```text
Workspace
├─ EdgeDrawers
├─ AreaGroup
│  ├─ EditorTab
│  └─ EditorTab
├─ FloatingGroup
└─ PopoutGroup
```

---

## 5. Docking interactions

Users must be able to:

- resize every Area;
- split left, right, above, or below;
- move tabs between groups;
- merge compatible adjacent groups;
- replace the current editor type;
- open as a tab;
- open floating;
- open popout;
- maximize and restore the active Area;
- close and reopen tools;
- move a docked editor to an edge drawer;
- move a drawer editor into the dock canvas;
- save, duplicate, rename, share, import, export, and reset layouts.

Visible drop zones must show:

- target area;
- split direction;
- resulting layout preview;
- whether the action replaces, tabs, or splits.

Use Dockview as the single docking engine. Do not nest another docking library.

---

## 6. Tool opening

A tool can open from:

1. assistant action;
2. edge Tool Library;
3. Area header `+`;
4. command search;
5. Window menu;
6. keyboard shortcut;
7. artifact or issue “open in tool” action;
8. workflow step output.

Placement choices:

```text
Replace current editor
Add as tab
Split left
Split right
Split above
Split below
Open floating
Open popout
Open in saved workspace
```

When an assistant opens a tool, show a preview if the action materially changes the layout.

---

## 7. Area header

Every Area header includes:

```text
[Editor icon ▾] [Title] [Context summary] [Mode]
[Follow/Pin] [Add] [Split] [Float] [Maximize] [More] [Close]
```

Example:

```text
[Cube ▾] 3D Viewport  HomeHallway · Door_01  LIVE
[Follow] [+] [Split] [Float] [Max] […] [×]
```

Rules:

- height: 36px;
- compact, no large rounded cards;
- active Area uses a subtle blue underline, not a glowing border;
- AI-controlled or AI-proposed state uses a small violet indicator;
- status includes icon and text where space allows;
- controls collapse into the More menu at small widths;
- title can appear top or bottom where the editor benefits from it.

---

## 8. Shared and pinned context

All editors can follow global context or pin local context.

Global context includes:

- project;
- branch;
- scene;
- selected object IDs;
- selected asset IDs;
- feature;
- task;
- ChangeSet;
- render job;
- build;
- playtest;
- issue;
- camera pose;
- timeline time.

A pinned editor shows a lock icon and a compact context badge.

Example use:

- left Render Viewer pinned to Build A;
- right Render Viewer pinned to Build B;
- 3D Viewport follows the selected Issue;
- Inspector pinned to Door_01 while the global selection changes.

Editors communicate through typed context, commands, and events. They do not import or call each other directly.

---

## 9. Workspace presets

The initial `Home` workspace is chat-only.

Additional presets load only when requested:

| Workspace | Default arrangement |
|---|---|
| Home | Conversation only |
| Design | Conversation + Feature Spec + Task Graph |
| Assets | Asset Browser + 3D Preview + Inspector + QA |
| Character | Character View + Rig/Animation + Inspector + Timeline |
| World | Scene Tree + 3D Viewport + Inspector + Navigation/Issues |
| Logic | Feature Tree + State Graph + Code Diff + Test Console |
| Render | AOV + Render Viewer + Recipe + Queue |
| Build | Build Matrix + Console + Profiler + Gates |
| Playtest | Game View + Agent Monitor + Trajectory + Issues |
| Review | Before/After + ChangeSet + Approval + Comments |
| Judge | Locked hero-demo arrangement with one-click reset |

Changing Workspace changes tool arrangement, not the underlying project or route.

---

## 10. Editor catalog

### Assistant and project

- Conversation
- Project Intake
- Project Bible
- GDD / Feature Spec
- Production Plan
- Task Board

### Concept and assets

- Moodboard
- Concept Review
- Asset Browser
- Asset Inspector
- Asset Factory
- Material Editor
- Asset QA
- Provenance Viewer

### Character and animation

- Character Editor
- Rig Inspector
- Skin QA
- Animation Timeline
- Retarget Preview
- Animator Graph

### World and scene

- 3D Viewport
- Scene Outliner
- Object Inspector
- Annotation List
- World Graph
- Path/Region Editor
- NavMesh View
- Lighting View

### Logic and content

- Feature Editor
- Gameplay State Graph
- Interaction Graph
- Code Diff
- Test Case Editor
- Dialogue/Quest Graph
- UI Flow
- UI Preview
- Audio Library
- Audio Mixer
- VFX Preview
- Shader Parameters

### Render and engine

- Render Viewer
- AOV Viewer
- Render Recipe
- Render Queue
- Comfy Workflow Viewer
- Unity Inspector
- Prefab Inspector
- Build Matrix
- Build Console
- Profiler

### Test, review, release

- Game View
- Agent Monitor
- Trajectory
- Step Log
- Issue Browser
- Version Diff
- ChangeSet
- Approval
- Activity
- Release Center

### System

- Integration Health
- Worker Monitor
- Documentation
- Settings

---

## 11. 3D viewport

The 3D Viewport is a professional editor, not a card.

Required behavior:

- ResizeObserver updates renderer and camera;
- hidden tabs suspend render loops;
- assets share caches across viewports;
- no more than two continuous live WebGL viewports by default;
- synchronized camera option for comparisons;
- object selection updates global context;
- issue opening restores camera pose and selects the target;
- drag assets from Asset Browser into the scene;
- point, surface, region, path, relation, state, sketch, and voice annotations;
- visual overlays for object IDs, collider, NavMesh, depth, normals, masks, paths, and heatmaps;
- fixed-camera capture for visual diff;
- explicit axis and unit display.

3D annotation colors:

| Type | Color |
|---|---|
| Selection / spatial structure | cyan |
| Human intent / approved target | amber |
| AI proposal | violet |
| Validated | green |
| Warning / approval | yellow |
| Blocking issue | red |

---

## 12. Conversation editor visual hierarchy

Conversation messages use a clean document flow, not oversized speech bubbles.

- user messages: subtle elevated surface;
- assistant prose: mostly flat on canvas;
- code/logs: mono blocks;
- commands: compact action rows;
- approvals: amber/yellow framed panels;
- failures: red icon + explicit next action;
- live progress: node list with state, not fake typing animation;
- artifacts: thumbnails with provenance and “open in tool.”

The composer supports:

- multiline text;
- `@` context attachment;
- `/` commands;
- file/project drop;
- mode selector only when needed;
- send/cancel;
- current project/scene chips;
- clear Live/Mock/Cached indication.

---

## 13. Visual language

### 13.1 Color tokens

```css
:root {
  --canvas: #101318;
  --surface-1: #191e25;
  --surface-2: #222932;
  --surface-3: #2a333e;
  --surface-hover: #2c3744;

  --text-primary: #eef2f6;
  --text-secondary: #a8b3c2;
  --text-muted: #7d899a;

  --accent-blue: #8aafff;
  --accent-violet: #b5a4ed;
  --home-amber: var(--accent-blue); /* legacy selection token */
  --spatial-cyan: #7fc8cf;
  --ai-violet: var(--accent-violet);
  --success: #84cda9;
  --warning: #e2bc76;
  --critical: #f398a5;
  --info: var(--accent-blue);

  --border-subtle: #2a323d;
  --border-default: #394554;
  --border-strong: #526174;
  --focus-ring: #8aafff;
  --overlay: rgb(6 10 17 / 70%);
}
```

Semantic rules:

- blue = selection, focus and deliberate interaction; legacy `home-amber` aliases blue;
- cyan = spatial or structural information;
- violet = AI interpretation or proposed result;
- green = validated;
- yellow = warning or waiting approval;
- red = failed, blocked, destructive, or critical issue;
- gray = inactive, unavailable, rolled back.

Do not use amber as decoration everywhere.

### 13.2 Typography

```css
font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
```

No external font download is required.

| Use | Size | Line height | Weight |
|---|---:|---:|---:|
| Empty-state display | 30px | 40px | 650 |
| Editor heading | 15px | 22px | 600 |
| Body | 14px | 21px | 400 |
| Metadata | 12px | 18px | 400 |
| Logs/IDs | 12px | 18px | 450 mono |

### 13.3 Shape

- editor areas meet edge-to-edge;
- border radius: 0–6px inside workspaces;
- floating groups: 8px;
- action cards: 8–10px;
- no nested card-on-card visual maze;
- 1px dividers carry hierarchy;
- shadows only for overlays/floating groups.

---

## 14. Motion

- ordinary transitions: 120–180ms;
- drawers: 160–220ms;
- layout preview: immediate with minimal easing;
- AI indicator: subtle pulse, no large glow;
- status changes: small crossfade or icon transition;
- respect reduced motion;
- never animate large 3D content merely for decoration;
- no delayed artificial progress.

---

## 15. Status communication

Never use color alone.

| State | Shape / icon |
|---|---|
| Running | rotating arc |
| AI processing | violet star/pulse dot |
| Waiting approval | yellow diamond |
| Passed | green check circle |
| Blocked | red octagon / alert |
| Rolled back | gray reverse arrow |
| Cached | clock/archive icon + label |
| Mock | flask icon + label |
| Live | linked-dot icon + label |

---

## 16. Judge Mode

Judge Mode must:

- load in one action;
- restore a known layout;
- make edge handles discoverable;
- preload required tool bundles;
- lock critical editors against accidental closure;
- retain resize, tabs, and inspection;
- disable destructive shortcuts;
- clearly mark Live/Cached/Mock;
- provide one-click reset;
- offer a guided 60–90 second experience;
- avoid requiring API keys or environment setup;
- show cached results instantly while allowing at least one real step to run.

---

## 17. Accessibility and ergonomics

- keyboard alternative for every drag-only action;
- minimum pointer target 28px in expert mode, 36px in Judge Mode;
- focus ring visible on dark backgrounds;
- status text and icons accompany color;
- resizable text in conversation and docs;
- logs use selectable text;
- tooltips do not contain required information;
- shortcut editor and conflict warning;
- persistent undo for layout operations;
- warn before closing an editor with unsaved local state.

---

## 18. Performance rules

- lazy-load heavy editors;
- virtualize asset grids, logs, and long timelines;
- suspend hidden 3D and game views;
- debounce layout persistence;
- do not remount editors during resize;
- keep pointer movement out of global React state;
- use shared caches for GLB, textures, and thumbnails;
- avoid more than two active continuous WebGL contexts;
- use static thumbnails for inactive render variants;
- preserve editor state across tab movement.

---

## 19. Responsive behavior

Primary target: desktop, 1280×720 minimum; 1920×1080 recommended.

At narrow widths:

- keep conversation usable;
- default drawers to Peek;
- prevent layouts below editor minimum sizes;
- collapse Area header controls;
- offer saved compact layouts;
- mobile is view/review only, not full production editing.

---

## 20. Forbidden patterns

- dashboard first;
- permanent sidebar on the home state;
- permanent inspector on the home state;
- full-screen AI chat as the only way to operate tools;
- dozens of glowing cards;
- excessive gradients or glassmorphism;
- hidden corner-only split gestures;
- multiple docking libraries;
- hard-coded editor types in the shell;
- business logic inside layout components;
- mock results presented as live;
- AI actions that rearrange layout without permission;
- WebGL views rendering while invisible;
- enormous global stores;
- table inside card inside card.

---

## 21. Design acceptance checklist

- [ ] Fresh launch shows only conversation plus subtle edge affordances.
- [ ] All four edges can be dragged open.
- [ ] Edge drawers support hidden, peek, and pinned states.
- [ ] Tools can be opened from chat, Tool Library, menu, and shortcut.
- [ ] Tools can tab, split, float, pop out, maximize, and close.
- [ ] Layout can save, restore, import, export, and reset.
- [ ] Assistant layout changes require explicit confirmation.
- [ ] Every editor supports global or pinned context where relevant.
- [ ] 3D view resizes without remounting and suspends when hidden.
- [ ] Live/Mock/Cached status is visible.
- [ ] Judge Mode is discoverable and resettable.
- [ ] Visual style remains professional, warm, precise, and non-template-like.
# 拉出区域交互补充（2026-09-05）

区域是功能容器，不是只负责打开其他窗口的启动栏。四边拉出空区域时，直接在其中选择功能；选中后同一面板原位承载，保留尺寸和位置。标题栏提供「选择功能」，需要其他布局时才显式选择添加标签、拆分或浮动。响应式布局以面板宽度而非整页宽度判断，窄抽屉中的搜索和功能内容必须可读可操作。
# 任务授权交互增量（2026-09-05）

最新用户修订覆盖下文旧两模式页设计：一个 Agent 对话、一个输入框，用权限区分讨论/授权执行；工具工作台默认 Agent 输入与结果，手动配置收进高级区。提供方切换可选 Codex CLI。入口统一不代表全部生产能力已执行，详见 `CODEX_PROVIDER_HANDOFF.md`。

聊天维持纯问答；「Agent 任务」让用户描述目标、审阅一次授权卡，再自动配置专有工具会话和执行注册动作。技术配置默认隐藏，不要求填工程路径或端口。任务卡与生产节点树共享进度；真实错误、未知费用、授权到期、停止和恢复均明确展示。卡片完成状态只取服务端双端验收，不取模型自述。首版有界箱体闭环已实测，详见 `AGENT_LIVE_VERIFICATION.md`。
# 单人策划新入口（2026-09-06）

文件夹项目的唯一主对话按 idea、grill-me、大纲、技术路线、制作卡片显示阶段。阶段推进由明确按钮触发，不将普通讨论当作执行授权。文档和卡片编辑是结构化内容编辑，不新增聊天输入。继承中性灰、四边拉手和已有布局。原有项目不强制迁移；多人入口预留但不实现。见 `PLANNING_JOURNEY_STAGE1.md`。
# 最新用户修订：先保持单一简洁对话

不继续展开每步骤的独立功能页。策划只显示当前阶段和下一步，大纲/制作清单/版本成为可展开结果附件，不默认铺开表单。文件夹选择保留路径与精简目录浏览。此修订优先于下方阶段导航与复杂工作台目标。

## 主对话制作流程（2026-09-08）

新项目默认只显示对话与输入框。AI 根据讨论主动澄清关键问题，信息足够时给出制作摘要和“开始制作”；不要求方向表单、架构选择、大纲确认或制作卡片。历史项目资料仍可折叠查看。输入框的“执行权限”在项目中持久保存：执行前询问在制作/改动前确认，完全访问在用户开始制作或发送后续改动时使用原生 CLI 任务授权。模型回复不能设置权限。制作文字、工具活动和最终试玩链接留在同一对话。

## 2026-09-08：边缘柔性拉起

左、右、下边缘停留 650ms 后进入预览。鼠标处保持约 96px 的平直段，两侧用连续曲线贴回边缘；肩部宽度采用无明显回弹的阻尼跟随，避免整块矩形平移和过强果冻弹跳。拉出超过 24px 后，推回原边缘 10px 内即可取消，260ms 内柔和收回；再次离开并靠近边缘可重新拉起。点击才创建真实分区，Escape、右键和离开工作区仍可取消。减少动态效果偏好关闭弹性过渡。

### 项目入口更新（2026-09-08）

项目管理使用视口中央的模态窗口，不再占用工作区分栏。最近项目、新建项目和文件夹选择在同一窗口逐步切换；中性炭灰底、20px 圆角、轻量文件夹线条图标、紧凑最近项目行。关闭返回原工作区，项目切换保留既有未保存更改确认。

确认分区时，真实工具内容以当前鼠标位置的拉起曲线为遮罩，在 320ms 内沿边缘铺满目标区域；相邻栏同时按原生布局的新旧位置平移，文字保持原字号，不使用淡入淡出。确认时阻止重复提交；创建失败显示原错误，减少动态效果模式直接完成。动画直接作用于原生栏及其内容层，使用 Web Animations 驱动位置变换和曲线遮罩，不使用页面截图转场。

分隔线拖动仍由 Dockview 调整比例；松手时检测新压到最小尺寸的栏，并按正常关闭流程关闭其中所有标签。松手在工作区外同样生效；锁定栏或拒绝未保存提示会恢复拖动前布局。指针取消会恢复，普通比例调整不关闭区域。

## 导出页面

按需打开的「导出」页面左侧为设置、平台执行和历史产物，右侧为持续 Agent 对话；窄区域纵向排列。沿用中性炭灰变量，显示真实失败原因、继续操作和设备验证状态。源码修改进入现有开发对话，避免在打包页面隐式修改游戏。

确认采用连续交接：点击时原预览立即展开；原生布局及内容层就绪后沿用点击时的同一时钟与缓动曲线，在同一绘制帧接管当前进度，不停住等待、不从零重播。布局尺寸集中读取后再统一写入动画，不在各栏之间交替测量和写样式；位置未改变的旧栏不添加动画。

## 窗口标题统一（2026-09-08）

所有原生分区的顶部统一使用 38px 标签栏、相同内边距、字重、圆角标签与关闭按钮，不再仅对对话和场景窗口应用专用外观。内部工具操作栏仍保留各自的功能。


## 2026-09-09：原生 CLI 制作主线

新游戏制作采用「方向对齐 → 确认可编辑制作简报 → Codex/CodeBuddy 原生会话 → 工作台回流 → 准确会话续改」。权限独立选择 scoped/full；完整权限也需要确认简报。旧任务和领域编辑服务保留，新制作入口不再使用逐动作 JSON 规划器。

工作区级源码登记与任务级 MCP 桥连接真实源码、GLB 资产版本、场景实例和试玩候选；新工程采用所选架构的轻量起点。手动修改后的「更新作品」只执行物化和构建，不调用模型。详见 [原生制作说明](modules/ai-agent-runtime/docs/native-cli-production.md)。

## 消息内记忆交互（2026-09-09）

采用对话内折叠记录，不新增侧栏。依据、修订与学习变化复用经验组件与中性灰主题；正文 14px、摘要 13px、元信息 12px。编辑按需展开、失败保留草稿、撤销产生新修订；集中管理保留现有模态入口。详见 [交互及验证](docs/conversation-memory.md)。
