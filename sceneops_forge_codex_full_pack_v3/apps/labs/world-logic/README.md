# 工作台 05：场景与玩法

独立 React Web 已把 `world-composer`、`logic-studio`、`scene-viewer` 的既有领域实现接成可操作界面。默认 Web **http://127.0.0.1:4314**；本地 API **http://127.0.0.1:8314**。不需要启动其他工作台。

## 首次安装与启动

在应用根 `sceneops_forge_codex_full_pack_v3/` 执行：

```bash
python3 -m venv apps/labs/world-logic/.venv
apps/labs/world-logic/.venv/bin/python -m pip install -r apps/labs/world-logic/requirements.txt
pnpm --dir apps/labs/world-logic install
pnpm --dir apps/labs/world-logic dev
```

也可以在依赖已安装后使用共享入口 `pnpm lab world-logic`。Node 22.12+、pnpm 11.13.0、Python 3.9+。启动器优先使用本 lab `.venv/bin/python`，其次使用 `python3`；可显式指定 `WORLD_LOGIC_PYTHON`。本次宿主实际运行 Python 3.9.6 / FastAPI 0.128.8 / Pydantic 2.13.2 / Uvicorn 0.39.0。

端口占用即报错，不结束其他进程。显式改端口：

```bash
WORLD_LOGIC_WEB_PORT=4414 WORLD_LOGIC_API_PORT=8414 pnpm --dir apps/labs/world-logic dev
```

Web 和 API 都只监听 `127.0.0.1`。`Ctrl+C` 关闭本命令创建的子进程。OpenAPI 位于 API 的 `/openapi.json`；模块业务路径统一经 Web `/api` 代理。

## 手动体验

1. 点击场景树或三维对象标签，确认顶部 `sceneops_id`、对象检查器和关联玩法节点同步。左键拖动旋转、滚轮缩放，点击“重置视角”。
2. 在钥匙对象填写问题、意图、验收并添加批注；批注保存稳定 ID、局部/世界坐标、法线、视角、场景版本和当时的逻辑预览状态。点“定位 / 恢复视角”，或导出批注。
3. 编辑玩法节点名称、类型、对象绑定、出边目标/事件；可以添加状态、添加/删除边。节点条件/效果及完整图 JSON 支持编辑，再交由原确定性服务检查。
4. “对象关系”页编辑交互关系的来源、谓词和目标。世界与玩法关系属于各自领域草稿，按稳定对象 ID 连接，分别送审。
5. 填写变更理由，生成玩法 ChangeSet。审阅基础版本、修改前后、目标 ID、风险、审批权限、验证及回滚计划；可导出 JSON。没有 approve/apply 按钮或写回路由。
6. “开始本地预览”，按可用转移依次推进：Start → Quest active → Use target → Target is locked → Collect item → Pickup feedback → Use target → Target opens → Homecoming line → Home reached。查看背包、`target.is_open`、`quest.stage` 和事件。
7. 修改场景关系谓词（例如 `unlocks` 改为 `opens`），生成场景 ChangeSet。原 `WorldMutationPlan` 的 `level-designer` 与 `project-owner` 审批要求分别映射为 `scene:approve`、`project:approve`。
8. 可在 C# 页粘贴真实 unified diff，通过既有 `CodeChangeCoordinator` 生成 CodeChangeSet。不会执行代码、编译、测试或修改 Unity 文件。

刷新页面重置隔离草稿与批注。提案只存在当前浏览器响应状态中，需保留时使用导出；不声称已有数据库保存或正式审批。

## 真实性与依赖

| 能力 | 状态 |
|---|---|
| 场景、世界路径、钥匙/门绑定 | `mock`，确定性 fixture |
| WebGL 几何代理显示、空间换算、玩法解释器 | 当前浏览器/本地 API 实际执行；样例内容仍为 `mock` |
| 本地玩法验证 | `live`，复用原确定性 validator |
| 图/场景/C# ChangeSet | `planned` / `waiting_approval` |
| Unity、Blender、GLB 解码、生产写回 | `blocked`，没有外部适配器 |
| AI 生成 / AI playtest | 未接入、未执行 |
| Cached 真实运行结果 | 未提供 |

本工作台不需要 AI；若后续加入 AI 玩法建议/生成，遵循用户要求使用 **codebuddycli**，并在前端提供模型选择。当前没有伪装为可调用的 AI 或模型选项。

