# Third-Party Notices

This repository declares the following third-party Python dependencies for the core-contract and module-runtime implementation. Full license texts are distributed by their respective packages.

| Package | Use | License |
|---|---|---|
| Pydantic | Typed core contracts and module manifest source | MIT |
| PyYAML | Safe loading of `module.yaml` | MIT |
| Hatchling | Python package build backend | MIT |

Tests use the Python and Node.js standard libraries and add no test-framework dependency.

## Three.js 游戏制作知识（S1）

从 [majidmanzarpour/threejs-game-skills](https://github.com/majidmanzarpour/threejs-game-skills/tree/e5f301d548bb18c530afbece78cd25082f4cda9c) 固定提交改写 Director、Gameplay、Debug、QA 方法，版权 © 2026 Majid Manzarpour，MIT。
逐文件来源和改写说明见 `modules/ai-agent-runtime/backend/src/sceneops_ai_agents/skills/SOURCES.md`，完整许可随该目录 `LICENSE` 打包。未复制 scaffold、示例资产、外部生成脚本或依赖。

## 独立工作台工具链

- React/ReactDOM 19.2.8：MIT；真实 UI。
- TypeScript 6.0.3：Apache-2.0；共享类型工具链。
- Vite 8.0.0：MIT；localhost 开发服务。
- TanStack React Query 5.90.21：MIT；模型目录服务器状态。
- openapi-typescript 7.13.0：MIT；从 Pydantic/OpenAPI 生成网络类型。
- Dockview React 8.2.0：MIT；唯一停靠引擎。
- Dockview Enterprise 8.2.0：商业许可，当前仅官方允许的本地无 key 评估，保留水印；无生产许可声明。https://dockview.dev/docs/overview/enterprise-setup/
- FastAPI 0.128.8 / Pydantic 2.13.2：MIT；uvicorn 0.39.0：BSD-3-Clause；本地 CodeBuddy adapter API。
- CodeBuddy CLI：使用宿主已有 2.144.0 可执行文件，不将 CLI 或凭据打包进仓库。

## V5 AI Provider

Dockview Core 8.2.0（MIT）的受控本地修改见 `patches/dockview-core@8.2.0.patch`：补齐 EdgeGroupView 的公开 setSize 订阅、允许中心剩余尺寸为零，并在原生分界线结束且边栏缩至折叠尺寸时调用公开 collapse。修改四个分发 bundle，未修改版权、许可证或 Enterprise 水印；pnpm 锁文件记录该补丁。升级时确认上游公开尺寸通路、四向拉满和拖回收起均通过，再移除对应补丁。

- HTTPX 0.28.1：BSD-3-Clause；用于异步 OpenAI-compatible Chat Completions HTTP 请求、超时和取消。许可声明依据安装包 METADATA，完整许可随依赖分发。关闭自动重定向及环境代理，不打包服务商凭据。
- jsonschema 4.26.0：MIT；CLI 结构化回复的标准 Draft 2020-12 校验。固定版本，完整许可证随依赖分发；不使用自写 schema 近似算法。
# 任务级 Agent 接入补充（2026-09-05）

新增官方 Codex CLI 0.144.1 文本适配，使用已安装 CLI，无新增 npm/Python 第三方包、无复制第三方 Bridge。CLI 和账户许可沿用官方条款；实现参考官方文档与公开对应版本源码，不自动安装或升级。

本轮常驻连接使用仓库自有 Blender/Unity 适配器；未复制或安装第三方 MCP 服务，未新增外部 npm/Python 包版本。沿用用户本机 Blender 5.1.2、Unity 2022.3.62f3c1 和 CodeBuddy CLI；软件许可/模型账户仍由用户管理。Unity 本地 UPM 引用固定随附 `integrations/unity-package`，不依赖远端浮动分支。Dockview 现有许可声明与水印保留。
# Markdown rendering additions (2026-09-06)

- [react-markdown](https://github.com/remarkjs/react-markdown), 10.1.0, MIT: CommonMark rendering as React nodes, without raw HTML execution.
- [remark-gfm](https://github.com/remarkjs/remark-gfm), 4.0.1, MIT: tables, task lists and other GFM syntax. Remote images are not automatically loaded by the shared renderer.
