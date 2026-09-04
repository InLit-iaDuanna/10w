# 核心合同 v1

`packages/core-contracts/src/sceneops_core_contracts` 中的 Pydantic 模型是核心合同源；JSON Schema 与 TypeScript 类型由 `packages/core-contracts/tools/generate.py` 确定性生成。核心合同仅包含跨模块原语，领域模型不得加入这里。

## 稳定 ID

| 类型 | 前缀 | 用途 |
|---|---|---|
| User / Agent / Service / System | `usr_` / `agt_` / `svc_` / `sys_` | Actor identity |
| Project / Branch / Scene / Scene Object | `prj_` / `brn_` / `scn_` / `sobj_` | 工程与 3D identity |
| Asset / Asset Version | `ast_` / `aver_` | 资产与发布版本 |
| Build / Run / Issue | `bld_` / `run_` / `iss_` | 生产执行 |
| ChangeSet / Approval / Artifact | `chg_` / `apr_` / `art_` | 修改、审批与产物 |
| Event / Command / Correlation | `evt_` / `cmd_` / `corr_` | 消息链路 |
| Feature / Task / Render Job / Playtest Run | `fea_` / `tsk_` / `rjob_` / `prun_` | WorkbenchContext |

名称、路径、数组索引和层级路径不是 identity。`sceneops_id` 对应 `SceneObjectId`。

## 执行真实性

| Mode | 合同含义 |
|---|---|
| `live` | 当前请求真实执行 |
| `cached` | 复用历史真实 Run；Provenance 必须包含 `cached_from_run_id` |
| `mock` | 确定性 fixture；Provenance 必须包含 `fixture_id` |
| `planned` | 尚未执行 |
| `blocked` | 无法执行；Run 必须包含结构化错误 |

## 命令与事件

`CommandEnvelope` 与 `EventEnvelope` 都包含稳定 ID、版本、UTC 时间、correlation、Actor、mode 与 JSON payload。Event 额外包含可选 causation command。领域 payload schema 由生产它的模块拥有。

标准错误码为 `INVALID_ARGUMENT`、`NOT_FOUND`、`CONFLICT`、`PERMISSION_DENIED`、`PRECONDITION_FAILED`、`APPROVAL_REQUIRED`、`INTEGRATION_OFFLINE`、`TIMEOUT`、`CANCELLED`、`UNAVAILABLE` 与 `INTERNAL`。模块可增加稳定的大写领域错误码；UI 依赖 code 与结构化 details，不解析 message。

事件引用和发布后兼容规则位于 `packages/core-events`：同一版本不可改动；schema 变化必须使用连续的下一个版本。

## ChangeSet 与审批

ChangeSet 必须记录 base version、目标模块/集成/对象、前后值、理由、预期结果、影响范围、风险、验证与回滚计划。`dry_run_supported` 固定为 true。破坏性修改及 scene/project/repository/release 范围修改必须声明审批要求。

这些合同不执行变更；执行权仍属于经 allowlist 的 typed adapter。

## Artifact 与 Provenance

Provenance 包含源项目/版本、相关 `sceneops_id`、生产模块、工具与 adapter/recipe 版本、Actor、mode、UTC 时间、checksum 表示及审批状态。AI 产物另外记录 provider/model、workflow checksum、prompt、seed 与参数。

核心包只校验 `sha256:<64 lowercase hex>` 的合同表示，不实现 checksum 计算。

## 生成与验证

```bash
python3 packages/core-contracts/tools/generate.py
python3 packages/core-contracts/tools/generate.py --check
scripts/module-test core-contracts
```

Breaking change 必须创建新的合同版本；不得就地修改已发布 v1 的语义。
