# Three.js 制作知识 S1

本轮接入三个随包适配稿与原 `AgentRuntime.next_action` 请求。原公共系统、主制作角色、单动作协议、授权筛选和 Provider purpose=`agent-action` 保留；源码模板、工具权限、供应商配置不变。完整游戏先实现代表性场景，局部修改保持范围。

## 装配与选择

资源位于 `backend/src/sceneops_ai_agents/skills/`，包含 Gameplay、Debug、QA、时间状态参考、来源及 MIT 许可。版本 `sceneops-s1.1`，上游提交 `e5f301d548bb18c530afbece78cd25082f4cda9c`。原内联 Gameplay 短指令被替换，正文每次请求只装入一次，不加入 history/observations。

`skill_context.py` 使用现有 goal、capabilities 与动作结果：

- 明确解释/讨论/比较请求保留咨询模式；非源码领域不装载这三份知识。
- 允许源码修改且未进入其他阶段时选择 Gameplay。
- 同一源码操作最新结果失败时加入 Debug，包括工具调用成功但内部 check/build 失败。后续同操作结果或最新状态快照覆盖旧结果，不搜索源码和日志中的指令文本。
- 明确检查请求、成功的检查/构建/预览后、或成功写入且有检查能力时选择 QA。知识不授予执行权限。
- 冲刺、冷却、暂停、重开等时间任务才附带 `references/time-and-state.md`。

请求前读取包资源；实际加载路径、适配版本、上游提交记录于原 CapabilityResult.logs，再由 Harness 保存。缺失资源以 `SKILL_RESOURCE_UNAVAILABLE` 写入日志及本轮指令，不记成功、不猜内容；无关代码路径仍可工作。用户游戏目录和全局同名 skill 不参与查找。

本轮复用工作区已有的历史兼容修正：无 history.read 时保留精确内联历史；历史失败单独标记；大而旧的 observation 以可回读引用代替，最新正文仍可用于准确写入。

## 验证方式

`test_skill_context.py` 从 AgentRuntime → Provider 请求捕获正文、purpose、阶段和实际加载日志，并通过 ProviderService → CLI transport 注入边界确认指令未被替换。所有模型响应都是 fixture，未运行真实模型或 CLI。

`test_prompt_context.py` 捕获完整请求的 history 与 observations，覆盖旧授权与当前正文、历史失败和领域工具授权。

`test_skill_packaging.py` 使用 pyproject 声明的 Hatchling 构建实际 wheel，在无关 cwd 的子进程中直接从 wheel 导入模块与资源，并再次捕获 Provider 请求；不依赖源目录相对路径。该测试需要构建后端及其依赖已在构建环境可用，不自行安装。当前机器使用既有 uv 缓存工具，未增加依赖。

通过 `scripts/python-workspace.mjs` 的 pythonEnvironment 加载本地包后运行对应 unittest 文件；两种现有工程回归分别为 `JourneySmoke.test_folder_to_v1_cards_and_reopen`（ECS/Miniplex）和 `JourneySmoke.test_manual_object_component_project_and_legacy_state_are_safe`。它们检查原工程/分支和架构保持，不能证明模型已完成冷却修改。

2026-09-07 当前工作区实测：19 项请求/上下文测试通过，1 项实际 wheel 加载测试通过，2 项既有架构回归与 4 项 Provider 路由测试通过。缺 reference 测试中的 warning 为预期故障注入。打包测试最初因构建环境缺 Hatchling 依赖无法启动；显式引用本机已缓存依赖后通过，没有安装或升级。

## Limitations

首版选择仅识别明确请求前缀和真实动作状态，不声称理解任意自然语言的阶段意图。泛化意图或复杂多文件修改可能仍需主 Agent 根据完整目标安排下一动作。

真实模型冷却修改及原版/适配版对照未执行：本地 `.local/sceneops.sqlite3` 中现有 card-development grant 已于 `2026-09-06T22:21:17.808738Z` 过期，没有可沿用的有效测试授权。本轮未创建/延长生产授权、未调用外部生成。

本轮不覆盖浏览器画面、真实输入、视觉质量或性能提升。S2–S6 留待后续任务。回退本轮提交即可恢复原指令装配；不会撤销已经制作的游戏成果。
