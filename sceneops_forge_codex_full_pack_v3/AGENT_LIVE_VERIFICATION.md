# 任务级 Agent：使用与真实验收

2026-09-05。本轮按用户批准的任务授权计划执行；不操作现有生产工程，不运行游戏 demo、生产构建、渲染或 AI playtest。

## 使用

在应用根执行 `pnpm dev`，默认 Web 4300/API 8300；当前用户预览沿用 4301/8301 和 `.local/v5-preview`。启动器不安装依赖、不创建案例、不调用模型，等待 API 健康后才开放 Web。

对话上方选择「Agent 任务」，描述目标，点击「准备任务」，审阅工作目录、能力、模型和预算后确认一次。无需填 Blender/Unity 路径、端口或插件参数。普通「聊天」仍只问答，不执行工具。首版一个独立项目支持一个有界箱体资产；选择已有任务项目会明确拒绝，新的目标使用新独立项目。

AI 仍使用 CodeBuddy CLI，且 CLI 的文件、Shell、MCP 工具限制保留；模型只输出结构化行动，应用执行已注册能力。OAI-compatible URL/API Key 接口保留，不自动切换提供方或 Mock。提供方与模型在任务准备时固定。

预算为总计 8 次模型请求、20 分钟、每动作最多 2 次尝试，规划和修复计入。费用未知明确显示未知，不承诺美元硬限额。连接阻断可在原授权未过期时「检查连接并继续」；过期或未知写入结果不自动放宽授权。

## 真实验收

- 任务：`task_ef6745aaba5543a19ff645cbfe38dd3a`。
- 独立项目：`prj_089e33f927e547d99665770ece54abd3`。
- 完成时间：`2026-09-05T11:52:11.827316Z`；状态 `completed`，4/8 模型调用，费用未知。
- 模型：CodeBuddy `glm-5.3-flash`，实际选择创建、导出、Unity 导入和最终核验四个动作。
- Blender 5.1.2：可见专用会话；对象「Agent 验收箱体」，asset `ast_smokecube01`、object `sobj_smokecube01`，Z-up 尺寸 `[1,2,3]` 米；保存 `.blend`、FBX 和 identity sidecar。
- Unity 2022.3.62f3c1：用户激活后真实可见专用会话，导入 FBX 并保存 `Assets/SceneOpsAgent.unity`；同一 asset/object identity，instance `inst_smokecube01`，Y-up 尺寸 `[1,3,2]` 米；`errors: []`。
- Unity 资产 GUID：`aec3d82f40db045ec809b9d5310c9191`，真实 GlobalObjectId 同时保存在任务回读证据。
- 最终 `agent.finish` 重新读取两端会话，`verified: true`；不是模型文本或旧缓存判定成功。浏览器任务页显示“已验证完成”，原生 Unity 场景窗口可见实际箱体。
- Blender OS 隔离探针在实时回读中为 `outside_write_denied: true`。Unity 采用固定类型化能力、项目路径检查和私有 IPC；不声称 Unity 整个进程被 OS 文件系统沙箱限制。

本机证据存储：`.local/agent-validation/sceneops.sqlite3` 的任务/事件及 Harness 记录；产物为 `.local/agent-validation/agent-workspaces/prj_089e33f927e547d99665770ece54abd3/`。它们不提交 Git、不迁入用户预览项目、不作为默认示例加载。目录保留，可由用户独立打开。

## 实测发现和修复

首次 Unity 连接未完成：应用数据目录中的 embedded UPM 子目录带 macOS hidden 标记，Unity 没有导入桥接程序集。改为固定引用应用随附 canonical package，旧自有 embedded 包移入当前工程私有备份，不删除用户数据。错误分类不再把许可证成功日志或更新检查 404 当作连接失败原因。

在原任务 blocked 状态重启本轮独立后端后，显式恢复沿用原 grant、动作与 request ID，模型次数仍为 3；Unity 导入成功后第 4 次模型调用请求完成。完成检查自动重连 Blender、读取已保存场景，不重放创建/导出。

## 定向验证

已运行 Blender 会话协议 8 项、Unity 会话 15 项和 Agent 任务 14 项定向测试，合计 37 项通过，覆盖授权、范围拒绝、预算、取消、恢复和双端验收。独立复核发现的日志 symlink 越界和过期授权停止响应过量返回也已修复并补回归。这些测试使用明确注入的会话/模型替身，不冒充真实 DCC；真实证据单独列于上节。

前端类型源由 Pydantic/OpenAPI 生成。执行了类型检查并筛查本轮 Agent/对话/工具树组合文件，没有这些文件的诊断；全仓仍存在先前模块类型债，不能宣称全项目类型检查通过。

## Limitations

- 仅基础箱体交换闭环，其他模块的 UI 不等于真实工具处理器；不是整条游戏生产链完成。
- 真实写入派发后进程中断、结果不确定时仍停止并要求人工检查，不盲目重放。自动恢复覆盖可确认的连接阻断和已保存会话，不包含所有生产恢复场景。
- 重复执行、取消、编译等待、预算耗尽有定向测试；并未把所有边界都在真实 DCC 中逐一故障注入。Unity Editor 完整测试套件未运行。
- OAI 兼容提供方本轮未真实推理；GLM 这次成功不代表稳定性或成本验收。
- 主入口原有渲染面板仍出现读取接口 HTTP 422；它不是本轮已验证的 Agent 资产能力，未执行渲染或修复渲染业务。
- Unity 使用系统许可服务及固定随附包，运行日志留在本机；勿公开原始编辑器日志。公开错误路径按安全规则脱敏。
- 使用 unity-mcp-orchestrator 技能的状态先读、等待编译、控制台回读原则；实际连接是 SceneOps 类型化适配器，并非安装第三方任意代码 MCP。
