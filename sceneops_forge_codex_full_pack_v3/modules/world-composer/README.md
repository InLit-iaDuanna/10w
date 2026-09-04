# World Composer

World Composer 是 SceneOps Forge 的关卡空间生产模块。它把稳定场景身份、空间标注、对象放置提案、世界图、路径/区域、导航、灯光目标、固定相机恢复和关卡门禁组织成一条可审查的数据链；编辑器本身不直接修改 Blender、Unity 或项目文件。

## 当前完成范围

- `sceneops_id` 加载、选择、重命名/复制语义，以及父子层级 local/world 换算；
- 非均匀缩放下的 inverse-transpose normal；
- 九种 Prompt 09 明列能力：object pin、surface pin、point、region volume、path trace、relation link、state、sketch、voice-to-draft；
- Asset drag/drop 到完整 `WorldMutationPlan`，再通过 `ChangeSetGateway` 提交到核心 ChangeSet；
- 可复现 graybox 和 procedural grid recipe；
- scene/object/camera/path/evidence/context 的 Issue 恢复；
- 固定相机捕获请求、相机比较同步和 overlay registry；
- object IDs、collider、NavMesh、paths、depth、normals、masks 和 heatmaps 八种 typed overlay；
- missing collider、overlapping spawn、unreachable target、NavMesh break、invalid scale、missing interaction relationship 六项门禁；
- Find My Way Home 与 Warehouse Escape 的确定性 mock 数据。

`packages/scene-viewer` 是本任务获授权实现的无渲染依赖公共基础层。真实 React/R3F/WebGL 宿主、GLB loader、module-runtime 和外部工具连接尚未存在，见“执行真实性”和“限制”。

## 用户

- 关卡设计师和世界设计师；
- 技术美术、灯光师与导航负责人；
- 需要精确空间上下文的 QA、AI playtest 和 Issue 审查者。

## 公共编辑器

| ID | 中文标题 | 默认位置 | 权限 |
|---|---|---|---|
| `scene.viewport.3d` | 3D 视口 | center，最小 640×400 | `scene:read` |
| `scene.outliner` | 场景大纲 | left | `scene:read` |
| `scene.object.inspector` | 对象检查器 | right | `scene:read` |
| `scene.annotations` | 空间标注 | bottom | `scene:annotate` |
| `scene.world.graph` | 世界图 | bottom | `scene:read` |
| `scene.path-region` | 路径与区域 | bottom | `scene:write` |
| `scene.navmesh` | 导航网格 | bottom | `scene:read` |
| `scene.lighting` | 灯光目标 | right | `scene:write` |

所有定义均为 lazy loader，支持 follow-global / pinned context，并声明 loading、empty、ready、failed/retry、disconnected、permission-denied、module-disabled 和 stale。3D 视口还声明 suspended；隐藏、未激活或零尺寸时，公共 viewer 生命周期会停止连续渲染。

## 公共命令与事件

命令：

- `scene.annotation.create`
- `scene.object.place.propose`
- `scene.issue.restore`
- `scene.capture.fixed.request`
- `scene.level.validate`
- `scene.world.update.propose`
- `scene.recipe.apply.propose`

事件 payload schemas：

- `scene.annotation.created@1`
- `scene.object.placement_proposed@1`
- `scene.level.validated@1`

事件目录只定义模块拥有的 payload；`event_id`、correlation/causation、actor、时间和执行模式 envelope 继续由缺失的 `core-contracts` 提供。

## 数据与合同边界

- `WorldLevelDocument` 是 World Composer 的门禁/编辑投影，不是核心 `SceneSnapshot` 的替代品。
- `WorldAnnotation` 是模块磁盘文档；未来网络类型必须从核心 Pydantic/OpenAPI 生成。
- `WorldMutationPlan` 是送入 `ChangeSetGateway` 的领域载荷，不复制核心 ChangeSet 状态机。
- Asset Browser 只提供 `assetId`/`assetVersionId` 与 drop context；本模块不复制资产仓库。
- 世界关系仅保存稳定 source/predicate/target，玩法实现属于 `logic-studio`。

详细不变量见 [public-contracts.md](docs/public-contracts.md)。

## 注解类型决策

`design.md` 的概括句列出八类，但 Prompt 09 逐项列出 object pin、surface pin、point、region、path、relation、state、sketch、voice-to-draft，共九项。本模块以更具体的任务提示为准，版本 1 使用九个 discriminant，并用九类 round-trip 测试固定该决定。free-world point 使用 scene reference，不伪造对象；object/surface/relation 使用 object reference。

Surface pin 同时保存 geometry version、triangle indices、barycentric、local/world position 和 local/world normal。拓扑版本变化返回 stale，不会静默吸附到最近表面。

## 对象放置与审批

拖放和键盘命令共享 `createAssetPlacementPlan`。调用方必须提供核心签发的新 `sceneops_id`；asset identity 与 scene instance identity 不得相同。输出包含 base version、前后值、目标工具/对象、理由、预期、影响、风险、验证、回滚、审批角色和 `dryRunRequired: true`。只有 `ChangeSetGateway` 返回的审批结果才能进入 typed adapter。

