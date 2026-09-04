# 模块运行时 v1

SceneOps Forge 使用构建期静态模块注册：

```text
modules/*/module.yaml
  -> Pydantic/schema validation
  -> entrypoint + event schema validation
  -> dependency graph + import boundary validation
  -> deterministic frontend/backend catalogs
  -> composition roots
```

模块 manifest 本身不执行代码；不存在运行时目录扫描或任意插件加载。

## Manifest source

- Pydantic source: `modules/module-runtime/backend/src/module_runtime/manifest.py`
- Generated JSON Schema: `modules/module-runtime/contracts/module-manifest.schema.json`
- Deterministic valid/invalid fixtures: `modules/module-runtime/contracts/examples/`

每个 manifest v1 必须声明所有顶层字段、三个 requires 列表、六个 contributes 列表、permissions 与至少一个公开 entrypoint。目录名必须等于 module ID。

Event contribution 使用 `dotted.event.name@version`。每个版本在模块的 `contracts/events/` 中提供 `<event-type>.v<version>.schema.json`，并声明匹配的 `x-event-type` 与 `x-event-version`。

## Diagnostics

主要失败码：

- `MANIFEST_SCHEMA_INVALID`
- `DUPLICATE_MODULE_ID` / `DUPLICATE_FEATURE_FLAG`
- `DUPLICATE_EDITOR_ID` / `DUPLICATE_COMMAND_ID` / `DUPLICATE_JOB_ID`
- `ENTRYPOINT_MISSING` / `ENTRYPOINT_OUTSIDE_MODULE`
- `MODULE_DEPENDENCY_MISSING` / `MODULE_DEPENDENCY_CYCLE`
- `UNDECLARED_MODULE_IMPORT` / `INTERNAL_MODULE_IMPORT`
- `NON_STATIC_IMPORT_FORBIDDEN`
- `EVENT_SCHEMA_MISSING` / `EVENT_VERSION_INVALID`

诊断包含 owner module 与 repository-relative path，可直接用于 CI 输出。

## Public boundaries

- Frontend: another module may import only `frontend/src/index.ts` or `@sceneops/<module-id>`.
- Backend: another module may import only the package named by `entrypoints.backend`；子模块是 internal。
- 跨模块 import 必须同时在 `requires.modules` 声明。
- Core modules 不得依赖 feature modules。

## Enablement and integrations

Resolver 以生成目录的依赖顺序计算模块状态。Feature flag false 返回 `disabled`；必需集成缺失或依赖未启用返回 `blocked`；可选集成缺失保持 `enabled` 并返回缺失列表与用户可见说明。未知 feature flag 直接失败。

## Generated consumers

- Web: `apps/web/src/registries/generated-module-catalog.ts`
- API: `services/api/generated_module_catalog.py`
- Tooling/inspection: `generated/module-catalog.json`
- Docs: `docs/module-map.md`

前后端组合根消费生成目录，不维护 feature switch 或 module import switch statement。

## Commands

```bash
scripts/module-validate
scripts/module-generate
scripts/module-generate --check
scripts/module-scaffold my-module --title "My Module" --description "..."
scripts/module-test my-module
scripts/module-test all
```

脚手架拒绝覆盖已有目录，并可用 `--surface` 只生成 frontend、backend 或二者。新模块的 fixture runner 明确返回 Mock success，或抛出稳定 Mock failure。
