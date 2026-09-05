# SceneOps Forge Design Specification

Version: 2.0  
Direction: **Chat-First Pull-Out Spatial Workbench**  
Visual mix: **60% engineering editor + 25% warm homecoming identity + 15% precision blueprint clarity**

## V5 harness visual update

V5 keeps the conversation-only first screen and four-edge workspace. Its visual language makes the
production harness legible without turning the home screen into a dashboard:

- graphite surfaces hold the work area; amber identifies deliberate human intent and selected context;
- blue marks focus and spatial interaction; violet is reserved for AI/provider configuration;
- the conversation hero describes the truthful sequence: goal, production plan, then human approval;
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

- height: 30–34px;
- compact, no large rounded cards;
- active Area uses an amber underline, not a glowing border;
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
  --canvas: #0d0f11;
  --surface-1: #15181c;
  --surface-2: #1b1f24;
  --surface-3: #242930;
  --surface-hover: #2a3037;

  --text-primary: #f1ece3;
  --text-secondary: #a5adb6;
  --text-muted: #717a84;

  --home-amber: #eca85b;
  --spatial-cyan: #58c8c5;
  --ai-violet: #a58bfa;
  --success: #55c98b;
  --warning: #f2c14e;
  --critical: #f06d6d;
  --info: #67aaf9;

  --border-subtle: #252a30;
  --border-default: #2f363e;
  --border-strong: #414a55;
  --focus-ring: #76d9d6;
  --overlay: rgba(4, 6, 8, 0.68);
}
```

Semantic rules:

- amber = human intent, selected approved candidate, homecoming identity;
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
