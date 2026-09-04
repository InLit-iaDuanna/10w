# Core Kernel

Core Kernel 提供跨模块最小执行内核：合法 Run 状态迁移与可审查 ChangeSet 的核心策略。它不拥有资产、场景、构建或测试等领域数据。

## 公共表面

- Command: `core.run.transition`
- Event: `core.run.state_changed@1`
- Job: `core.run.transition`
- Policy gate: `core.changeset.approval`
- Python: `core_kernel`
- TypeScript: `frontend/src/index.ts`

状态机允许：

```text
queued -> running -> waiting_approval -> running -> succeeded
queued/running/waiting_approval -> failed | cancelled
failed/succeeded -> rolled_back
```

非法迁移返回结构化 `INVALID_RUN_TRANSITION` 错误；fixture 与测试中的执行模式为 `mock`，不声明 Live/Cached。

## 测试

```bash
scripts/module-test core-kernel
```

## 限制

本模块不调度 worker，不持久化 Run，也不执行外部工具。
