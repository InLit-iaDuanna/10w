# SceneOps Forge V5 · AI 生产工作台

一个 Web、一个 API，原生 Dockview 停靠编辑器，不使用 iframe。首页为对话和四边拉手；点击「本地项目」创建空项目。向内拖动或双击四边拉手，在拉出的区域选择功能，并直接由该区域承载；区域顶部「选择功能」可原位切换，拆分/浮动需主动选择。首次启动不导入示例、不执行作业，AI 默认「CLI 默认模型」，不是 Mock。

V5 增加目标理解、明确选中的项目上下文、可审阅生产计划、受控运行记录、恢复建议和模板草稿，并重做统一 UI/UX。默认 CodeBuddy Code CLI，也可以显式配置 OpenAI-compatible URL / API Key。当前交付是计划与运行主干，不是已验证的 Blender → Unity 全生产链。详见 [V5 交付说明](V5_HANDOFF.md)。

## 安装与启动

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

`apps/web/workbenches.json` 是分组声明，`pnpm generate:workbenches` 生成编辑器目录。网络类型由后端公开模型/OpenAPI 生成：`pnpm generate:workspace`、`pnpm generate:ai`、`pnpm generate:harness`。这些生成命令不执行测试或业务操作。

API 和生成命令统一从 `services/api/requirements.txt` 中显式声明的本地包加载源码。开发用 Python 命令通过 `node scripts/python.mjs <脚本或参数>` 运行，避免依赖 editable 安装的 `.pth` 文件；不扫描用户生产目录或动态发现插件。Python 依赖变化时手动重新运行上述安装命令。

旧入口保留：`pnpm lab <id>`，参见 `apps/labs/README.md`，但主应用不依赖启动它们。旧入口是原实验环境，可能有原来的显式 Mock 流程；它们不共享主应用的空态承诺。依赖已统一到根 workspace/锁文件，旧说明中的子目录安装命令以本 README 为准。原 worktree、未提交改动与历史数据未改动。

## Limitations

V5 初始交付只做空态烟测。用户随后授权真实 AI 连通检查，GLM 已取得聊天、建议、结构化计划和单步专家分析的实际成功结果；同时记录了 JSON 校验拒绝和 HY4 超时，并非稳定性或内容质量验收。见 [AI 真实验证](AI_LIVE_VERIFICATION.md)。CLI 结构化输出由应用严格校验，不依赖本机存在挂起问题的 `--json-schema` 模式，仍禁用所有工具。

未运行完整测试、类型检查、生产构建、游戏 demo、Unity、Blender、渲染或 AI playtest；恢复、审批与回滚没有实际业务验证，13 项外部能力仍 planned/blocked。OAI 接口保留但未真实验证。Dockview 保留原有评估水印。[初始烟测记录](V5_SMOKE.md)、[能力缺口](PROTOTYPE_GAP_MATRIX.md)；`INTEGRATION_SMOKE.md` 只记录上一版。
