# Build Release Adapters

模块服务只接收 `ArtifactCatalog` 与 `DeploymentAdapter` typed ports。适配器实现位于
`backend/src/build_release/adapters.py`，不会接收 shell 命令、可执行文件、工作目录、
环境变量或任意目标路径。

`LocalFileDeploymentAdapter` 支持：

- capability report 与 health check；
- dry-run 目标预览；
- 取消检查和结构化进度；
- 源产物 SHA-256 与大小校验；
- 受配置根目录约束的相对路径；
- symlink、hardlink、绝对路径与 `..` 穿越拒绝；
- 暂存、复验、原子激活和可重放收据；
- target/project/game/build-target 物理命名空间；
- 每个 operation 的持久 receipt 与完整 immutable-input reconcile；
- 以新激活记录实现 rollback，不删除历史。

`DeterministicMockDeploymentAdapter` 只用于 fixture 和测试，并始终返回 `mock`。
它支持确定性的失败次数，用于验证重试和追加式 attempt 历史。

真实 Judge/生产目标必须由 composition root 注入固定根目录和真实 artifact-store，
并完成 `ReleaseAuthority`、权限、持久化与活动部署协调。模块默认 authority 会阻断 live
service mutation。当前仓库没有这些上游实现，因此不得把临时目录验证描述为生产 live 发布。
