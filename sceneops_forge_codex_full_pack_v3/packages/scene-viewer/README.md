# @sceneops/scene-viewer

面向 World Composer 与真实 3D 渲染器的确定性场景核心。它负责稳定对象身份、选择、空间换算、相机状态、叠加层注册、视口生命周期和共享资源引用；不负责 WebGL 绘制，也不直接调用 Blender、Unity 或文件系统。

## 公共入口

生产代码只从 `@sceneops/scene-viewer` 导入。确定性演示数据从 `@sceneops/scene-viewer/fixtures` 导入。

| 能力 | 公共 API |
|---|---|
| 稳定身份 | `loadSceneObjectIndex`, `SceneObjectIndex` |
| 选择与上下文固定 | `SceneSelectionModel` |
| 坐标和法线 | `SceneTransformResolver`, `multiplyMatrix4`, `invertMatrix4`, `transformPoint`, `transformNormal` |
| 相机捕获/还原/比较 | `captureCameraState`, `restoreCameraState`, `CameraComparisonSynchronizer` |
| 叠加层 | `SceneOverlayRegistry` |
| 视口生命周期 | `ViewportLifecycleController`, `ContinuousViewportBudget` |
| 资源缓存 | `SharedResourceCache` |

## 不变量

- `sceneops_id` 是唯一主身份。名称和 `nodeKey` 仅用于显示或加载定位。
- 重命名保留 `sceneops_id`；复制必须由调用方提供全新的 `sceneops_id` 和 `nodeKey`。
- 源资产身份与场景实例身份分离；复制场景实例时保留 `assetId`，但更换实例 ID。
- 矩阵采用 glTF/WebGL 常见的列主序，列向量右乘；坐标为右手系、Y 轴向上，距离单位为米。
- 点使用完整齐次变换；方向不使用平移；法线使用逆转置矩阵并归一化，所以非均匀缩放可验证。
- 相机捕获显式记录场景与版本；还原到不同场景或版本会失败。
- 隐藏、非活动或零尺寸视口的渲染模式必为 `suspended`。
- 组合根共享默认上限为 2 的 `ContinuousViewportBudget`；超额可见视口自动降为 on-demand，并在预算释放后提升。
- 缓存实例由组合根显式创建与关闭；包不保存全局 WebGL 资源，也不序列化资源句柄。

## 渲染器接入

真实渲染器实现 `CameraStatePort` 与 `ViewportRuntimePort`，并将 DOM 的 `ResizeObserver`、标签可见性和活动状态转换为 `ViewportLifecycleController` 输入。渲染器根据 `SceneOverlayRegistry.resolve` 返回的纯数据负载自行创建绘制对象。所有 Blender/Unity 修改仍必须通过模块的 typed adapter 与 ChangeSet/审批路径，不能从本包执行。

```ts
import {
  SceneTransformResolver,
  ViewportLifecycleController,
  loadSceneObjectIndex,
} from '@sceneops/scene-viewer';

const index = loadSceneObjectIndex(sceneNodes);
const transforms = new SceneTransformResolver(index);
const worldPoint = transforms.localPointToWorld('sobj_home_door', [0, 1, 0]);

const lifecycle = new ViewportLifecycleController('world-main', rendererPort);
lifecycle.resize(960, 540, window.devicePixelRatio);
lifecycle.setVisibility(true, true);
```

## 执行真实性

| 模式 | 本包状态 |
|---|---|
| `live` | `planned`：真实 WebGL/Three/React 渲染器由消费方接入，本包不伪造 live 绘制。 |
| `mock` | 已实现：fixtures 和测试端口完全确定性。 |
| `cached` | 不作为运行结果提供。`SharedResourceCache` 只是进程内资源生命周期，不等同于真实运行回放。 |
| `blocked` | 无核心算法阻塞；真实渲染效果验证不属于该无渲染依赖包。 |

## 测试

```bash
npm test --prefix packages/scene-viewer
npm run typecheck --prefix packages/scene-viewer
```

`npm test` 仅需要 Node.js 22；类型检查需要安装 package 的开发依赖。测试覆盖成功与失败路径，包括 ID 加载、重命名/复制、选择 follow/pin、矩阵和法线、相机上下文保护、比较同步、叠加层、视口暂停以及资源引用/释放。

## 限制

- 本包不解析 GLB 二进制；加载器应把 glTF node/extras 转换为 `SceneNodeDescriptor`。
- 本包不持久化相机、选择或缓存；消费模块负责把可序列化快照写入其领域存储。
- 资源释放器是同步接口，适合 WebGL/Three 常见的同步 `dispose()`；异步外部存储不属于该缓存。

## 2026-09-05：公开 React 代理视图

新增 `@sceneops/scene-viewer/react` 子入口，导出 `ScenePreview` / props 类型。它使用 Three 0.183.2、React 19.2.8（仅该入口需要的可选 peer），从原 `SceneObjectIndex` 与 `SceneTransformResolver` 取得稳定 ID 和完整层级变换，绘制 box proxies、路径及可点击标签。相机旋转、缩放、对象 picking、选择高亮和相机快照可实际操作。

采用事件驱动按需绘制，无连续 animation loop；ResizeObserver 与 IntersectionObserver 响应可见性和尺寸，document hidden 不绘制。卸载释放 GPU geometry/material、controls、renderer 与 observer。

这是可运行的代理渲染宿主，不是 GLB 解码或真实游戏画面。旧入口 `.` 与 fixtures 的无 React 导入行为保持不变。独立入口与仅一次主路径 smoke 见 [工作台说明](../../apps/labs/world-logic/README.md)；原包完整测试没有在本轮重跑。
