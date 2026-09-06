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

## 版本树只读 API

- `GET /api/version-collaboration/tree`：宿主根据 `X-SceneOps-Project` 绑定项目目录；返回 GitRepositoryState 字段及可空 `progress`。GitCommit 新增兼容性默认字段 `parent_ids`，提交按 child-before-parent 拓扑顺序返回，UI 从上到下反向绘制。最多 200 个提交，分支读取本地 refs/heads；`--all` 同时纳入其他本地已有引用可达的历史，不进行远端 fetch。
- `GET /api/version-collaboration/tree/commits/{commit_id}/files`：返回结构化变更文件；合并提交相对第一父提交，初始提交返回新增文件。
- `POST /api/version-collaboration/tree/branches/preview`：生成创建或切换本地分支的 typed BranchChangeSet dry-run，包含预期 HEAD、起点和结构化阻塞原因。
- `POST /api/version-collaboration/tree/branches/apply`：只接受刚刚预览且显式确认的完整 ChangeSet；重新检查仓库状态一致后执行 `git switch -c` 或 `git switch`。不提供删除、远端 push 或 merge。
- progress 仅反映策划服务现有事实，不表示生产验收完成率。不存在可读取仓库时返回 409 及中文说明。
