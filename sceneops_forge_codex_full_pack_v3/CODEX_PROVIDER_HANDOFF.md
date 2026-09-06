# Codex 提供方与统一 Agent 入口

2026-09-05，用户要求增加 Codex CLI 切换，并把聊天/任务视为同一 Agent、工作台默认由 Agent 输入驱动。

## 追加：用户授权的完全权限与真实 low 烟测

权限菜单现为“仅讨论 / 受控工具（先授权）/ Codex 完全权限（先授权）”。完整权限仅经新的任务授权卡和 `accept_full_access=true` 启用，默认讨论、旧授权及 CodeBuddy 行为不变。需要当前提供方为 Codex CLI，不自动切换用户设置。

完整权限使用原生 `danger-full-access` 和 `approval_policy=never`，文件/Shell 可用，工作目录为自动创建的独立空工程；**工作目录不是 OS 沙箱，CLI 技术上能访问目录外**。卡片明确说明风险，服务端范围作为 developer 指令传入；禁止自行操作其他工程、安装系统软件、购买和发布。不自动加载全局 MCP、插件、hooks 和其他账户服务。

此模式走原 Harness：高风险任务级 ChangeSet、真实空目录前置记录、grant 派生审批、一次 CLI 调用、最多 20 分钟、取消停止进程组。内部多次模型调用无法精确计数，不宣称受原 8 次模型预算约束；费用和费用估算保持未知。无法逐个 CLI 内部文件变更进行类型化审批。CLI 结束标 `review_required`（待审阅），不假冒业务验收；未知写入不重放。

真实测试按用户指定 `gpt-5.6-sol`：本机 bundled catalog 中没有 `lite` 枚举，轻量档为 `low`，已明确传入。任务 `task_67c59f3e2f3e4959b6b07e993273faea` 只调用一次 CLI，实际文件修改事件创建 `smoke.txt`，命令事件读回，主代理再次读取文件确认内容为 `SceneOps Codex CLI OK` 加换行。任务目录：`.local/codex-agent-validation/agent-workspaces/prj_446a84ae86fb4cd8a0bf510e4057919e/`；任务与事件在同数据目录的 SQLite。输出 usage 为 input 23901、cached input 22144、output 230、reasoning output 31；这是 CLI 汇总，不等于一次底层模型请求，也不代表美元费用。

烟测脚本 `scripts/smoke-codex-agent.py` 只在明确授权后手动运行，不属于启动流程。没有新建游戏案例、安装依赖或启动 DCC。另通过完整 CLI 适配替身主路径、任务授权链替身烟测。初版下面的“未真实推理”只描述追加授权前的阶段。

## 已实现

- 模型设置提供 CodeBuddy CLI / Codex CLI / OpenAI 兼容服务。三个提供方各自记住模型，切换不传入旧提供方模型。当前用户设置仍为 CodeBuddy `glm-5.3-flash`，未代用户保存新偏好。
- 官方 Codex CLI 0.144.1 非交互 JSONL 接入，默认使用 CLI 默认模型，也可填写明确模型 ID。CodeBuddy 与 OAI 接口保留。网络类型由 Pydantic/OpenAPI 重新生成。
- 移除“聊天 / Agent 任务”两个页面。同一输入框以“仅讨论 / 任务内执行（先授权）”区分权限，默认没有工具执行授权；任务卡、进度和证据就在同一对话中。切换权限保留草稿，准备失败保留输入。
- 统一业务工作台默认显示该 Agent 输入，明确附带当前已保存模块草稿用于讨论；原手动表单、旧工作台和 Mock 导入进入高级设置，既有本地数据不迁移、不删除。任务执行目前只使用目标，不附带模块草稿，界面明确提示。

## 隔离与验证

使用 OpenAI Docs 技能核对 [官方非交互 CLI 文档](https://learn.chatgpt.com/docs/non-interactive-mode)，并核对安装版本与相同 release 源码。`--ignore-user-config` 配合 `CODEX_EXEC_SERVER_URL=none` 不创建文件或执行环境；CLI 不注册需要环境的 apply_patch、view_image，Shell/MCP/插件/应用等另明确禁用。内部计划工具不等于外部操作权。版本变化明确阻止推理，不能靠提示词假装隔离。

- Codex transport 替身主路径烟测：1 项通过。
- Provider 独立临时 SQLite 往返切换及 Codex 路由烟测：1 项通过。
- CLI 配置解析：通过；使用不存在的本地 provider 在推理前停止，不发起网络认证/推理。
- 4301 启动、健康、模型列表：通过；Codex 候选已出现在 API。
- 实际浏览器：三个 provider 选项可见；选择 Codex 后取消，没有保存偏好。修复设置标签被紧凑模型 CSS 隐藏的问题。同一输入框切换权限保留未发送草稿；烟测草稿随后清除。没有发送 AI 请求或新建任务。
- 本轮相关文件类型检查未见诊断；全仓历史类型债仍存在，不能宣称全项目通过。完整测试未运行。

## Limitations

不是全部生产节点已自动化。真实执行仍是此前验收的基础资产 Blender → Unity 闭环；角色/动画、复杂世界、渲染、构建、游测、发布等尚未补齐真实处理器。默认 Agent 输入和折叠手动配置是入口改造，不是外部能力完成证明。

Codex `gpt-5.6-sol / low` 的最小文件操作已真实通过，不代表其他模型、持续会话、复杂生产流程或稳定性验收。失败不切回 CodeBuddy/Mock。没有执行 Blender/Unity、新游戏案例、构建、渲染或 playtest。用户原项目、布局与历史验收目录保留。当前执行任务仍使用新独立目录，不接管既有项目，也未实现像桌面 Codex 那样的全部持久会话体验。
