# 第三方依赖

生产依赖：

- FastAPI（MIT）：组合 Concept Lab HTTP router 与 OpenAPI。
- Pydantic（MIT）：网络和版本化数据合同的源定义。
- React（MIT，peer dependency）：宿主工作台渲染两个 lazy editor。

仅开发/测试：

- pytest（MIT）、httpx（BSD-3-Clause）、jsonschema（MIT）、PyYAML（MIT）：后端单元、API 和 schema 验证。
- TypeScript（Apache-2.0）、`@types/node` / `@types/react`（MIT）：前端严格类型检查。

Python 精确解析记录在 `backend/uv.lock`，Node 精确解析记录在 `frontend/package-lock.json`。模块不包含供应商图像模型 SDK、模型权重或下载资产。
