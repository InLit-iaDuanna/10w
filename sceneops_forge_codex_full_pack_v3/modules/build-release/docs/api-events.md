# Build Release API 与事件

公开 OpenAPI 位于 `contracts/openapi/build-release.openapi.json`，由 Pydantic/FastAPI
生成。主要端点：

- `POST /build-release/builds`
- `POST /build-release/candidates`
- `POST /build-release/candidates/{candidate_id}/approvals`
- `POST/PATCH /build-release/patch-notes`
- `POST /build-release/deployments/prepare`
- `POST /build-release/deployments`
- `POST /build-release/deployments/{deployment_id}/retry`
- `POST /build-release/rollback-plans`
- `POST /build-release/rollback-plans/{plan_id}/execute`
- `POST /build-release/feedback-links`

版本化 event payload JSON Schemas 位于 `contracts/events/`。core-kernel 拥有 envelope；
本模块只拥有 payload：

- `build.manifest.recorded@1`
- `release.candidate.created@1`
- `release.candidate.readied@1`
- `release.deployment.succeeded@1`
- `release.deployment.failed@1`
- `release.rollback.executed@1`

当前仓库没有共享 event transport，因此 service 尚不发布这些事件；catalog/transport
接线为 Planned。不能把 schema 存在描述为事件已经 live 发出。
