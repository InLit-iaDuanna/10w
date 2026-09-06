# SceneOps Forge V5 · AI 生产工作台

制作卡片现在可选择“导入已有模型”或“新建模型”。导入 GLB/FBX 后由真实 Blender 检查并生成 `.blend`、预览 GLB、Unity 交换 FBX；新建在唯一主对话中逐块对齐，每条新回答都会追加一个真实 Blender/GLB 草稿版本。确认的版本可存入项目资产库，再进入 Three.js 环境场景人工摆放，或继续由同一个主对话让 AI 使用库内资产搭建。两条模型路径都写入卡片 Git 工作树且不自动提交/合并，归一化另存版本。验证范围见 [卡片模型烟测](CARD_ASSET_WORKFLOW_SMOKE.md)。

最新：同一 Agent 输入框通过权限区分讨论和执行，不再分两个页面；工作台默认 Agent 输入，手动表单放入高级设置。模型设置可切换 CodeBuddy CLI、Codex CLI 与 OAI 兼容服务。Codex 完全权限须单独确认，`gpt-5.6-sol / low` 已真实完成独立文件创建/读回烟测；其他生产环节未因此自动验收。[本次说明](CODEX_PROVIDER_HANDOFF.md)。

一个 Web、一个 API，原生 Dockview 停靠编辑器，不使用 iframe。首页为对话和四边拉手；点击「本地项目」创建空项目。向内拖动或双击四边拉手，在拉出的区域选择功能，并直接由该区域承载；区域顶部「选择功能」可原位切换，拆分/浮动需主动选择。首次启动不导入示例、不执行作业，AI 默认「CLI 默认模型」，不是 Mock。

V5 增加目标理解、明确选中的项目上下文、可审阅生产计划、受控运行记录、恢复建议和模板草稿，并重做统一 UI/UX。默认 CodeBuddy Code CLI，也可以显式配置 OpenAI-compatible URL / API Key。当前交付是计划与运行主干，不是已验证的 Blender → Unity 全生产链。详见 [V5 交付说明](V5_HANDOFF.md)。

最新增加「Agent 任务」：输入目标、确认一次范围后，自动准备独立工程并执行类型化动作。2026-09-05 已用真实 CodeBuddy `glm-5.3-flash` 完成 Blender 创建箱体 → 保存/导出 FBX → Unity 导入/放置 → 两端身份、尺寸和控制台核验，共 4 次模型调用。此项是有界基础资产闭环，不代表整条游戏生产链完成。[使用与实测证据](AGENT_LIVE_VERIFICATION.md)。

## 安装与启动

当前版本采用区域内层级拆分、中性灰配色和游戏生产流程树；不再在统一页面外围叠加全局抽屉。见 [最新交互与接入状态](NESTED_REGION_VERIFICATION.md)。

最新交互：全部窗口关闭后回到中央聊天，四边可拉满并拖回收起；发送立即显示用户消息。右上角「诊断」可查看/导出本机最近 200 条界面记录。[验证和限制](INTERACTION_POLISH_VERIFICATION.md)。

顶部/底部拉出后现在直接显示搜索与功能列表；聊天支持 Enter 发送、Shift+Enter 换行。用户授权的扩展功能回归及未通过项见 [UI 功能验证](UI_FUNCTIONAL_VERIFICATION.md)。

最新界面已改为紧凑的石墨灰/蓝色工作台：顶部保留本地项目，区域标题选择功能，更多操作收进菜单。原四边拉出和原位承载逻辑保留。范围与验证见 [UI 更新烟测](UI_REFRESH_SMOKE.md)。

应用根为 `sceneops_forge_codex_full_pack_v3`。需要 Node >= 22.12、pnpm 11.13、Python 3.12；CodeBuddy CLI 可稍后自行安装及登录，缺少 CLI 不影响打开工作台。

首次手动安装（不会运行本项目测试）：

