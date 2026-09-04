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
