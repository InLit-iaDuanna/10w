# Character and Animation

统一 UI 功能回归修复：命令与类型显式导入 `zod/v4`，避免与其他模块 Zod 3 的 Vite 预打包名称冲突。11 项前端回归及统一空态动态导入通过；没有运行角色生产、预览或 Unity 操作。

独立工作台入口现位于 [`apps/labs/character-animation`](../../apps/labs/character-animation/README.md)，Web `127.0.0.1:4313`、API `127.0.0.1:8313`。包含六个编辑器、动画元数据草稿、本地检查、版本差异和待审批 Unity 映射提案。当前启动请使用该入口的 pnpm 安装说明；下方 npm 测试命令属于原模块独立开发说明，本轮未执行。

Character and Animation 为 SceneOps Forge 提供可检查的角色、Rig、Skin、动画片段、重定向、Animator 状态、预览证据与 Unity 映射流程。主路径接受导入资产；角色生成和自动绑定始终是可选能力。

## 解决的问题

- 以稳定 ID 连接源资产、角色、Rig、Skin、片段、预览、Unity Prefab 和场景对象；
- 对骨骼层级、缺骨、比例/坐标轴、蒙皮权重、片段时长、事件标记、Root Motion、Loop 接缝和潜在滑步提供结构化证据；
- 比较和审批 Rig/Clip 版本，并保留明确回退版本；
- 用固定相机生成可回归比较的预览；
- 通过 typed adapter 和获批 ChangeSet 提议/执行 Unity 映射；
- 在自动绑定、重定向、预览或 Unity 集成离线时继续检查导入数据。

主要用户是角色美术、动画师、技术美术、Unity 工程师和审核负责人。

## 公共编辑器

| ID | 用途 | 离线行为 |
|---|---|---|
| `character.editor` | 查看角色、来源、版本、Feature/Task 与 Unity 身份 | 可查看导入数据 |
| `character.rig-inspector` | 检查层级、坐标与版本差异 | 可查看导入 Rig |
| `character.skin-qa` | 查看蒙皮检查和证据 | 可运行本地确定性检查 |
| `animation.timeline` | 查看片段、事件、Root Motion 与检查结果 | 可查看导入 Clip |
| `animation.retarget-preview` | 检查映射并显示固定相机预览 | Profile 可检查，捕获显示 `blocked` |
| `animation.animator-graph` | 查看状态与转换引用 | 可查看已导入状态规格 |

所有编辑器都懒加载，接受 follow-global 或 pinned context，保存的只是小型可序列化本地状态。加载、空、失败、离线、权限、重试和成功状态由同一组件明确呈现。

## 公共命令与 API

命令：

- `character.inspect`
- `character.version.compare`
- `character.version.review`
- `animation.preview.capture`
- `animation.retarget.preview`
- `character.unity-mapping.propose`
- `character.unity-mapping.execute`

后端挂载路径为 `/api/modules/character-animation`。Pydantic 是网络合同源，生成的 OpenAPI 位于 `backend/openapi.json`，TypeScript 类型位于 `frontend/src/generated/api.ts`。详见 [docs/contracts.md](docs/contracts.md)。

## 拥有的数据

模块拥有角色规格、Rig/Skin/Clip 版本元数据、重定向 Profile、Animator 状态、质量报告、预览引用和 Unity 映射提议。源模型、纹理和二进制资产仍由 Asset Library / Artifact Store 拥有；本模块仅保存稳定 ID、版本和 provenance 引用。

## 集成与模式

- 无必需外部集成；导入检查始终可用。
- `artifact-store`、`blender`、`unity`、`automatic-rigging`、`retargeting` 均为可选。
- 默认后端使用离线适配器，因此外部预览、重定向和 Unity 写入返回结构化 `INTEGRATION_OFFLINE`，状态为 `blocked`。
- `DeterministicMockCharacterToolAdapter` 只供测试/演示 fixture 使用，结果明确为 `mock`。
- 当前没有 `live` 或 `cached` 适配器，也没有伪装成真实执行的结果。
- Unity 映射提议为 `planned`；只有核心审批把 ChangeSet 标为 `approved` 后，执行入口才会调用适配器。

适配器接入要求和故障排查见 [docs/integration.md](docs/integration.md)。
逐项实现状态见 [docs/status.md](docs/status.md)。

## 设置与生成

后端需要 Python 3.9+。从模块目录生成合同：

```bash
PYTHONPYCACHEPREFIX=/tmp/sceneops-character-pycache \
PYTHONPATH=backend/src \
python3 backend/scripts/export_contracts.py
```

前端需要 Node.js 22+：

```bash
cd frontend
npm install --ignore-scripts
npm run generate:api
```

## 测试

```bash
cd backend
PYTHONPYCACHEPREFIX=/tmp/sceneops-character-pycache \
PYTHONPATH=src \
python3 -m unittest discover -s tests -v

cd ../frontend
npm run check
npm audit --omit=dev
```

确定性示例是 `contracts/examples/remember-home-character.json`，场景步骤位于 `examples/remember-home/simple-character-path.json`。

## 已知限制

- 滑步检测只根据已标记脚掌接触样本位移给出启发式提示；它不构成人工质量批准。
- 固定相机帧差只提供回归信号，不判断表演、变形或美术质量。
- 未提供自动绑定实现，也不承诺“完美自动绑定”。生成源必须先由上游变成有 provenance 的可导入资产。
- 当前规格基线缺少 core-kernel、module-runtime、Asset Library、Design Room、Production Planner、ForgeShell 和 engine-unity 实现，因此目录级注册、真实 Artifact Store、真实 Unity 写入和 Playwright shell E2E 仍是 `planned`/`blocked`；模块本地合同、服务、fixture 与组件测试不依赖这些实现。

统一应用现公开 `loadIntegratedWorkbench()`；空态、自有草稿、样例边界与验证限制见 [统一编辑器说明](docs/unified-workbench.md)。


## 七领域项目联通（2026-09-10）

公开 AssetAnimationPreview，由 Shell 注入当前项目资产工作台；直接读取版本化 GLB 的真实动画片段进行预览，隐藏时暂停。预览不写入动画姿态或创建新的资产身份。
