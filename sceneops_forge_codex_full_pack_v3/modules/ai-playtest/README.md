# AI Playtest

AI Playtest 为 Unity 或其他已接入的游戏运行时提供**有界、可复现、可追溯**的自动预筛与回归测试。它记录动作前后观察，将动作结果与证据绑定，将异常整理为可恢复的问题，回钉到场景对象、资源、组件、脚本、功能或验收条件，并在修复后用同一份测试配置复跑。

它不判断“是否好玩”，也不替代真人可用性、无障碍或偏好研究。

## 独立工作台

从应用根执行 `pnpm --dir apps/labs/ai-playtest install --ignore-workspace`，再执行 `pnpm --dir apps/labs/ai-playtest dev`，打开 `http://127.0.0.1:4319/`。公开懒加载接口 `loadAIPlaytestWorkbench` 提供场景快照、行为时间线、问题定位、模拟审阅和提案草稿。该入口不调用 runner；页面内容始终标记为 Mock，提案为 Planned。首次启动、手动路径与本轮验证记录见 `apps/labs/ai-playtest/README.md`。

2026-09-05 本轮只执行了独立入口启动/导入与一次问题选择联动烟测；原 hero 测试没有重跑。其他测试、构建及外部操作 not run / pending approval。以下套件命令保留供以后明确授权使用，不代表本轮已执行。

## 用户与能力

- QA：运行 smoke、goal-driven、explorer 或受控 destructive 测试。
- 设计师：检查目标进度、轨迹、反馈缺失和任务状态不一致。
- 工程师：查看运行时错误、导航/碰撞问题和带置信度的源码回钉。
- 制作人：比较同一测试配置在两个构建上的测量结果与问题差异。

## 公共编辑器

| 编辑器 | 用途 |
|---|---|
| `playtest.game-view` | 游戏画面、相机证据、构建与执行模式 |
| `playtest.agent-monitor` | 代理模式、目标、边界、当前动作和运行状态 |
| `playtest.trajectory` | 轨迹、目标对象、时间点和恢复上下文 |
| `playtest.step-log` | 每步观察、动作、结果、进度、故障信号和遥测状态 |
| `playtest.issue-browser` | 问题证据、回钉置信度、人工确认/拒绝和 ChangeSet 提案入口 |
| `playtest.regression` | 同 TestCase、replay、adapter、行为版本和测量 recipe 的前后构建比较 |

编辑器均采用懒加载贡献，并显式呈现 `loading`、`empty`、`ready`、`failed`、`offline`、`permission_denied` 和 `disabled` 状态。缺少 Unity 时仍可打开并运行确定性 mock；Live 操作会明确不可用。

## 公共命令和事件

命令：`playtest.run`、`playtest.cancel`、`playtest.issue.open-backpin`、`playtest.issue.review-backpin`、`playtest.changeset.propose`、`playtest.regression.compare`。审核人 ID 由认证后的 command/request context 注入，不能由客户端正文自报；只有已唯一解析并人工确认的回钉能进入 ChangeSet 提案。

事件：`playtest.run.started@1`、`playtest.step.recorded@1`、`playtest.issue.created@1`、`playtest.issue.backpin.resolved@1`、`playtest.regression.compared@1`。事件 JSON Schema 位于 `contracts/events/`，TestCase、source catalog 与 deterministic runtime fixture Schema 位于 `contracts/manifests/`；producer/transport 仍由尚未落地的 core module-runtime 接入。

## 数据所有权

本模块拥有 TestCase、PlaytestRun、Observation、PlaytestStep、EvidenceBundle、Issue、Backpin 与 RegressionComparison。`PlaytestRun` 是 Issue 的持久化真源；相同 run ID 与相同请求幂等返回，不同请求复用同一 ID 会拒绝。模块只保存其他域的稳定 ID，不拥有构建、Unity 对象、资源、功能、验收条件或 ChangeSet 实体。

## 集成与降级

- Live：需要实现 `PlaytestRunnerAdapter` 的 Unity/runtime adapter；当前规范工作树中尚未提供，因此为 **Blocked**。
- Cached：合同和 UI 状态已支持，但没有真实历史运行工件；命令可用性会拒绝无来源的 cached 请求，状态为 **Planned**。
- Mock：模块提供确定性 adapter 和 Find My Way Home / Warehouse Escape fixtures，状态为 **Implemented**。
- LLM/persona：可选；persona 目前是确定性启发式并始终显示限制标签。
- ChangeSet：只生成发送给 owning module 的 typed proposal；由于 core-kernel 尚未落地，跨模块实际派发为 **Planned**。
- 现场恢复：命令携带原 run/build/mode；Mock/Cached 证据明确要求宿主确认，实际工作区切换由组合层执行。
- Jobs/workflow：模块提供组合描述符和 workflow manifest；core job 状态机、持久化进度、重试与恢复注册为 **Blocked**，不会伪装为已运行。

适配和组合说明见 [docs/integration.md](docs/integration.md)，算法边界见 [docs/limitations.md](docs/limitations.md)。

## 示例

- `contracts/examples/find-my-way-home-key-door.test-case.json`：钥匙—门目标；修复前确定性 fixture 会在门交互上产生结构化证据和组件回钉。
- `contracts/examples/warehouse-escape.test-case.json`：开关—门—出口的可复用项目配置，平台源码无需变化。
- `contracts/examples/find-my-way-home-before.runtime.json` 与 `find-my-way-home-after.runtime.json`：同配置前后构建的 mock 遥测。
- `contracts/examples/source-catalog.v1.json`：与三个 Mock 构建版本绑定、可解析的源记录；它是 fixture 源快照，不冒充仓库内真实 Unity 源码。

## 本地测试

模块可独立安装并运行本地套件：

```bash
python3 -m pip install -e 'modules/ai-playtest/backend[test]'
npm install --prefix modules/ai-playtest/frontend
python3 -m unittest discover -s modules/ai-playtest/backend/tests -v
npm test --prefix modules/ai-playtest/frontend
npm run typecheck --prefix modules/ai-playtest/frontend
```

后端需要 Python 3.10+。Pydantic、FastAPI、测试依赖与前端直接依赖均已固定版本；FastAPI 只用于组合层路由。

## 已知限制

- 当前只有 deterministic mock 被实际执行；没有把 mock/cached 结果描述为 live。
- 缺少 engine-unity 的公共 runtime bridge，不能验证真实输入、截图捕获、性能采样或对象恢复。
- 缺少 apps/web、module-runtime 与 core job runtime，不能验证 Dockview 挂载、生成 client、持久化 job 恢复或浏览器 hero flow。
- 回钉置信度表示证据吻合程度，必须经过人工审核；被拒绝的回钉会保留而不会被覆盖。
- AI 只能进行预筛和回归辅助，不能声称代表乐趣、偏好、无障碍或真人体验。

统一应用现公开 `loadIntegratedWorkbench()`；空态、自有草稿、样例边界与验证限制见 [统一编辑器说明](docs/unified-workbench.md)。
