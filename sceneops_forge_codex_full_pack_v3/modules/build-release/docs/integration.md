# Build Release 集成合同

## 上游输入

本模块不执行 Unity 构建，也不读取其他模块内部文件。集成层需要把以下信息转换为
`build_release` 的公开 Pydantic records：

| 来源 | 所需公开信息 | 当前状态 |
|---|---|---|
| core-kernel | 稳定 ID、ExecutionMode、Artifact/Provenance、错误与事件 envelope | Planned：核心模块缺失 |
| engine-unity | Unity player artifact、版本、packages、settings、BuildRun 结果 | Blocked：模块缺失 |
| version-collaboration | Git commit/clean attestation、批准的 ChangeSet、精确作用域审批 | Blocked：模块缺失 |
| asset/render/world/playtest | 七类门禁的 typed evidence IDs 与 checksums | Blocked：模块缺失 |
| artifact-store | 产物存在性、大小、SHA-256 与受控 URI | Planned：typed port 已定义 |
| module-runtime | manifest 校验、feature flag、前后端 catalog 注册 | Planned：运行时缺失 |

缺失的 core 公共合同没有在根目录中被修改。本模块使用窄的 module-local records 继续
实现并测试；主集成任务应以正式 core 类型替换这些边界，而不是让另一模块导入
`repository.py`、`adapters.py` 或其他内部文件。

## Source identity

`source_commit` 是 Git object ID，`source_identity` 同时声明算法；它与 artifact 的
SHA-256 不是同一种标识。Release Candidate 创建时校验 clean flag、项目/游戏/target、
两次构建输入 fingerprint、输出 fingerprint 和全部证据。部署前再次检查 manifest、
门禁与产物，避免审批之后的产物漂移。

真实 Git clean attestation 必须由 version-collaboration 的 allowlisted typed adapter
通过 `ReleaseAuthority.verify_source` 提供；人类审批同样必须通过
`ReleaseAuthority.verify_approval` 对照权威记录。默认 authority fail closed，当前模块
不能仅凭调用方布尔值、role 或 decision 证明其真实有效，因此生产集成仍为 Blocked。

## Cached Judge contract

`cached` artifact 必须包含 `origin_live_run_id` 与 `origin_live_artifact_id`；catalog 必须
解析该 ID，证明 origin 是同 project/game/type/version/commit/checksum/size 的 `live` record，
然后再复验 cached bytes。`FileArtifactCatalog` 单独无法证明历史 provenance，因此对 cached
fail closed。仓库目前没有任何历史 live run，所以两个示例
fixture 都把 cached Judge 场景记录为 `blocked`；它们没有伪造 cached 文件。

## Deployment persistence

模块内存仓库会在外部 mutation 前检查并锁定 deployment ID/idempotency key，且把 deployment、
candidate 与 rollback 状态一次提交。生产仓库必须实现相同唯一约束、事务和 receipt/outbox
恢复语义；进程内实现不能替代数据库事务，也不能把文件系统和数据库变成单一原子事务。

## Frontend

`frontend/src/index.ts` 只导出 `moduleContribution`。五个编辑器延迟加载；编辑器级集成
全部 optional，以便离线检查历史。写命令单独检查权限和 artifact-store。待 core 与
shell 出现后：

1. 从 `contracts/openapi/build-release.openapi.json` 生成 TypeScript client；
2. 用正式 `ModuleContribution`、EditorDefinition 与 CommandDefinition 类型验证贡献；
3. 通过生成 catalog 注册，不在 shell 写条件分支；
4. 通过 TanStack Query 和共享事件 transport 读取服务状态；
5. 增加 React Testing Library 与 Dockview 集成 E2E。
