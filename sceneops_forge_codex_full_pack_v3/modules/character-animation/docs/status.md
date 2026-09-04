# 实现状态

更新时间：2026-09-05（Asia/Shanghai 工作会话；合同时间戳仍使用 UTC）。

| 范围 | 状态 | 证据 |
|---|---|---|
| Pydantic/OpenAPI/JSON Schema | `mock` 可验证 | 后端合同测试与生成脚本 |
| 导入 Character/Rig/Skin/Clip 检查 | `mock` 可验证 | Remember Home fixture 与质量测试 |
| 六个 React 编辑器 | `mock` / `cached` / `blocked` 状态可渲染 | Vitest + Testing Library |
| Rig/Clip 比较、审批、回退引用 | `mock` 可验证 | 版本测试 |
| 固定相机预览与回归 | `mock` 可验证 | DeterministicMock adapter；无真实图像 |
| Unity Mapping proposal | `planned` | dry-run ChangeSet fixture |
| 自动绑定 | `blocked` | 无 adapter；导入路径不受影响 |
| 真实重定向/预览 | `blocked` | 无 vendor adapter |
| 真实 Unity 映射 | `blocked` | 无 engine-unity 和 Unity adapter |
| Cached replay | `planned` | 尚无先前真实执行 evidence |
| Live execution | `blocked` | 尚无任何外部工具 adapter |
| ForgeShell 目录注册与 Playwright E2E | `blocked` | core/runtime/shell 尚不存在 |

不得将表中的 `mock`、`planned` 或 `blocked` 行展示为 `live`。

## 验证记录

- 全局“只允许运行最小烟测”规则下达前：后端最近一次完整运行是 34/34 通过；前端是 5 个文件、11/11 通过；TypeScript 严格检查通过；npm 安装审计报告 0 vulnerabilities。
- 该规则下达后又补充了 PreviewArtifact 帧序列字段和预览输入证据前置检查，因此当前提交的完整后端/前端回归、TypeScript 全量检查和安全扫描均为 `not run — pending explicit approval`，不能沿用前述通过结论。
- 规则下达后的允许烟测：公开后端入口导入成功；Remember Home 检查结果 `passed`（模式 `mock`）；固定相机 Idle 预览生成 31 帧（模式 `mock`）。
