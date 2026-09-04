# AI Playtest 能力边界

AI Playtest 是机器可重复的预筛与回归工具，不是人类研究。

- 它可以发现配置定义的停滞、软锁、不可达目标、重复失败交互、导航/碰撞错误、反馈缺失、任务状态不一致、运行时错误和性能阈值越界。
- 它不能从自动轨迹推断乐趣、审美、可访问性、舒适度、情绪、偏好或代表性玩家体验。
- persona 模式只是带明确标签的动作选择启发式，不是某类人的模拟。
- 回钉结果只表示候选源与证据的匹配程度；`ambiguous`、`unresolved` 和人工 `rejected` 都是正常、可见状态。
- 回归结果只按 TestCase 中声明的指标方向与容差计算。未声明或缺失的指标不会被臆测为改善。
- Mock fixture 用于合同和确定性验证，不能作为真实 Unity、真实性能或真实玩家证据。

## 集成限制

- **Live / Blocked**：缺少 engine-unity 公共 playtest/telemetry bridge，未实际发送输入、捕获真实截图、读取真实性能或恢复 Unity 现场。
- **Cached / Planned**：合同与可用性 gate 已存在，但当前没有带可信 provenance 的历史真实运行工件。
- **Frontend composition / Blocked**：缺少 apps/web、module-runtime、Dockview、生成 OpenAPI client 与 TanStack Query 组合层。
- **Jobs / Blocked**：模块只提供 job/workflow 组合描述符；持久化状态机、进度、恢复与重试必须由尚未存在的 core job runtime 实现。
- **Event transport / Blocked**：版本化 event 类型和 Schema 已定义，但 producer、outbox 与消费者注册依赖 core module-runtime。
- **Cross-module ChangeSet / Planned**：模块只产出 typed proposal；CommandRegistry 派发、审批和 owning module 执行未在本工作树接通。
- **HTTP validation envelope / Planned**：模块显式处理的错误使用统一顶层 envelope；请求体 422 仍依赖组合根的全局 handler。
- **Artifact store enrichment / Planned**：本地 fixture artifact 已记录稳定身份和 provenance；生产 artifact-store 的内容校验与正式发布元数据需在集成层补齐。
