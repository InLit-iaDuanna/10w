# Three.js 测试适配器 v1

新建的两种工程在 Vite `sceneops-test` 模式中公开 `window.__sceneopsTest`，普通开发和构建模式不发布该对象。用 `pnpm exec vite --mode sceneops-test --host 127.0.0.1` 启动测试预览，或在构建命令追加 Vite 的 `--mode sceneops-test`。旧工程不会被重新初始化覆盖。

对象包含 `version: 1`、`states()`、`setState(id)`、`pause()`、`resume()` 和 `diagnostics()`。唯一初始状态为 `start`。未知状态抛错且不修改当前游戏；重置回到原始出生位置、零分、全部收集物可见，清空按键与速度，清零模拟步数和累计时间并恢复运行。

诊断返回 `state_id`、`player: {x,y,z}`、数值 `score`、`collectibles: [{id,x,y,z,collected,visible}]`、`simulation: {paused,steps,elapsed_seconds}` 和 `randomness: {kind:'none',description:'fixed positions; no random source'}`。位置使用原游戏世界坐标（米，Y 向上），保留各模板原始出生高度。收集物 ID 为固定 `collectible-1` 到 `collectible-3`。诊断读取实际游戏对象／ECS 实体和分数，不读取预期断言。

暂停时原 RAF 继续绘制并更新上一帧时间，但不执行输入、移动或收集。恢复后不会补算暂停期间的墙钟时间。适配器没有直接推进或替代游戏逻辑的接口；执行器通过 Playwright Clock 驱动原 RAF，通过真实键盘事件进入原输入系统。对象／组件生命周期与 Miniplex 三个独立系统分别保留。

协议检查（Node 22.6+ 支持 TypeScript 类型擦除；不调用模型或浏览器）：

```bash
PYTHONPATH=modules/project-intake/backend/src python -m unittest discover -s modules/project-intake/backend/tests -p test_game_test_adapter.py
```

模板真实移动、收集、重置及暂停的浏览器验证由 AI playtest 执行器集成检查负责。
