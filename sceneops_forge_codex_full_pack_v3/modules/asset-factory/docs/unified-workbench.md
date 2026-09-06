# 统一应用编辑器

公开入口 `loadIntegratedWorkbench()` 返回接受 `@sceneops/core-ui.IntegratedWorkbenchProps` 的懒加载 React 编辑器。宿主负责项目空态、文档读取/保存、手动样例导入、AI 模型和建议、停靠布局。

支持自有概念/资产规格、预算与来源草稿。显式导入 Mock 后，复用概念评审、生产与资产库操作面板；统一入口隐藏旧独立 AI 区，使用宿主 AI 提供方。

制作卡片的增量路径已由宿主通过公开 `CardAssetWorkflow` 组合：导入 GLB/FBX、确认结构化原语方案、Blender 新建、GLB 预览、FBX 导出和另存归一化版本均写入当前卡片 Git 工作树。每个产物明确标记为实际 Blender 输出，不把方案当产物。该路径不等于旧 AssetSpec 全流水线已经接通，也不自动发布进资产库、提交 Git 或合并分支。

默认空项目不选择或运行 Demo。草稿通过 `onSave` 保存到当前项目的模块文档，错误可见且保留输入；`onDirtyChange` 支持切换项目提醒。旧独立入口保持兼容。

## 验证边界

卡片路径已在隔离临时 Git 工程中完成一轮真实 Blender 烟测，并用 CodeBuddy `glm-5.3-flash` 完成一次结构化方案烟测。未运行游戏案例、生产构建、渲染、游测或完整测试套件；旧 AssetSpec 流水线和下游 Unity 采用仍按各自证据单独判断。
