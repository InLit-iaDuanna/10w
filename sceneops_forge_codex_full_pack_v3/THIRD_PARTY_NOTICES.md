# Third-Party Notices

Playwright 1.62.1 (Apache-2.0) supplies the optional local browser observation runtime. Its Chromium download retains the upstream browser's bundled notices and licenses.

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

## 本地导出工具（2026-09-08）

导出隔离目录按用户授权下载固定版本的 Vite 8.2.2、Electron 44.2.0、electron-builder 26.15.3、Capacitor 8.5.1，用于 Web、桌面及安卓包装。各工具项目采用 MIT 许可证；Electron 分发另包含 Chromium 等第三方许可，打包工具提供的许可文件须随发行产物保留。工具版本集中在 `modules/build-release/backend/src/build_release/export_templates.py`。

## 导出发布技能参考来源

2026-09-08 核对 capawesome-team/skills（MIT）、electron-userland/electron-builder（MIT）、fastlane/fastlane（MIT）。SceneOps 发布技能为重新编写的工作指导，未复制整份源码或手册；来源 commit、许可与采用边界见 `EXPORT_AGENT_SKILLS.md` 及各技能 references/sources.md。

## 原生材质与灯光（2026-09-09）

- Three.js 0.185.1、@types/three 0.185.4：MIT；原生模型预览、WebGPU、TSL 与 glTF 读写，工作台相关包统一版本。
- Zod 4.5.4：MIT；结构化材质、Shader 操作与固定内部 JSON 入口校验。使用 `zod/v4`，与宿主既有 Zod 3 并存。
- JSZip 3.10.1：采用 MIT 许可；工程包及 Shader 包编码。
- tsx 4.23.13：MIT；固定内部 TypeScript 校验入口。
- @webgpu/types 0.1.72：BSD-3-Clause；WebGPU 类型定义。
- gltf-validator 2.0.0-dev.3.10：Apache-2.0；导出 GLB 的 Khronos 校验测试。
- Draco 浏览器解码文件取自已锁定 Three.js 分发，Apache-2.0 许可随 `apps/web/public/draco/LICENSE` 保留，用于压缩模型读取。

Lumaform 领域实现迁入自用户提供的本地 shader-ai 项目，不包含其独立应用导航或全局样式。
