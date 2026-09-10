# SceneOps Forge V5 · AI 生产工作台

浏览器验证环境：根依赖包含 Playwright 1.62.1，安装依赖后执行 `pnpm exec playwright install chromium`。生产任务不会自行下载浏览器。原生新制作和续改默认授权内置资产，Agent 可通过目录查询和选材安装工具接入真实素材；安装不等于游戏已加载或试玩通过。

当前新制作主线（2026-09-09）：**SceneOps 对齐目标 → 确认可编辑制作简报与权限 → Codex／CodeBuddy 原生制作 → 工作台接回实际文件、资产和试玩候选 → 准确会话续改**。新工程使用轻量 Three.js / TypeScript / Vite / pnpm 起点。历史任务与编辑服务继续保留；本轮不接 App Server、SDK 或多 Agent 编排。接口、配置与故障处理见 [原生 CLI 制作](modules/ai-agent-runtime/docs/native-cli-production.md)，实际验收见 [验收报告](NATIVE_CLI_PRODUCTION_ACCEPTANCE.md)。

专业制作现在会在主 Agent 开始前调用一次独立的“制作推荐模型”，按本轮任务从内置资产、当前项目资产、有效经验和已有技能中选择材料。游戏、建模、场景、策划和导出共用同一套准备记录；游戏只复制所选素材，并区分推荐、提供、复制、源码引用和运行验证。配置、接口、失败语义与 A/B 验收格式见 [按任务选择资产、经验与制作方式](docs/production-preparation.md)。

工作台内置「暖陶与松影」场景套装：3 套场景、17 件建筑／物件、4 个同造型异色角色，可直接预览、加入项目，并供已授权 Demo 任务复用。见 [固定场景与资产说明](BUILTIN_SCENES.md)。

制作卡片现会主动开始对齐；收束后自动展示执行确认，确认后使用当前项目的开发权限与内置基础资产制作 Demo，成功预览自动在右侧打开。见 [主动对齐与 Demo 执行](DEMO_EXECUTION_FLOW.md)。

2026-09-07 审计问题修复及定向验证结果见 [审计修复记录](AUDIT_REPAIR_20260907.md)：模块一致性、完整 AI 结构纠错、项目错误边界和测试入口已修复；该记录明确区分代码回归与尚未重跑的真实外部全链路。

最新：第一次生成游戏工程代码前，用户可手动选择对象／组件式或 ECS · Miniplex，也可让当前 AI 提供方推荐。确认后会创建真实、可构建和预览的 Three.js 工程，制作卡与卡片 Agent 持续读取同一技术方案。[实现、操作与真实 Agent 验证](GAME_CODE_ARCHITECTURE_MILESTONE.md)。新建项目现已写入可恢复身份，scaffold 形成选择性 Git 基线；新卡从进入时最新的集成提交创建，旧卡保持原 base，复制项目不会静默改绑。[身份与基线里程碑](GAME_PROJECT_IDENTITY_BASELINE_MILESTONE.md)。卡片 Agent 还能在明确授权后自行准备依赖、检查、构建、按日志修复并启动严格 localhost 预览，任务卡按钮复用相同能力。[运行闭环与验收记录](GAME_PROJECT_RUNTIME_MILESTONE.md)。

制作卡片现在可选择“导入已有模型”或“新建模型”。导入 GLB/FBX 后由真实 Blender 检查并生成 `.blend`、预览 GLB、Unity 交换 FBX；新建在唯一主对话中逐块对齐，每条新回答都会追加一个真实 Blender/GLB 草稿版本。确认的版本可存入项目资产库，再进入 Three.js 环境场景人工摆放，或继续由同一个主对话让 AI 使用库内资产搭建。两条模型路径都写入卡片 Git 工作树且不自动提交/合并，归一化另存版本。验证范围见 [卡片模型烟测](CARD_ASSET_WORKFLOW_SMOKE.md)。

最新：同一 Agent 输入框通过权限区分讨论和执行，不再分两个页面；工作台默认 Agent 输入，手动表单放入高级设置。模型设置可切换 CodeBuddy CLI、Codex CLI 与 OAI 兼容服务。Codex 完全权限须单独确认，`gpt-5.6-sol / low` 已真实完成独立文件创建/读回烟测；其他生产环节未因此自动验收。[本次说明](CODEX_PROVIDER_HANDOFF.md)。

一个 Web、一个 API，原生 Dockview 停靠编辑器，不使用 iframe。首页为对话和四边拉手；点击「本地项目」创建空项目。向内拖动或双击四边拉手，在拉出的区域选择功能，并直接由该区域承载；区域顶部「选择功能」可原位切换，拆分/浮动需主动选择。首次启动不导入示例、不执行作业，AI 默认「CLI 默认模型」，不是 Mock。

V5 增加目标理解、明确选中的项目上下文、可审阅生产计划、受控运行记录、恢复建议和模板草稿，并重做统一 UI/UX。默认 CodeBuddy Code CLI，也可以显式配置 OpenAI-compatible URL / API Key。当前交付是计划与运行主干，不是已验证的 Blender → Unity 全生产链。详见 [V5 交付说明](V5_HANDOFF.md)。

最新增加「Agent 任务」：输入目标、确认一次范围后，自动准备独立工程并执行类型化动作。2026-09-05 已用真实 CodeBuddy `glm-5.3-flash` 完成 Blender 创建箱体 → 保存/导出 FBX → Unity 导入/放置 → 两端身份、尺寸和控制台核验，共 4 次模型调用。此项是有界基础资产闭环，不代表整条游戏生产链完成。[使用与实测证据](AGENT_LIVE_VERIFICATION.md)。

## 安装与启动

### macOS 一键启动

