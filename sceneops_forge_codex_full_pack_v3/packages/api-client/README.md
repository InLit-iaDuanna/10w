# Shared local API client

`@sceneops/api-client` 提供统一 JSON 请求、已编码二进制上传、AbortSignal、超时和可见错误处理。功能模块使用自身 OpenAPI 生成类型声明请求/响应，组件只调用模块公开服务或 TanStack Query hook。二进制调用只负责传递模块已校验的 `BodyInit` 和显式 Content-Type，不把文件转成 JSON。当前 Shell 通过同源 `/api` 代理连接 localhost API；不向浏览器暴露 CLI、文件系统或宿主凭据。
