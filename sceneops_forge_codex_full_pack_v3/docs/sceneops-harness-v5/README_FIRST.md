> 原始 V5 目标设计资料存档。文内提示词、强制测试与工具命令不构成本轮执行授权；实际范围见 HARNESS_MIGRATION_DECISIONS.md 和根 AGENTS.md §16.1。

# SceneOps AI Production Harness V5

这是一套用于把现有 SceneOps 原型升级成真正 AI Harness 的架构与实施计划。

## 文件

- `ARCHITECTURE.md`：最终系统架构。明确 AI Control Plane、Harness Kernel、本地 Blender/Unity 执行、证据治理与模块边界。
- `IMPLEMENTATION_PLAN.md`：从当前原型迁移到完整产品的分阶段计划、Subagent 分工、模型路由和验收门。
- `LOCAL_BLENDER_UNITY_TEST_PLAN.md`：本机 Blender、Unity、构建与真实 Player 的强制测试矩阵和命令模板。
- `OPEN_SOURCE_REFERENCE_MATRIX.md`：哪些开源项目直接用、借鉴、包在 Adapter 后，哪些核心必须自研。
- `CODEX_RETROFIT_PROMPT.md`：一次性发给 Codex 主代理的执行任务。
- `AGENTS_HARNESS_PATCH.md`：追加到仓库根 `AGENTS.md` 的强制工程规则。

## 使用顺序

1. 把本目录文件复制到现有仓库的 `docs/sceneops-harness-v5/`，并将 `AGENTS_HARNESS_PATCH.md` 合并进根 `AGENTS.md`。
2. 用现有原型建立 Git Tag：`prototype-shell-baseline`。
3. 在 Codex 中打开仓库，发送 `CODEX_RETROFIT_PROMPT.md`。
4. Codex 必须先运行原型测试和生产构建，再修改架构。
5. 所有外部能力都先通过本地 Capability Probe；Blender、Unity 未在本机真实通过时，只能标记 `Mock`、`Cached` 或 `Blocked`。
6. 先完成 `Asset to Engine` 和 `Issue to Verified Fix` 两条 Live Pipeline，再扩展全流程节点。

## 最重要的产品原则

```text
AI Control Plane 负责：理解、规划、调度、观察、诊断、恢复、沉淀。
Deterministic Plane 负责：Blender、Unity、构建、测试和文件操作。
Evidence Plane 负责：证明输入、过程、产物和结论都是真的。
```
