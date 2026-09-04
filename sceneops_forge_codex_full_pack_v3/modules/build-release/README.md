# Build and Release

Build and Release 把 Unity 构建产物、版本上下文、门禁证据、审批与 ChangeSet 串成可追溯
的 Release Candidate，并负责本地/Judge 发布记录、补丁说明和追加式回滚。模块不会执行
Unity 构建或 Git 变更；这些能力只能通过 typed public contracts 输入。

## 用户与问题

面向制作人、QA、发布负责人和 Unity 工程师，解决以下问题：

- Development、QA、Judge、Release Candidate 配置如何形成确定性的 Build Matrix；
- Build A/B 是否拥有相同输入，并是否真的产生相同输出 bytes；
- 资产、场景、代码、渲染、Unity 测试、性能、AI 回归是否全部通过；
- 一个候选由哪个 commit、模块目录、Project Bible、资产/场景版本、Unity 环境和测试产生；
- 谁批准了候选、部署、known-good 标记与 rollback；
- 发布失败如何重试，当前版本如何回到上一 verified known-good candidate；
- 补丁说明如何只描述真正批准并随候选交付的 ChangeSet。

## 所有权

模块拥有 `BuildMatrix`、`BuildRun`、`BuildManifest`、`ReleaseGate`、
`ReleaseCandidate`、`Deployment`、`PatchNote`、`FeedbackLink` 和 `RollbackPlan`。

不拥有：Unity 构建执行、Git clean attestation、ChangeSet 审批系统、跨模块门禁生产者、
artifact-store、Shell/Dockview 和全局 event envelope。

## 编辑器

| ID | 中文标题 | 可见状态 |
|---|---|---|
| `build.matrix` | 构建矩阵 | 四 profile、A/B、source、manifest、mode |
| `build.console` | 构建控制台 | attempts、日志、失败、重试、断连 |
| `release.gates` | 发布门禁 | 七类门禁、evidence、stale/missing/corrupt |
| `release.center` | 发布中心 | 候选、精确审批、部署历史、known-good、rollback |
| `release.patch-notes` | 补丁说明 | ChangeSet anchors、人工修订、revision |

编辑器区分 `loading / empty / ready / failed / offline / permission_denied` view state，
并独立显示 `live / cached / mock / planned / blocked` execution mode。它们全部 lazy-load，
只序列化 ID、筛选器、展开项、tab 与 follow-tail 等本地展示状态。

## 命令与事件

模块公开十个命令：

```text
build.matrix.create
build.manifest.record
release.candidate.create
release.candidate.approve
release.patch-note.generate
release.patch-note.edit
release.deploy
release.deploy.retry
release.rollback.plan
release.rollback.execute
```

按钮、聊天、菜单与 workflow 必须调用同一命令 ID。部署和回滚命令要求 typed adapter、
精确 scope approval 和当前状态复验。事件 payload 合同见
[`docs/api-events.md`](docs/api-events.md)；event transport 尚未接线。

## 核心行为

### Reproducibility

BuildManifest 的 canonical SHA-256 保护发布清单完整性。输入 fingerprint 包含 commit、
完整 matrix target definition、producer mode、module catalog、Project Bible、asset versions、
scene snapshots、Unity/packages、recipe、settings 与 test evidence；输出 fingerprint 比较
产物类型、版本、mode、prior-live 绑定、bytes checksum 与大小，不会把 run ID 或 URI 当成
可复现证据。Manifest、BuildRun 和所有 artifact/evidence 的 run identity 与 mode 必须一致。
候选至少需要两个不同 manifest。

SHA-256 仅用于规格明确要求的 artifact/manifest 完整性边界：稳定 ID、Git commit 和普通
类型无法检测 artifact bytes 被替换或 evidence 变 stale。

### Gates

七类门禁全部 required 且默认 blocking。缺失、重复冲突、失败、blocked、planned、
commit/build 不匹配、跨项目 evidence、artifact 缺失或 checksum/size 不符都会阻断。
Gate evidence 必须逐字段等于 immutable BuildManifest 中已记录的 evidence，不能在候选阶段
注入新的“通过”结果。
Release Candidate profile 只接受 `live` source；Judge 接受 `live` 或带 prior-live provenance
的 `cached` source；Development/QA 可使用明确标记的 deterministic mock。

### Approvals

审批记录绑定 action、target ID、role 与 SHA-256 scope fingerprint。候选、部署、
known-good 和 rollback 是不同 action；任何 candidate、gate evaluation、patch-note revision、
target、base deployment 或 idempotency 输入变化都会产生不同 scope。
部署与回滚 scope 还绑定 patch-note content checksum、adapter ID/version、dry-run destination
及预览证据。`ReleaseAuthority` 是 Git/provenance 与人类审批的可信边界；没有该实现时，
`live`/`cached` source intake 和 live adapter mutation 均 fail closed。

### Deployment and rollback

部署先 dry-run，再执行 staging → checksum verify → atomic activation。每次失败和重试都
追加 attempt；同 idempotency key/相同输入可安全重放，不同输入冲突。Rollback Plan 在
同一项目/游戏/target/profile/build target 中选择最近的 earlier known-good deployment，
复验 artifact，执行时 compare-and-swap active deployment，并追加一条 activation；不会
删除历史或执行 source reset。

