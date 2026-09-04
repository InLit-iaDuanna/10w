# Module Runtime

Module Runtime 在构建期发现 `modules/*/module.yaml`，执行 schema、入口、依赖图、贡献 ID、事件版本和跨模块 import 边界校验，然后确定性生成前后端静态目录。它不会在应用运行时发现或执行任意插件代码。

## 公共表面

- Command: `module.catalog.inspect`
- Event: `module.catalog.generated@1`
- Job: `module.catalog.build`
- Python: `module_runtime`
- TypeScript: `frontend/src/index.ts`

## 命令

```bash
scripts/module-validate
scripts/module-generate
scripts/module-generate --check
scripts/module-scaffold example-module \
  --title "Example Module" \
  --description "One coherent capability."
scripts/module-test module-runtime
```

脚手架可用 `--surface frontend|backend|both` 仅创建需要的表面；若目标目录已存在会失败，不覆盖用户文件。

## 校验内容

- 重复 module/feature-flag/editor/command/job/workflow/policy-gate/event ID；
- 缺失前端文件或后端 package 入口；
- 缺失依赖、依赖环、core 反向依赖；
- permission、feature flag、贡献 ID 与事件版本格式；
- 缺失或元数据不一致的 event payload schema；
- 未声明的跨模块 import 和绕过公开入口的 internal import；
- 非静态 Python/TypeScript import 目标。

## 启停与缺失集成

前后端 resolver 都按生成目录的依赖顺序计算：

- feature flag 为 false：`disabled`；
- 必需集成缺失或依赖不可用：`blocked`；
- 仅可选集成缺失：保持 `enabled` 并返回明确降级元数据；
- 未知 feature flag：失败，避免拼写错误被静默忽略。

## 生成文件

- `contracts/module-manifest.schema.json`
- `frontend/src/generated/module-manifest.ts`
- `backend/src/module_runtime/generated_manifest.py`
- 每个已注册模块自己的 generated manifest
- `apps/web/src/registries/generated-module-catalog.ts`
- `services/api/generated_module_catalog.py`
- `generated/module-catalog.json`
- `docs/module-map.md`

## 执行真实性

生成与校验是当前主机上的真实本地执行（Live）。`contracts/examples` 中的输入以及 `runtime-fixture` 输出是确定性 Mock。没有 Cached 结果；缺少外部集成时 resolver 返回 Blocked，而不是伪造成功。

## 限制

当前 import 边界覆盖 Python AST 与 TypeScript/JavaScript 静态 import 语法，不解析编译器 path alias 配置；跨模块推荐使用 `@sceneops/<module-id>` 或指向公开 index 的相对路径。
