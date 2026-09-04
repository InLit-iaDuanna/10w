# Runtime Fixture

Runtime Fixture 是最小注册样例，供模块运行时证明 Editor、Command、Event、Job、feature flag 与 optional integration 元数据都能进入静态目录。

## 用户与公共表面

面向平台开发者和测试人员，不面向最终游戏制作流程。

- Editor: `runtime.fixture`
- Command: `runtime.fixture.run`
- Event: `runtime.fixture.completed@1`
- Job: `runtime.fixture.execute`
- Python: `runtime_fixture`
- TypeScript: `frontend/src/index.ts`

## 数据与集成

本模块不持久化数据。`fixture-renderer` 是可选集成；缺失时模块仍可用，并在 runtime metadata 中显示降级状态。

## Fixture 状态

- `mock-success.json`: 确定性 `succeeded/mock`；
- `mock-failure.json`: 确定性 `failed/mock`，错误码为 `FIXTURE_REQUESTED_FAILURE`。

不会调用 Live 工具，也不产生 Cached 输出。

## 测试

```bash
scripts/module-test runtime-fixture
```

## 限制

Editor 贡献仅是注册描述，不包含业务 UI。
