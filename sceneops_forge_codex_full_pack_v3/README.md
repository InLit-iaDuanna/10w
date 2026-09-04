# SceneOps Forge 统一工作台

一个 Web、一个 API，原生 Dockview 停靠编辑器，不使用 iframe。首页为对话和四边拉手；点击「本地项目」创建空项目，向内拖动或双击四边拉手打开工具库/命令搜索，再打开各工作台。首次启动不导入示例、不执行作业，AI 默认「CLI 默认模型」，不是 Mock。

## 安装与启动

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

## 维护与兼容

`apps/web/workbenches.json` 是分组声明，`pnpm generate:workbenches` 生成编辑器目录。网络类型由后端公开模型/OpenAPI 生成：`pnpm generate:workspace`、`pnpm generate:ai`。这些生成命令不执行测试或业务操作。

旧入口保留：`pnpm lab <id>`，参见 `apps/labs/README.md`，但主应用不依赖启动它们。旧入口是原实验环境，可能有原来的显式 Mock 流程；它们不共享主应用的空态承诺。依赖已统一到根 workspace/锁文件，旧说明中的子目录安装命令以本 README 为准。原 worktree、未提交改动与历史数据未改动。

## Limitations

本轮只做启动空态烟测；代理没有运行完整测试、类型检查、生产构建、demo 案例、真实 AI 推理、Unity、Blender、渲染或 AI playtest。可见页面的手动 AI 请求出现 CLI 错误，真实推理尚未成功验证。Dockview 保留原有未授权水印。保存草稿不等同于外部生产能力已验证。烟测结果、持久化范围与进一步未验证项见 `INTEGRATION_SMOKE.md`。