`DeterministicMockWorldMutationAdapter` 实现 health、capabilities、dry-run、取消、幂等重试、进度、结构化日志、验证、provenance 和 rollback；它始终标为 `mock`，不触碰外部数据。

## Fixtures

- `fixtures/remember-home/world.mock.json`：钥匙、Home Entrance、拾取区域、路径、灯光目标和稳定关系；
- `fixtures/remember-home/key-placement-input.mock.json`：Asset Browser 等价放置输入；
- `fixtures/warehouse-escape/world.mock.json`：switch、door、obstacle、exit 的复用场景；
- `fixtures/issues/navmesh-path-break.mock.json`：可重复的 Warehouse NavMesh 断边；
- `contracts/examples/object-pin.mock.json`：完整空间注解示例。

## 运行与测试

Node.js 22：

```bash
npm install --prefix modules/world-composer/frontend
npm test --prefix packages/scene-viewer
npm test --prefix modules/world-composer/frontend
npm run typecheck --prefix packages/scene-viewer
npm run typecheck --prefix modules/world-composer/frontend
```

模块测试涵盖 public manifest/API、九类注解、surface stale、空间换算、camera/Issue restore、follow/pin、放置 ChangeSet、安全 adapter、recipes、八编辑器状态、两套 demo 和六项 gate。

## 执行真实性

| 模式 | 当前状态 |
|---|---|
| Live | Planned/Blocked：没有 React/R3F host、artifact-store、Asset Browser、Blender/Unity typed adapter 或真实项目。 |
| Mock | 已实现：纯算法、viewer 端口、mock adapter 和两套项目 fixture 可重复运行。 |
| Cached | 未提供：仓库没有任何既往真实运行产物，进程内资源 cache 不等于 cached evidence。 |
| Planned | 固定相机 artifact、真实 asset drop source、外部 scene mutation 和视觉 E2E。 |
| Blocked | 正式 core types、module catalog/feature flag、生成 API client、shell/R3F、Blender/Unity、hero build/playtest。 |

## 降级行为

- Blender/Unity 离线：仍可浏览 mock/已加载的投影、创建注解与 ChangeSet 计划；实际写入显示 disconnected/blocked。
- Artifact store 离线：固定相机请求显示 disconnected，不生成伪 evidence。
- NavMesh/collider/scale policy/interaction snapshot 缺失或过期：相关 gate 返回 `blocked + reason`，不会猜测 pass。
- Voice adapter 缺失：只接受已有 transcript 的 `voice-draft`；不声称完成实时转写。

## 限制

- 当前 editor loaders 返回模块本地、框架无关的可见 screen model；正式 React `EditorProps` 绑定因 shell/core 类型缺失而 Blocked。
- `module.yaml` 可由本地合同测试核对，但正式 manifest schema、依赖图和 generated catalog 因 `module-runtime` 缺失而 Blocked。
- 没有实际 GLB 解码、WebGL 绘制、fixed-camera artifact、Unity/Blender mutation 或真实 Cached evidence。
- Hero fixture 只覆盖 key placement 与 Home Entrance 的 world 数据；pickup/inventory/lock/quest 属于 `logic-studio`。
- Warehouse fixture 验证同一算法和合同；真实 Unity build 与 E2E 留给后续集成任务。

精确集成缺口见 [integration-status.md](docs/integration-status.md)。

## 2026-09-05：独立 Web 整合更新

原 09 基线中“只有 headless / 无 React Host / 无 core ChangeSet”的限制现已在独立入口解决：从应用根执行 `pnpm --dir apps/labs/world-logic dev`。首次安装、手动动作、准确 smoke 记录见 [工作台 README](../../apps/labs/world-logic/README.md)。旧段落中的完整测试命令只供显式授权后使用，未在本轮执行。

新增公开 `loadWorldWorkbench()`、`loadWorldSession()` 与相应 props/session 类型；既有 headless API 保留。React UI 使用原 `buildWorldEditorScreen`、批注验证、稳定选择和世界变更计划；`scene-viewer/react` 提供按需绘制的 Three 几何代理。

新增公开 Python `world_composer.workbench_router`：`POST /api/world/proposals` 把原 `WorldMutationPlan` 映射至原样引入的核心 ChangeSet。场景 ID 与对象 ID 均进入 target；level-designer/project-owner 分别要求 scene:approve/project:approve。未知审批角色映射显式报错，不自动弱化审批要求。仅提案，不保存/审批/执行生产修改。

界面已支持对象选择、对象批注与视角恢复、场景关系编辑和 ChangeSet 展示。GLB 解码、真实 DCC/Unity 写回、正式 Shell 注册、其他八类批注界面的完整交互仍不在本次入口范围；原算法继续保留。完整测试与新增后端回归均 `not run / pending approval`。

统一应用现公开 `loadIntegratedWorkbench()`；空态、自有草稿、样例边界与验证限制见 [统一编辑器说明](docs/unified-workbench.md)。
