# World Composer 编辑器行为

## 注册

所有编辑器由 `frontend/src/editors/definitions.ts` 静态声明并从模块公共入口导出。模块不接触 Dockview DOM，不在初始 Home workspace 自动打开工具。正式 shell 应把 loader 结果包装为生成的 `EditorDefinition` / React `EditorProps`。

3D 视口默认位于 center，最小 640×400，是 World workspace 的主专业编辑器；其他工具作为 left/right/bottom 支持区。所有编辑器支持 follow-global 或 pinned context。

## 可见状态

| 状态 | 显示行为 | 可用动作 |
|---|---|---|
| loading | “正在加载”，显示 scene/mode | 等待/取消由宿主 job 提供 |
| empty | 区分未选场景与空数据 | 打开场景 |
| ready | 显示 exact scene version 与执行模式 | 编辑器自身 typed commands |
| failed | 结构化失败文本 | `scene.editor.retry` |
| disconnected | 集成离线，不伪造结果 | `integration.open` |
| permission-denied | 明文提示权限不足 | 无绕过动作 |
| module-disabled | 显示 feature flag 已关闭 | 无执行动作 |
| stale | 显示绑定版本过期 | `scene.version.open` |
| suspended | 仅 3D 视口；hidden/inactive/zero-size | 重新可见后恢复一次 |

状态同时显示中文文本和 `live/cached/mock/planned/blocked` 标签，不能只靠颜色。

## 3D 生命周期

`ViewportLifecycleController` 接收 ResizeObserver 的 CSS 尺寸/device-pixel-ratio、tab visibility 和 active state。它只向 renderer port 发送尺寸和运行/暂停命令；WebGL renderer、AbortController 和资源句柄不进入序列化 editor state。组合根给所有实例注入同一个 `ContinuousViewportBudget`，默认只允许两个 continuous 视口；第三个降为 on-demand，预算释放后自动提升。

`SharedResourceCache` 由组合根显式实例化，共享同一 in-flight GLB/texture load，并在租约释放及显式 eviction 后 dispose；它不是 cached evidence。

## Selection 与比较

Outliner、Viewport 和 Inspector 共享 `SceneSelectionModel`，仅使用 `sceneops_id`。Pinned selection 不随 global 更新；恢复 snapshot 会验证所有 ID。`CameraComparisonSynchronizer` 向已注册的比较视口复制纯 camera pose，源视口不回写自身。

## Overlay

`SceneOverlayRegistry` 注册纯 typed payload；重复 ID 失败，resolution 顺序稳定，并按 context availability 返回 unavailable reason。真实 renderer 按 resolved payload 创建临时绘制资源，不能把资源对象放进 registry 或 Zustand。
