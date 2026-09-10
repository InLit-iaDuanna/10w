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

## 2026-09-07 审计修复

权限 ID 支持冒号分隔的多级作用域（例如 `logic:code:approve`）；注册器保留原始字符串，实际权限检查仍精确匹配，不引入通配授权。Asset Factory 的发布入口使用 `asset.pipeline.publish`，Asset Library 保持 `asset.version.publish`，避免两个不同模块重复注册同一命令。

历史事件 schema 文件名保持可访问。规范事件文件可通过本地 `$ref` 引用原合同，共用事件包另外限制 `event_type`；不复制或放宽 payload 校验。角色与概念模块的生成器同时输出事件类型与版本元数据。

Python 边界检查忽略 setuptools 的 `backend/build` 副本，继续扫描真实源码与测试。JavaScript 的对象方法 `client.import(...)` 不属于动态模块导入；真实计算目标 `import(modulePath)` 仍被拒绝。

后端生成目录的每项是 `{manifest, module}`：manifest 来自已验证 YAML，module 是该 manifest 声明的公开 Python 包，使用静态 import 绑定。模块现有路由工厂与构造参数各异，当前 `services/api/app.py` 仍负责依赖注入及路由装配；生成目录不虚构通用 `backend_module_contribution` 导出，也不表示所有业务路由已自动挂载。

前端生成目录显式绑定 `{...moduleContribution, manifest: generatedModuleManifest}`，所有模块启停及入口判断只消费 YAML 生成的完整合同；历史模块自身的简写 UI manifest 不作为目录合同。统一宿主仅注册一次 `harness.pipeline`，使用模块公开 editor 定义并保留原有项目选择、脏状态和生产视图包装。
