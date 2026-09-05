# Third-Party Notices

This repository declares the following third-party Python dependencies for the core-contract and module-runtime implementation. Full license texts are distributed by their respective packages.

| Package | Use | License |
|---|---|---|
| Pydantic | Typed core contracts and module manifest source | MIT |
| PyYAML | Safe loading of `module.yaml` | MIT |
| Hatchling | Python package build backend | MIT |

Tests use the Python and Node.js standard libraries and add no test-framework dependency.

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

- HTTPX 0.28.1：BSD-3-Clause；用于异步 OpenAI-compatible Chat Completions HTTP 请求、超时和取消。许可声明依据安装包 METADATA，完整许可随依赖分发。关闭自动重定向及环境代理，不打包服务商凭据。
- jsonschema 4.26.0：MIT；CLI 结构化回复的标准 Draft 2020-12 校验。固定版本，完整许可证随依赖分发；不使用自写 schema 近似算法。
