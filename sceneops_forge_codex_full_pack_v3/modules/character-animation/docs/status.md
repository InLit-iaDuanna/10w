# 实现状态

更新时间：2026-09-05（Asia/Shanghai 工作会话；合同时间戳仍使用 UTC）。

## 独立工作台新增交付

`apps/labs/character-animation` 已增加独立 Web/API 启动；公开前端 `CharacterAnimationWorkbench` 复用六个编辑器和既有命令，后端直接注册原 contribution。页面支持动画元数据草稿、检查、版本比较、重定向配置、状态关系和待审批映射提案；外部适配器维持 offline。

本轮启动及 HTTP 源码入口检查成功；唯一主路径为通过 Web 代理检查原始角色（15 checks、passed、mock），再生成映射（planned、waiting_approval、dry_run=true）。完整测试、类型检查、构建、浏览器交互验证和所有外部执行均 not run / pending approval。最后表单禁用样式调整未重复烟测。详细命令和人工操作见 [`lab README`](../../../apps/labs/character-animation/README.md)。

以下表格和历史测试记录属于原模块实现，不表示本次 UI 组合已通过完整回归。当前工作树只引入共享启动骨架，未引入 Shell UI/core 实现。

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
