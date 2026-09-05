# V5 开源依赖采用记录

- 复用现有 FastAPI / Pydantic / SQLite / React / TanStack Query / Dockview，不引入第二个工作流引擎或停靠框架。
- 新增 HTTPX **0.28.1**，BSD-3-Clause，用于异步 Chat Completions HTTP、超时和取消。版本在 AI Provider 的 pyproject 中固定；许可依据本地安装包 METADATA。
- AI 连通修复采用 `jsonschema` **4.26.0**（MIT）校验无工具 CLI 返回的 JSON，支持 Pydantic 生成的 `$defs`、引用及组合 schema；不用字符串清洗或自写不完整校验。[官方校验文档](https://python-jsonschema.readthedocs.io/en/stable/validate/)。
- 保留现有 `openapi-typescript` 生成链。`integration-center` 明确声明已使用的 `openapi-fetch` **0.17.0**，不依赖其他 lab 间接提供。
- V5 参考矩阵是设计参考，未自动下载或复制其中框架源代码，未安装 Bridge，未接入其中的外部制作服务。
- Dockview Enterprise 继续本地评估并保留水印；不声明已获得生产商业授权。更多依赖见根 `THIRD_PARTY_NOTICES.md`。
