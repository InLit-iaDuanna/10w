# 发布与回滚操作

## 创建候选

1. engine-unity 产生两次独立 BuildRun（A/B）。
2. `build.manifest.record` 验证完整清单和所有 artifact/evidence。
3. `release.candidate.create` 比较输入与输出 fingerprints，聚合七类阻断门禁。
4. 若门禁失败、缺失、冲突、stale、corrupt 或 mode 不适合 profile，候选进入
   `blocked`，不会等待“自动恢复”。
5. 若需要人审，候选返回 `scope_fingerprint`；审批必须绑定 candidate ID、action、
   role 与该 fingerprint。

## Patch notes

Patch Note 只接受 candidate 中列出的、同项目/游戏/commit、已经批准且带 approval ID
的 ChangeSet。生成顺序按 ChangeSet ID 确定。人工可重排、改写或删除条目，每次编辑
递增 revision 并保存完整内容快照与 checksum；不能创建无 ChangeSet anchor 的变更声明，
也不能修改批准 provenance。部署审批绑定 revision 和 content checksum；审批后状态为
`approved`，再次编辑会产生新 draft revision。

## Deployment

1. 先调用 `/deployments/prepare` 获取目标、当前 base deployment、精确 operation scope
   、adapter ID/version、patch-note checksum、dry-run destination 和所需角色。
2. 人类分别批准 `deploy`；若设置 known-good，还要单独批准
   `mark_known_good`。
3. `/deployments` 重算 scope、复验门禁/产物/patch-note revision，再调用 typed adapter。
4. 失败会保留结构化错误、日志和 attempt；`/retry` 只接受同一 immutable operation。
5. 同 idempotency key 与相同输入返回原记录；不同输入返回 conflict。
6. target/project/game/build target 各自拥有独立 active pointer；每个 operation receipt
   可在较新部署后继续做幂等 reconcile。

## Rollback

Rollback Plan 只从相同 project、game、target、profile 与 build target 的较早、成功、
known-good 部署中选择，且产物仍需通过完整性校验。执行前 compare-and-swap 当前 active
deployment。Rollback 使用独立审批并追加新的 activation Deployment；不会运行
`git reset`、删除候选或重写历史。

Live 执行还要求可信 `ReleaseAuthority` 复验 source attestation 与每一条 approval；默认
未配置状态会明确阻断，不接受 request body 自报的 clean/role/decision 作为生产权限。

## 执行模式

| Mode | 含义 |
|---|---|
| live | adapter 此次真实执行；产物自身 mode 另行记录 |
| cached | 来自带 prior-live provenance 的历史真实产物 |
| mock | 确定性 fixture/adapter，仅用于本地验证 |
| planned | 已定义但尚未执行，不产生成功 artifact |
| blocked | 因缺少合同、集成、审批或证据无法执行 |
