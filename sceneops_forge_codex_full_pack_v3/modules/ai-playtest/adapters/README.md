# Playtest Runner Adapter

`DeterministicPlaytestRunnerAdapter` 是模块自带的 **Mock** 实现，用于合同、代理决策、遥测恢复、证据、回钉和回归测试。它永远只报告 `mock`。

Live runtime 必须实现后端公共 `PlaytestRunnerAdapter` protocol，并满足：

- health/capability/dry-run；
- bounded reset / observation / available actions / execute action；
- game state、goal progress、camera/screenshot evidence；
- timeout、cancellation、telemetry recovery、measurement recipes 和 structured logs；
- stable build、scene、`sceneops_id` 与 source candidate；
- execution mode 和 adapter/tool provenance。

动作失败不会自动重试，因为重复交互可能产生副作用。动作后的观察会直接复用为下一步输入；遥测读取只可恢复到精确下一序号，恢复事实必须留在 step 或初始 terminal failure signals 中。`telemetry_sequence` 由 adapter 读取通道生成，fixture 作者不能预填。独立的 actions/game-state/goal getters 必须返回同一个 Observation 快照，否则运行以 execution-truth 错误失败。`capture_evidence(session, None)` 表示无动作的初始/终态检查点。运行时隔离与重置承担测试动作的补偿边界。

Adapter 必须为每个可测指标报告实现 ID、实现版本和参数；输出值只能来自当前 run 已执行动作与已访问观察。相同指标名但 recipe 不同的运行不可做 exact regression。

确定性 fixture 先通过 `DeterministicRuntimeFixture` Pydantic 模型整体校验，再由 adapter 使用。其版本化 JSON Schema 位于 `contracts/manifests/deterministic-runtime-fixture.v1.schema.json`。