前端：React/ReactDOM 19.2.8、TypeScript 6.0.3、Vite 8.0.0，和 Shell 组版本一致。Three.js 0.183.2 用于 WebGL 几何代理；TanStack Query 5.90.21 管理 API 请求状态；openapi-fetch 0.15.0 是唯一网络客户端。具体依赖原因与许可证见 [DEPENDENCIES.md](DEPENDENCIES.md)。

## 公开边界与共享组合

- lab 只做 React/API/进程组合，业务 UI 与状态编辑继续位于各自 `modules/*`。
- lab 只导入模块 `frontend/src/index.ts`；浏览器重编辑器经公开 lazy loader 加载。保留旧 headless API；React 界面实际使用原 screen model 状态。
- `scene-viewer/react` 是新增公开子入口，复用原 `SceneObjectIndex` / `SceneTransformResolver`，使用按需绘制而非连续帧循环；隐藏页面或视口不绘制。
- 核心 ChangeSet 从原 01 的 `477e673` **原样引入 `packages/core-contracts`**，没有复制第二个 kernel，也没有改动其代码。
- 原 09 `9fc484c`、原 10 `0bb6b75` 已按提交整合。原 10 的原始对象绑定保留；新增 `modules/logic-studio/contracts/examples/world-workbench.binding.json` 对齐世界 fixture 的 ID。
- 共享骨架来自 Shell 组 `4f3416e`。本 lab 有自己的 `pnpm-workspace.yaml` / `pnpm-lock.yaml`，使 pnpm 11 的自动依赖安装留在 lab 内；**没有提交或修改根锁文件**。首次发现 pnpm 自动生成根锁文件后，仅清理本轮产生的未跟踪根锁文件。
- Shell 组合请求：整合时保留本 lab 的独立安装边界；正式全局目录/权限注册接入其公开 lazy loaders；无需根工具链修改。

## 类型再生成

生成器支持的 TypeScript peer 为 5.x，因此仅代码生成工具独立使用 TypeScript 5.9.3；前端仍为 6.0.3。生成器不是运行工作台的依赖。

```bash
npm install --prefix apps/labs/world-logic/scripts/codegen --workspaces=false --package-lock=false --no-audit --no-fund
pnpm --dir apps/labs/world-logic generate:api
```

源为组合 API 的 Pydantic/OpenAPI；输出 `modules/logic-studio/frontend/src/generated/workbench-api.ts`。禁止手改生成文件。组件通过注入的公共接口调用同一个 openapi-fetch 客户端，不直接 fetch。

## 本次验证

2026-09-05，仅执行启动/导入检查与 **一条最小本地主路径**：

- 启动 `pnpm --dir apps/labs/world-logic dev`：Vite Web 4314、Uvicorn API 8314 启动成功；组件、世界 fixture、玩法 fixture 及 OpenAPI 导入成功。
- 在 Codex 内置浏览器实际打开页面，三维代理、对象树、检查器与玩法图可见；浏览器 warning/error 日志为空。
- 同一主路径：钥匙上添加一条批注 → 将 `collectible_pickup` 标签改为“拾取黄铜钥匙” → 生成 ChangeSet `chg_ab5e5c710e3a4ab699800e720fe91062`，观察 `waiting_approval`、`logic:approve` 和前后图版本 1→2 → 开始本地预览，推进 `quest_active → target_interaction → locked_feedback → collectible_pickup`。
- 最终实际显示 `inventory.items=["asset_key_home_01"]`、`target.is_open=false`、`quest.stage="open_target"`；事件含 `target.locked_feedback_shown`、`collectible.collected`。到此停止测试，没有继续执行后半段结局路径。

**not run / pending approval**：完整单元、集成、E2E、安全、性能、类型检查、编译构建、Unity、Blender、渲染服务和 AI playtest 套件。新增后端成功/失败回归用例已维护但未运行。场景提案、C# 提案、其他编辑分支、导出/恢复、离线/错误分支和门打开后的结局路径由用户手动验证或另行授权；不能引用旧任务测试结果充当本次组合证据。

## Limitations

- 本次可交付的是独立功能工作台，不是正式 Shell 四边停靠/EditorRegistry 全局挂载。
- 三维场景是已有 fixture 的代理几何，不是 GLB loader 或 Unity 运行画面；本地门状态变化显示在逻辑预览中，不伪造真实门动画。
- 预览只解释规范化图；不验证 Unity 物理、导航、代码、渲染或实际游戏体验。
- 不接外部服务，所有生产修改停在待审批提案。审批来源与权限必须由正式控制平面提供，不能信任客户端自行授权。
