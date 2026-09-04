# 集成说明

## Backend composition

```python
from version_collaboration import (
    GitCliAdapter,
    SqliteReviewRepository,
    VersionCollaborationService,
    create_router,
    version_collaboration_exception_handler,
)
```

Composition root 负责从可信项目 registry 解析 `project_id -> Path`，并把相同 paths 传给 `GitCliAdapter` allowlist。HTTP body 不包含 project path、argv 或 shell text。

`ChangeSetGateway` 与 `ApprovalVerifier` 是端口，不是本模块复制的 core entities：

- gateway 创建带 base、previous/proposed values、risk、validation、rollback 和 approval requirements 的 ChangeSet；
- verifier 对 `review_revision_id + diff_bundle_id + subject_id/version + base_version` 做精确验证；
- 未配置端口必须使用 `UnavailableChangeSetGateway` / `UnavailableApprovalVerifier`，并返回 blocked，而不是测试 fake。

Authenticated context 必须提供权限。后端会再次检查：

```text
review:read
review:create
review:comment
review:assign
review:approve
version:lock
version:rollback
```

## Producer integration

其他模块只提供版本化 snapshots 或 stable IDs：

- world/Unity provider → `SemanticEntity[]`；
- render provider → fixed-camera `VisualCapture`；
- ai-playtest provider → `BehaviorSnapshot`；
- build-release → `review.release.link`，保存 reciprocal approved subject ID。

本模块不读取 producer 的 repository、ORM 或 internal files。缺少输入时对应层为 `unavailable/planned`。

## Frontend composition

从 `frontend/src/index.ts` 注册 `moduleContribution`。`review` workspace 是 opt-in：

```text
review.version-diff   center
review.session        right split
review.activity       bottom split
```

编辑器只通过 `VersionCollaborationApi` 和 TanStack Query 读取 server state；mutation 通过 command registry。Shell 负责 Dockview、权限 gate、feature flag、generated client 实例和 context binding。模块 CSS 只消费全局 design tokens。

Pinned editor state 保存 project/review/revision IDs，不保存 server entities、client 或 React objects，因此两个 diff editor 可以分别固定到不同 review revision。固定状态使用 `/reviews/{review_id}/revisions/{review_revision_id}` 及其 summary 端点；离线时，已经载入的 sealed review diff 仍可阅读，只有需要 Git/LFS 的新操作会阻断。

创建首个 revision 时省略 `review_id` 和 `expected_previous_revision_id`。发布同一 session 的下一 revision 时两个字段必须同时提供，并指向服务端当前 revision；否则以 `STALE_BASE` 拒绝，避免并发作者覆盖彼此。

## Rollback sequence

```text
review.rollback.propose
  -> Git dry-run at exact current head
  -> verify binary LFS locks
  -> core ChangeSetGateway.create
  -> immutable proposal + activity

review.rollback.execute
  -> backend permission check
  -> reject a proposal from a superseded review revision
  -> core ApprovalVerifier exact binding
  -> verify locks again
  -> Git adapter rechecks exact head/dirty/conflict
  -> create a forward commit from the approved target tree
  -> atomically update HEAD with expected old OID
  -> synchronize index/worktree to the new commit
  -> verify idempotent retries by trailers + parent + tree + current HEAD/clean worktree
  -> append execution + ChangeSet history + activity
```

不使用 silent reset。若 execute 前 base 改变，旧审批不会被沿用。若仓库启用提交签名或可执行 commit hooks，adapter 会阻断，而不会通过底层 `commit-tree` 悄悄绕过安全策略。

## Git LFS lock consistency

active lock 是远端 Git LFS lock 的本地投影。读取、同一 owner 的幂等 acquire 以及 destructive unlock 前都会用精确 path 查询远端并匹配外部 ID；远端 acquire 成功但本地落库失败时会 unlock 补偿，远端 release 成功但本地更新失败时会尝试重新 lock 并替换本地投影。补偿不能确认时返回 `LOCK_RECONCILIATION_REQUIRED`，不会宣称成功。

## Event delivery boundary

`VersionCollaborationService` 强制要求 `EventPublisher`，避免静默丢弃事件。当前 repository 与 event bus 之间还没有共享事务/outbox；生产 composition root 应提供可重试的 durable publisher 或在 core 层补齐事务型 outbox。

## Generated contracts

修改 Pydantic API 后运行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend/src python3 backend/scripts/generate_contracts.py
```

CI 使用 `--check` 检测 `contracts/openapi.json` 和 `frontend/src/generated/api-types.ts` 是否过期。