在访达中双击根目录的 `启动 SceneOps.command`。首次运行会自动准备网页依赖、Python 3.12 本地环境和 API 运行依赖；完成后同时启动 Web/API 并打开工作台。后续再次双击会直接启动，检测到服务已运行时只打开现有工作台。

启动后请保留打开的终端窗口；关闭窗口或按 Ctrl+C 会停止本地服务。网页右上角的「环境配置」继续负责 CodeBuddy CLI / Codex CLI 的一键安装、官方登录和连接检查，无需手动启动后端。

终端中的等价一键命令：

```sh
pnpm start
```

Node.js 22.12 或更高版本仍需预先安装；一键入口会给出明确提示，不会修改系统权限。

### 开发者手动安装

首次打开后，可用「环境配置」向导选择 Codex CLI / CodeBuddy CLI，一键安装到用户目录，再按提示登录并检查连接。已有兼容安装会直接复用。macOS 支持打开终端登录，Linux 支持安装，Windows 提供手动指南；Node.js 仍需预先准备。[首次配置说明](modules/conversation-home/docs/environment-setup.md)。

当前版本采用区域内层级拆分、中性灰配色和游戏生产流程树；不再在统一页面外围叠加全局抽屉。见 [最新交互与接入状态](NESTED_REGION_VERIFICATION.md)。

最新交互：全部窗口关闭后回到中央聊天，四边可拉满并拖回收起；发送立即显示用户消息。右上角「诊断」可查看/导出本机最近 200 条界面记录。[验证和限制](INTERACTION_POLISH_VERIFICATION.md)。

顶部/底部拉出后现在直接显示搜索与功能列表；聊天支持 Enter 发送、Shift+Enter 换行。用户授权的扩展功能回归及未通过项见 [UI 功能验证](UI_FUNCTIONAL_VERIFICATION.md)。

最新界面已改为紧凑的石墨灰/蓝色工作台：顶部保留本地项目，区域标题选择功能，更多操作收进菜单。原四边拉出和原位承载逻辑保留。范围与验证见 [UI 更新烟测](UI_REFRESH_SMOKE.md)。

应用根为 `sceneops_forge_codex_full_pack_v3`。需要 Node >= 22.12、pnpm 11.13、Python 3.12；CLI 可在工作台的首次配置向导中安装及登录，缺少 CLI 不影响打开工作台。

首次手动安装（不会运行本项目测试）：

```sh
cd 10w/sceneops_forge_codex_full_pack_v3
pnpm install --ignore-scripts
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r services/api/requirements.txt
```

没有 uv 时，可用 Python 3.12 的 `python3 -m venv .venv` 与 `.venv/bin/python -m pip install -r services/api/requirements.txt`。

开发模式之后只需：

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

从「本地项目」创建文件夹项目，进入 idea → grill-me 对齐 → 大纲 v1 → 游戏技术方案 → 制作卡片。操作、烟测和未接入范围见 [阶段一说明](PLANNING_JOURNEY_STAGE1.md)及[架构里程碑](GAME_CODE_ARCHITECTURE_MILESTONE.md)。旧项目和原有生产路径保留。

## 对话直接制作（2026-09-08）

新项目从讨论开始，AI 问清关键问题后直接进入制作。主输入框可选择“执行前询问”或“完全访问”；完全访问使用当前 CodeBuddy/Codex 原生会话，制作后自动检查、构建并提供试玩入口。无需填写方向表单或操作制作卡片。权限范围与执行记录仍可查看，模型不能自行授权。详情见 [对话制作验证](CHAT_FIRST_PRODUCTION.md)。

游戏执行系统提示已补齐按玩法选择的相机策略、世界/屏幕尺寸链路、DPR、宿主缩放与真实视觉检查要求。GLM-5.3 重跑后，宽/窄窗口和 DPR 1/2 显示及移动、收集交付、重开实测通过。见 [验证记录](CHAT_FIRST_PRODUCTION.md)。

## 经验记忆

主对话工具栏新增“经验”，支持查看与纠正当前项目/共享经验。首次启动幂等导入 26 条历史经验，之后只自动整理启用后的新记录；读取和学习可独立关闭。详见 [功能与接口说明](modules/ai-run-distiller/README.md) 和 [实际验收范围](docs/experience-validation.md)。

## Agent 多平台导出

项目菜单或主对话的「导出」可创建安卓、Mac 和 Windows 本地试玩包任务，支持对话、重试与下载。入口、授权与精确验证范围见 [导出交付记录](PLAYABLE_EXPORTS_MILESTONE.md)。

原生导出 Agent 已接通：可在导出页执行本机命令、补齐工具并继续打包，真实 CodeBuddy 命令验证通过。见 [原生导出接入](NATIVE_EXPORT_AGENT.md)。


## 2026-09-09：原生 CLI 制作主线

新游戏制作采用「方向对齐 → 确认可编辑制作简报 → Codex/CodeBuddy 原生会话 → 工作台回流 → 准确会话续改」。权限独立选择 scoped/full；完整权限也需要确认简报。旧任务和领域编辑服务保留，新制作入口不再使用逐动作 JSON 规划器。

工作区级源码登记与任务级 MCP 桥连接真实源码、GLB 资产版本、场景实例和试玩候选；新工程采用所选架构的轻量起点。手动修改后的「更新作品」只执行物化和构建，不调用模型。详见 [原生制作说明](modules/ai-agent-runtime/docs/native-cli-production.md)。

## 对话中的学习与记忆（2026-09-09）

本次依据、记忆纠正和学习沉淀直接跟随消息与制作任务，支持来源、版本、编辑和撤销；集中入口保留项目记忆、通用经验和学习动态。详见 [功能及验证说明](docs/conversation-memory.md)。
