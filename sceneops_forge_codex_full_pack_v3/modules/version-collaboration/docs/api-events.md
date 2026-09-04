# API 与事件

完整 OpenAPI：`../contracts/openapi.json`。

## API groups

```text
GET  /api/version-collaboration/projects/{project_id}/git
POST /api/version-collaboration/reviews
GET  /api/version-collaboration/reviews/{review_id}
GET  /api/version-collaboration/reviews/{review_id}/revisions/{review_revision_id}
GET  /api/version-collaboration/reviews/{review_id}/summary
GET  /api/version-collaboration/reviews/{review_id}/revisions/{review_revision_id}/summary
GET  /api/version-collaboration/reviews/{review_id}/activity
GET  /api/version-collaboration/reviews/{review_id}/comments
POST /api/version-collaboration/reviews/{review_id}/comments
GET  /api/version-collaboration/reviews/{review_id}/assignments
POST /api/version-collaboration/reviews/{review_id}/assignments
GET  /api/version-collaboration/reviews/{review_id}/decisions
POST /api/version-collaboration/reviews/{review_id}/decisions
GET  /api/version-collaboration/reviews/{review_id}/approvals
POST /api/version-collaboration/reviews/{review_id}/approvals
GET  /api/version-collaboration/reviews/{review_id}/release-links
GET  /api/version-collaboration/projects/{project_id}/locks
POST /api/version-collaboration/locks/acquire
POST /api/version-collaboration/locks/release
POST /api/version-collaboration/rollbacks/propose
POST /api/version-collaboration/rollbacks/execute
POST /api/version-collaboration/release-links
```

Errors use the standard structured shape：

```json
{
  "code": "STALE_BASE",
  "message": "The reviewed base changed; re-plan and re-approve the action.",
  "details": {"expected_commit": "...", "actual_commit": "..."},
  "request_id": "request_...",
  "retryable": false,
  "suggested_actions": ["version.status.refresh", "review.session.create"]
}
```

## Event envelope

事件 schema：`../contracts/events/review-events.v1.schema.json`。

`event_type` 不带版本后缀，`event_version` 为 `1`。每个事件含 UTC timestamp、project、correlation/causation IDs、actor、mode 和 stable subject IDs。Publisher consumer 必须用 `event_id` 幂等处理。

Approval event 表示“core ApprovalVerifier 已验证并被本模块观察到”，不是本模块自行签发通用 Approval。Release link event 表示稳定 ID 链接已记录；release 的创建和有效性仍由 `build-release` 所有。
