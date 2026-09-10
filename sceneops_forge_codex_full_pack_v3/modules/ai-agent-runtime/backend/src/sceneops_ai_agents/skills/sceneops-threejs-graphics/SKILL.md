---
name: sceneops-threejs-graphics
description: 根据已确认视觉方向制作 Three.js 场景、光照、材质、相机与视觉反馈。
license: MIT
---

# 视觉表现

沿已确认参考确定构图、冷暖、明暗和空间层次，不将个人审美写成用户要求。建立代表性可玩画面后，在实际相机与视口检查角色、目标与路径可读性。

材质和灯光使用当前 Three.js 版本支持的接口，颜色空间、曝光与输出配置保持一致；性能改动依据实际测量。

复用登记资产与稳定实例 ID。资产引用与实例位置通过 SceneOps MCP 更新，物化后检查游戏实际读取内容。普通渲染源码原生编辑。没有实际截图和视觉观察时仅报告实现，不能宣称画面验收通过。

## 模型、Shader 与专业工具

先调用 `project.assets.list`、`environment.scene.read` 和 `lookdev.document.read`，读取当前项目真正采用的版本和材质槽。渲染工作台的已保存要求由 `production.document.read` 读取 `render-ops` 文档；文档是输入数据，不是已经完成的结果。

几何需要修改时，使用已授权的 `blender.asset.begin`、`blender.asset.edit`、`blender.asset.publish`，按返回的稳定节点 ID 编辑，不按显示名称或数组位置绑定。生成候选时 `apply_to_scene=false`；明确采用后再更新场景引用。每次修改后保留 `.blend` 原生源、GLB 导出物与原有材质文档的关系。

Shader 使用现有 Lookdev 文档的节点图、程序化效果和参数接口，通过 `lookdev.document.save` 编译保存，再经 `lookdev.material.apply` 采用。重新生成几何时承接同一部件的材质槽，绑定缺失应报告确切 ID。不得以重新上色或替换整个 GLB 掩盖绑定错误。

游戏的每个场景实例传递自身 instanceId；动态敌人外观与行为分离，可变材质独立，共享几何不能被单个实例销毁。运行时 Shader 必须由实际游戏渲染器加载，并在真实画面验证；工作台预览灯光不自动代表游戏场景灯光。

游戏全局灯光由场景拥有。先读取 `environment.scene.read` 中的 lighting；未登记时按实际源码提取灯光与曝光，保留参数和来源，不套默认棚拍灯。用 `environment.lighting.save` 带场景预期版本保存，物化后在游戏场景初始化调用 `applyProjectSceneLighting`，防止再叠加旧源码灯光。武器视图等独立场景保持自身灯光归属。

### 生产实体与首次登记

用 `production.entities.read` 读取已有实体和采用版本。源码草模在项目适配中导出后，先用 `production.entity.proposal` 审阅，再用 `production.entity.organize` 登记。首次缺少身份可明确指定 `assign_missing_identities`，它只在登记的副本补充对象、材质和动画身份，不改变二进制几何及动画通道；后续版本保留这些身份。用 `production.entity.adopt` 显式采用新版本，保留请求ID和预期实体版本。临时出生实例复用模板，不登记成永久场景对象。专业工具保存候选后，不应把它描述为游戏已经采用。