```sh
cd /Users/isduanna/Documents/10w/sceneops_forge_codex_full_pack_v3
pnpm install --ignore-scripts
uv venv .venv
uv pip install --python .venv/bin/python -r services/api/requirements.txt
```

没有 uv 时，可用 Python 3.12 的 `python3 -m venv .venv` 与 `.venv/bin/python -m pip install -r services/api/requirements.txt`。

之后只需：

```sh
pnpm dev
```

- Web：[http://127.0.0.1:4300](http://127.0.0.1:4300)
- API 健康接口：[http://127.0.0.1:8300/api/health](http://127.0.0.1:8300/api/health)
- 普通 API 请通过 Web 的 `/api` 或 `/v1` 代理访问。每次启动生成仅服务端使用的本地令牌；浏览器写请求需要同源 Origin。不会把令牌打包给前端。
- 可显式设置 `SCENEOPS_WEB_PORT`、`SCENEOPS_API_PORT`、`SCENEOPS_PYTHON`。端口冲突报错，不结束其他工作台服务。Ctrl+C 仅停止本次启动器的子进程。
- 启动器不自动安装依赖、不跑测试、构建、案例、外部工具或 AI 推理。

### 与原服务并存的 V5 预览

本轮不主动停止原有服务或改动原数据，V5 使用独立的持久目录。收尾时发现早先后台进程已结束，仅重新启动 V5 预览：

```sh
SCENEOPS_DATA_DIR="$PWD/.local/v5-preview" SCENEOPS_WEB_PORT=4301 SCENEOPS_API_PORT=8301 pnpm dev
```

预览入口为 [http://127.0.0.1:4301](http://127.0.0.1:4301)，API 为 8301。预览已运行时不要重复启动。这里创建的数据保存在 `.local/v5-preview/`，不自动复制或合并原 `.local` 数据。今后使用默认端口前，请自行关闭占用端口的旧服务；启动器不会替你结束它。

## 工作台分组

| 入口 | 合并的功能 |
| --- | --- |
| 对话与工作区 | 首页聊天、停靠布局、工具库、命令搜索、本地项目 |
| 项目与制作规划 | 项目需求、功能设计、任务和生产计划 |
| 概念与资产 | 概念规格、资产制作、资产库与评审 |
| 角色与动画 | 角色、骨骼、动作与动画片段 |
| 世界与逻辑 | 场景对象、空间布局、玩法状态与逻辑 |
| 界面、音频与特效 | UI、音频、VFX/Shader 草稿与原编辑器 |
| 渲染工作台 | 渲染配方、AOV 与已有产物证据 |
| Unity 与构建 | Unity 提案、构建发布配置与产物 |
| 版本与评审 | 变更集、评审、协作与版本记录 |
| AI 游测 | 游测规格、轨迹和问题证据 |
| 集成与运维 | 集成连接、运行观察和日志 |

## 数据与 AI

项目、聊天、模型选择、明确保存的模块草稿存入 `.local/sceneops.sqlite3`；原领域存储按项目隔离放在 `.local/projects/`。整个 `.local` 忽略 Git。备份时先停止本应用，然后复制完整 `.local`。`SCENEOPS_DATA_DIR` 可显式指定存储目录。不会迁移旧实验工作台的演示数据。

编辑器临时状态留在模块内；停靠布局单独存在浏览器 localStorage，不整体写入数据库。切换项目会提示未保存修改。固定上下文的面板仍跟随其固定项目，不会因全局切换而混入另一项目。

示例只有手动「导入 Mock 示例」后才载入，并保持 Mock 标记。导入不代表任何生产、审批或验证已执行。各模块原有外部链能力没有在本轮补齐。

AI 通过本机 `codebuddy --print --output-format json` 调用，共用模型设置；默认省略 `--model`，明确选模型才传入。禁用工具并限制 MCP，不允许 AI 自己写文件或执行业务操作。聊天使用本应用保存的历史，模块上下文由你明确选择；建议手动采用。支持取消、超时、手动重试；不可用时显示错误，不切换 Mock。模型列表只是 CLI 候选目录，不证明账户可用性；登录、额度和模型权限待你首次发送时验证。[官方 CLI 参考](https://www.codebuddy.ai/docs/cli/cli-reference)。

在首页「提供方设置」可切换兼容接口，填写服务根地址（例如 `https://your-provider.example/v1`）、模型 ID 和 Key；请求追加 `/chat/completions`。外部地址须为 HTTPS，本机回环地址可使用 HTTP。Key 只保存在本地权限 `0600` 的 `ai-provider-secrets.json`，按完整服务地址绑定，不返回前端、不存浏览器、不自动传给新地址。备份目录包含密钥，请妥善保管。[官方 Chat Completions 格式](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。

### AI 生产计划

先创建或选择项目，再打开「生产计划」，输入目标、约束及明确选中的已保存模块草稿。生成计划会发起两次模型调用，但不会开始执行；审阅步骤、模型路由、预算和阻塞原因后，才可手动开始可执行的计划。十个产品专家目前负责分析和建议，不控制外部制作工具。

运行默认在用量不明时禁止继续付费调用；可明确选择「按调用次数限制」策略，持久记录调用次数并限制时间/重试。未知 token 和费用始终显示未知，不能视为可靠的金额上限。生成计划的两次调用、手动请求恢复建议的一次调用不计入后续 Run 预算；不自动重试这些请求。可在能力面板分别设置 fast / standard / reasoning / vision / player 层级模型，留空沿用全局模型；层级名本身不证明模型具备视觉或玩家工具能力。

## 维护与兼容

`apps/web/workbenches.json` 是分组声明，`pnpm generate:workbenches` 生成编辑器目录。网络类型由后端公开模型/OpenAPI 生成：`pnpm generate:workspace`、`pnpm generate:ai`、`pnpm generate:harness`、`pnpm generate:agent`、`pnpm generate:card-assets`、`pnpm generate:environment`。这些生成命令不执行测试或业务操作。

API 和生成命令统一从 `services/api/requirements.txt` 中显式声明的本地包加载源码。开发用 Python 命令通过 `node scripts/python.mjs <脚本或参数>` 运行，避免依赖 editable 安装的 `.pth` 文件；不扫描用户生产目录或动态发现插件。Python 依赖变化时手动重新运行上述安装命令。

旧入口保留：`pnpm lab <id>`，参见 `apps/labs/README.md`，但主应用不依赖启动它们。旧入口是原实验环境，可能有原来的显式 Mock 流程；它们不共享主应用的空态承诺。依赖已统一到根 workspace/锁文件，旧说明中的子目录安装命令以本 README 为准。原 worktree、未提交改动与历史数据未改动。

## Limitations

V5 初始交付只做空态烟测。用户随后授权真实 AI 连通检查，GLM 已取得聊天、建议、结构化计划和单步专家分析的实际成功结果；同时记录了 JSON 校验拒绝和 HY4 超时，并非稳定性或内容质量验收。见 [AI 真实验证](AI_LIVE_VERIFICATION.md)。CLI 结构化输出由应用严格校验，不依赖本机存在挂起问题的 `--json-schema` 模式，仍禁用所有工具。

最新授权范围内已运行基础资产的真实 Blender/Unity 闭环及相关定向测试。未运行完整测试套件、生产构建、游戏 demo、渲染或 AI playtest；其他外部生产能力仍保持原 planned/blocked 状态。类型检查仍有历史诊断，不能宣称全项目通过。OAI 接口保留但未真实验证。Dockview 保留原有评估水印。[初始烟测记录](V5_SMOKE.md)、[能力缺口](PROTOTYPE_GAP_MATRIX.md)；旧验收文档仅反映对应日期，不覆盖本次结果。
# 新旅程：单人协作策划

从「本地项目」创建文件夹项目，进入 idea → grill-me 对齐 → 大纲 v1 → Three.js → 制作卡片。操作、烟测和未接入范围见 [阶段一说明](PLANNING_JOURNEY_STAGE1.md)。旧项目和原有生产路径保留。
