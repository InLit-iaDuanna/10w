# Unity C# ChangeSet 流程

Logic Studio 不直接写 Unity 项目，也不执行模型生成的 C#。当数据驱动图不足时，
它只创建统一差异格式的 `CodeChangeProposal`，目标必须是相对项目根的
`Assets/**/*.cs` 路径。

```text
planned proposal
  -> waiting_approval ChangeSet
  -> explicit logic:code:approve
  -> adapter health + capability check
  -> mandatory dry-run
  -> allowlisted apply with rollback token
  -> Unity compile + Edit Mode + Play Mode tests
      -> succeeded
      -> failed -> automatic rollback -> rolled_back / failed
```

ChangeSet 保留基础版本、目标集成与对象、前值、提议差异、理由、预期结果、影响
范围、风险、验证计划、回滚计划和审批记录。未经批准调用适配器会在适配器接收
任何请求前失败。

适配器协议位于 `backend/src/logic_studio/unity_adapter.py`，包含健康、能力、超时、
最大尝试次数、取消、进度、dry-run、apply、compile/test 与 rollback。当前
`DeterministicMockUnityCodeChangeAdapter` 仅记录内存收据，绝不访问项目文件；
其结果始终标记为 `mock`。

Live 实现必须由 `engine-unity` 提供并执行项目根路径校验、命令白名单、结构化
日志、错误映射和真实快照回滚。当前基线没有该模块，因此 live apply/compile
为 `blocked`，而非模拟成 live。
