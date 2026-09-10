# 导出 Agent 系统提示词与技能（2026-09-08）

**后续状态：原生导出执行已接通，支持本机命令与环境补齐，见 [最新接入记录](NATIVE_EXPORT_AGENT.md)。下文保留本技能交付时的阶段记录。**

本轮按用户要求集中整理提示词与发布知识，不继续为每一种环境缺项增加固定流程，也不实际安装 SDK、发布应用或运行电脑操作。

## 已交付

系统提示词位于 `modules/ai-agent-runtime/backend/src/sceneops_ai_agents/prompts/export-agent.md`。工作方式为：读取当前授权、主机与项目事实，发现缺项后使用真实可用工具补齐、验证并继续；常规工程问题不交给用户抄命令。包生成、独立启动、真机交互、上传与正式发布分开报告。

技能位于同一包的 `skills/`：

| Skill | 作用 |
|---|---|
| sceneops-export-environment | 检查本机与工程版本，补齐 Node/JDK/SDK/依赖和路径配置 |
| sceneops-export-android | Capacitor APK/AAB 构建、Gradle/SDK 诊断、资源与触控验证 |
| sceneops-export-desktop | Electron Mac/Windows 构建、跨架构原生依赖、包内资源与独立启动 |
| sceneops-release-publish | 用户明确要求时处理签名、渠道、Fastlane/商店或公开发行 |

每个技能的 references/sources.md 记录来源、固定版本与采用范围。没有自动安装远程 skill，没有搬入包含清空全局缓存、传输全部环境变量或默认迁移到云平台的指令。

## 实际运行加载

`load_export_knowledge(platforms, native=False, publish=False)` 读取产品自有系统提示词，按平台加载环境、安卓或桌面技能。仅明确发布模式加载发布技能；未知平台不能指定任意文件。导出对话真实调用该加载器，调用记录包含 skill_version 与 loaded_skills。

原生游戏任务的 `task_game_instructions` 追加按需技能目录及可读取的绝对资源路径；仅当目标涉及导出时读取对应技能，不让普通游戏开发自动安装 SDK。已有原生执行记录仍保存实际系统指令，目录列出不等于技能已读取或操作已执行。

`native=True` 提供原生导出会话的完整知识提示词，由具备真实工具和任务授权的执行器使用。提示词不会创建电脑工具或放宽现有权限。

## 来源

- [Capawesome 团队维护的 Capacitor skills](https://github.com/capawesome-team/skills/tree/cc8319c70de1fdb02d99823a359ecaf3bf4db960)：MIT，参考项目发现、版本识别、同步与故障定位。
- [Electron Builder](https://github.com/electron-userland/electron-builder/tree/0d47ef5c4dda24939e5a6b02927440bdc2da1cd1)：MIT，参考原生依赖、平台/架构构建与签名限制。
- [Fastlane](https://github.com/fastlane/fastlane/tree/3a4fc36716dec206b3f5441f19f0a5193733c828)：MIT，参考供稿与发布渠道、状态和元数据覆盖语义。

以上是固定 Git 版本引用，没有新增摘要算法。本地技能为 SceneOps 中文原创工作指导，不复制整份上游手册。另核对 Android、Capacitor 与 Electron 官方当前资料，版本示例不作为所有工程的固定要求。

## 验证与边界

四个 Skill 均通过 skill-creator 格式检查；导出对话/资源加载七项测试、原生提示词三项回归通过，模型传输使用注入提供方，未发起真实模型调用。

当前导出页面仍走结构化动作回调（continue/cancel/configure/request_development）；本次没有把它伪装成电脑控制接口。独立原生导出 profile、与 AgentTaskService 授权/取消/恢复的接线仍需实现，不能绕过该服务直接调用 ProviderService.execute_task。现有 project-demo-agent 具有游戏初始化与交付副作用，未拿它冒充导出专用任务。

因此，本轮完成的是可加载的系统提示词和四个发布技能，不宣称导出页面已经能自动安装 SDK。实际电脑工具、签名和商店操作仍依据执行器与已授权范围。

独立只读行为推演覆盖：JDK 已装但路径缺失/SDK 许可未授权、Mac 成功与 Windows 原生依赖缺失、Play 仅准备不上传。按结果澄清 Android CLI 来源、不可获得的目标环境，以及 draft/metadata 也属于商店写入。未执行真实安装或发布。