本地适配器按 target/project/game/build-target 分区物理 active pointer，并为每个 operation
保留不可变 receipt；较旧 operation 的重放只 reconcile，不会重新激活并覆盖更新版本。
内存仓库在调用适配器前锁定 deployment ID/idempotency key，并将相关领域记录一次提交。

Patch Note 保存初始内容、每次完整编辑快照和 content checksum。部署审批绑定该 checksum；
通过审批后 note 标记为 `approved`，后续再编辑会创建新 revision 并回到 `draft`。

## 适配器

- `StaticArtifactCatalog`：确定性 fixture catalog，结果必须保持 `mock`；
- `FileArtifactCatalog`：在配置根目录中验证真实文件 bytes/size；
- `DeterministicMockDeploymentAdapter`：可配置失败次数的 mock 部署/回滚；
- `LocalFileDeploymentAdapter`：支持 local/Judge 固定目标的安全原子文件激活。

前端不直接调用 Git、Unity、文件系统或 adapter。详细安全边界见
[`adapters/README.md`](adapters/README.md)。

## Fixtures 与示例游戏

- `fixtures/remember-home/release-scenario.json`
- `fixtures/warehouse-escape/release-scenario.json`

两者使用同一平台实现、不同 project/game/build/candidate/deployment IDs，并在 E2E 中验证
隔离。fixture 是 `mock`。因为仓库没有先前 live Unity run，两者的 cached Judge 期望均
明确为 `blocked`，没有把新造文件冒充历史真实缓存。

## Setup 与测试

当前环境已有 Python 3.9、Pydantic、FastAPI 和 PyYAML，可直接运行：

```bash
cd sceneops_forge_codex_full_pack_v3

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=modules/build-release/backend/src:modules/build-release/backend/tests \
python3 -m unittest discover \
  -s modules/build-release/backend/tests -p 'test_*.py' -v

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=modules/build-release/backend/src:modules/build-release/backend/tests \
python3 -m unittest discover \
  -s modules/build-release/e2e -p 'test_*.py' -v

node --experimental-strip-types --test \
  modules/build-release/frontend/src/tests/*.test.ts
```

重新生成合同：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=modules/build-release/backend/src \
python3 modules/build-release/backend/scripts/export_contracts.py
```

## 当前执行状态

| 状态 | 范围 |
|---|---|
| Live | `LocalFileDeploymentAdapter` 可在受控临时根目录实际复制、复验并原子激活 bytes；service 未配置可信 authority 时会阻断 live mutation，不是生产发布 |
| Mock | 后端完整领域流、failure/retry、两个游戏 QA candidate/Judge mock deployment、前端状态模型 |
| Cached | 无。仓库没有可验证的 prior-live provenance |
| Planned | module-runtime catalog、生成 TypeScript client、TanStack Query/SSE、正式 event transport、数据库 persistence |
| Blocked | live Unity builds、权威 Git clean attestation、真实人类 approvals、生产/Judge deployment、cached Judge replay、真实两个游戏 Release Candidate |

## 已知限制

- 根 `STATUS.md` 与 `EXECUTION_PLAN.md` 在任务起点不存在，本模块未越权创建 bootstrap 文件。
- core-kernel/module-runtime/engine-unity/version-collaboration/artifact-store/examples/apps 均不存在；
  因此 module-local records 需要主集成任务替换/适配为正式公共合同。
- React/toolchain 未安装，当前验证覆盖 contribution metadata、state/view models 与 command
  availability；真实 React、Dockview、TanStack Query 与浏览器 E2E 为 Blocked。
- In-memory repository 只用于独立测试；它提供进程内 operation 锁和原子领域提交，但不宣称
  durable、multi-process safe 或能让外部文件激活与数据库形成分布式事务。
- `source_dirty` 只是 release record 的一个字段；live/cached intake 还必须由正式
  `ReleaseAuthority` 验证 Git attestation，调用方自报布尔值不能解锁 live 路径。

集成顺序见 [`docs/integration.md`](docs/integration.md)，操作语义见
[`docs/release-operations.md`](docs/release-operations.md)。

## 2026-09-05 独立 Web 组合更新

已新增可运行入口 `apps/labs/unity-build`，React 19 / TanStack Query / 生成的 OpenAPI client 已接通。
公开后端新增 `UnityBuildWorkbenchService`、`create_workbench_router`，公开前端新增 `UnityBuildWorkbench`。
组合服务调用原 BuildReleaseService 进行 mock manifest 入库和候选分析，并通过 engine-unity 公共服务进行本地 ChangeSet 预览；本地草稿使用 SQLite revision 事务保存。
原有发布/审批/来源安全规则不变；入口不注册执行/部署/审批路由。旧“编辑器无可运行环境”描述已由此入口取代；真实外部链路仍 blocked。
启动、接口、mock 局限与本轮精确烟测见 [工作台说明](../../apps/labs/unity-build/README.md)。
完整旧套件本轮 **not run / pending approval**。调用工作台后端时需同时将 `modules/engine-unity/backend/src` 加入 Python 路径（独立入口已负责）。
