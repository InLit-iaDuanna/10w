# 本工作台依赖

运行依赖均通过已知 npm/PyPI registry 安装，无第三方 CDN、字体或远程图像请求。

| 依赖 | 版本 | 许可证 | 用途 |
|---|---|---|---|
| React / ReactDOM | 19.2.8 | MIT | 对齐共享 React UI |
| TypeScript | 6.0.3 | Apache-2.0 | 前端工具链版本 |
| Vite | 8.0.0 | MIT | 独立开发 Web 与 API 代理 |
| Three.js | 0.183.2 | MIT | 几何代理、相机与 ray picking |
| TanStack Query | 5.90.21 | MIT | 本地 API 请求状态 |
| openapi-fetch | 0.15.0 | MIT | 单一生成合同客户端 |
| FastAPI | 0.128.8 | MIT | 组合现有业务服务 |
| Pydantic | 2.13.2 | MIT | API 合同与类型源 |
| Uvicorn | 0.39.0 | BSD-3-Clause | localhost ASGI 服务 |
| openapi-typescript | 7.13.0 | MIT | 开发时生成 TypeScript 合同 |
| TypeScript（代码生成工具独立环境） | 5.9.3 | Apache-2.0 | 满足生成器 5.x peer 范围 |

React/DOM/Three 的 `@types` 为 MIT。Three 未引入额外引擎；图是 SVG，未添加新的图框架。各依赖的实际 LICENSE 文件随安装包提供。
