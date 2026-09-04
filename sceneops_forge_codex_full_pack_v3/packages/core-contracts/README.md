# Core Contracts

SceneOps Forge 的跨模块、版本化核心合同。这里仅包含稳定 ID、执行真实性、错误、Actor、Artifact/Provenance、命令/事件信封、ChangeSet/审批、Job/Run 与 `WorkbenchContext`；领域实体留在各自模块。

Python Pydantic 模型是合同源。`tools/generate.py` 由这些模型生成 JSON Schema 和 TypeScript 声明，生成文件不得手改。

## 公共入口

- Python: `sceneops_core_contracts`
- TypeScript: `frontend/src/index.ts`
- JSON Schema: `schemas/v1/*.schema.json`

## 约束

- 时间戳必须为 UTC。
- 稳定 ID 必须使用声明的类型前缀。
- 所有执行结果显式标记 `live`、`cached`、`mock`、`planned` 或 `blocked`。
- Cached provenance 必须引用真实来源 Run；Mock provenance 必须引用 fixture。
- ChangeSet 必须支持 dry-run；破坏性及场景以上范围的修改必须声明审批要求。
- 合同只声明 SHA-256 checksum 的表示形式，不负责计算 checksum。

## 测试

```bash
scripts/module-test core-contracts
```
