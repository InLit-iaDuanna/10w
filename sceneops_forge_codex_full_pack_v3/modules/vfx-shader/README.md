# VFX / Shader Studio

本模块把特效和着色器意图表示为可验证、可审批、可追溯的 Recipe，而不是让 AI 或前端直接修改 Unity 工程。它提供参数编辑器、确定性预览计划、质量档位与预算检查、游戏事件绑定，以及经 ChangeSet 审批后的 Unity 发布边界。

## 面向用户

- 技术美术：编辑材质和粒子参数，检查 overdraw 与粒子预算。
- 游戏设计：把高亮效果绑定到拾取钥匙、接近门口等稳定事件。
- 制作人与审核者：审批 ChangeSet，查看来源和发布结果。

## 公共能力

- 编辑器：`vfx.recipe`、`shader.parameters`、`vfx.preview`。
- 命令：`vfx.recipe.validate`、`vfx.preview.plan`、`vfx.recipe.publish`、`vfx.binding.set_enabled`。
- 事件：`vfx.recipe.validated@1`、`vfx.preview.planned@1`、`vfx.recipe.published@1`、`vfx.binding.changed@1`。
- 作业：确定性预览计划与经审批发布。
- 后端入口：Python 包 `vfx_shader`。
- 前端入口：`frontend/src/index.ts`，只公开模块贡献、编辑器和公共类型。

事件 JSON Schema 位于 `contracts/events/`，契约细节见 [集成文档](docs/integration.md)。

## 可用纵向路径

`Find My Way Home` fixture 为钥匙与门口提供低调的呼吸式琥珀轮廓。默认关闭；绑定 `gameplay.key.picked_up` 或 `gameplay.door.unlocked` 后可启用。它先生成 `mock` 预览计划，预算通过后形成提案；只有关联 ChangeSet 状态为 `approved`，Unity 适配器健康且具备能力时才能发布。关闭命令沿同一适配器边界执行。

`Warehouse Escape` fixture 复用同一模板，仅替换项目、场景对象、事件和颜色数据，不需要修改平台源码。

## 执行真实性

- `mock`：仓库内确定性预览及 Mock 适配器执行；所有 fixture 都显式标记。
- `planned`：尚未调用外部工具的预览或发布计划。
- `blocked`：模块关闭、权限不足、ChangeSet 未审批、Unity/Render 离线或能力缺失。
- `live`：只允许由实际外部适配器返回；本模块仓库没有 live fixture。
- `cached`：协议允许承接真实历史结果，但本模块不提供伪造缓存。

Render 是可选集成。Render 离线时仍能编辑和校验 Recipe；Unity 离线时发布被阻止，但 `blocks_core_build` 始终为 `false`，不会阻塞核心构建。

## 开发与测试

无需安装第三方依赖：

```bash
cd modules/vfx-shader/backend
python3 -m unittest discover -s tests -v
cd ../frontend
npm test
```

前端声明 React 为 peer dependency，由未来应用组合根提供。当前仓库没有根 runtime，因此前端贡献尚未在 ForgeShell 注册，真实 Unity/Render 适配器也尚未接入。

## 已知限制

- 不包含真实 GPU/WebGL 渲染器；预览是可重复的计划与 UI 信息。
- 当前以模块本地完整值对象落实根 ChangeSet 字段与 proposed → approved 生命周期；根 `core-kernel` 可用后应替换为其公共类型。
- SHA-256 值由上游制品存储提供；本模块不自行生成哈希。

## 原生材质与灯光编辑（2026-09-09）

`lookdev.material` 是工作台原生、可停靠、隐藏暂停的 GPU 编辑器。宿主传入稳定资产与场景实例目标；编辑器从项目 API 读取原始 GLB 与版本化材质工程，提供 PBR、程序化效果、Shader 参数、灯光、撤销重做、已保存版本对比、工程保存与 PNG / GLB / 工程 ZIP / Shader ZIP 导出。旧 VFX mock 预览与 Unity 审批发布路径独立保留。

公共组合接口是 `LookdevMaterialEditorProps`：`EditorHostProps<LookdevEditorState>` 加 `onDirtyChange`、`onConversationTargetChange`、`onOpenConversation` 和 `onApplied`。主对话收到 `LookdevConversationSession` 后调用 `submit(text, signal)`；请求固定当前材质选择、工程版本和灯光授权范围，返回操作需通过范围校验与 GPU 编译才提交本地历史。编辑器不包含聊天窗口或模型配置。

`LookdevEditorState` 使用 `assetId`、`assetVersion`、`sceneInstanceId`、`sceneVersion`、`sceneopsId` 和 `materialSlot`。应用到游戏会先保存文档，通过版本检查创建资产版本并返回 `needs_build`；宿主刷新资产与实例，再通过现有更新作品路径构建。保存失败、模型读取失败和 GPU 错误均显示并保留当前草稿。

定向烟测：`node scripts/frontend-test.mjs modules/vfx-shader/frontend/tests/lookdev-history.test.ts`，覆盖身份保持、撤销重做与越界 AI 操作拒绝。本文前述“不包含 GPU”限制仅适用于旧 VFX 配方预览，原生 Lookdev 已提供实际浏览器 GPU 渲染。

工程文档的 `history` 现在保存 `lookdev.history@1` 的 past/future 快照；重新打开后继续撤销与重做，加载时验证每个快照的源资产绑定。项目内 `editLog` 仍保存操作说明。旧文档只有操作日志时不虚构撤销快照。

工具库直接打开材质编辑时会列出本项目已保存资产，并绑定所选资产当前版本；没有版本的上下文选择先查询目录，不猜测版本。场景实例缺少场景版本时通过 World Composer 公共客户端读取，应用仍执行版本冲突检查。

主对话材质请求在发送前生成 turn ID，服务端保存完整请求生命周期。`session.history(signal)` 返回持久记录；只有 GPU 校验通过后才 finish 为 applied。取消、失败、拒绝和无需修改分别记录；会话保存故障不会把已接受的 GPU 修改谎报为未应用。

完整本次交付与逐项实际验证见 [原生材质整合记录](docs/native-lookdev.md)。原生工程以持久源材质身份和独立当前材质身份区分局部覆盖，不依赖 GLB 材质数组顺序。导出菜单通过项目版本 API 登记制品；保存默认进入项目。
