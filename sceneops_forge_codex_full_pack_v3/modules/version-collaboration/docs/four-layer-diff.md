# 四层差异合同

每个 `FourLayerDiff` 是 sealed bundle，绑定精确的 base/target `VersionReference`、`diff_bundle_id`、UTC `sealed_at` 和 execution mode。重新计算产生新 bundle，不更新旧结果。

## 状态语义

| State | 含义 |
|---|---|
| `succeeded` | 层已执行并发现变化 |
| `empty` | 层已执行，兼容输入之间没有变化 |
| `unavailable` | 缺少 producer 或输入；不是空差异 |
| `incompatible` | capture/schema/test descriptor 不可比较 |
| `failed` | provider 实际执行失败并保留原因 |

每层还有独立 mode。`mock` fixture、历史 `cached` evidence 和当前 `live` Git 不能混为一谈；bundle mode 取参与层中最保守的模式。

## File layer

输入为 Git adapter 解析的两个 commit，不接受 raw status 文本。输出包含 path、old path、change kind、additions/deletions、binary flag 和 LFS pointer metadata。Git object format 独立于 artifact checksum。

LFS pointer metadata 包含 pointer version、OID algorithm、OID、size、object availability（可未知）、lock requirement 和 active lock reference。二进制内容不生成文本 merge 结论。

## Semantic layer

每个 `SemanticEntity` 必须提供：

```text
entity_id
entity_kind
schema_id + schema_version
artifact_id
producer_module
values
mode
```

比较按 stable `entity_id` 对齐，并输出 JSON Pointer 属性路径。相同 ID 的 schema/provider/version 不同会产生 `incompatible_schema`；没有显式 provider migration 时不做名称、层级路径或索引回退。

删除是合法 diff。只有一个待执行 mutation 明确指向被删 ID 时，才产生 blocking `deleted_target` conflict。已有评论仍保留旧 version/object anchor。

## Fixed-camera visual layer

可比较 descriptor：

```text
camera_id + world-space pose + axis convention
projection + vertical FOV
width + height + channels
color_space
capture_recipe_version
renderer_version
```

任一字段不同即 `incompatible`。兼容时计算 changed samples、sample count、mean absolute error 和 maximum absolute error。这些是像素指标，不代表更好、更美或用户偏好。

## Behavior layer

可比较 descriptor：

```text
test_case_id
protocol_version
config_id
start_state_id
seed
```

build ID 可不同，因为比较目标正是不同 build。输出 objective、assertion 和 step 的 before/after delta。没有 producer 提供的 acceptance rule 时，不输出 improved/regressed 判断。

## Conflicts

首版结构化 conflict codes：

- `dirty_worktree`：非阻塞 review warning；不可用于 mutation；
- `merge_conflict`：blocking；
- `stale_base`：审批或执行基线不再匹配；
- `locked_binary_asset`：缺少锁或锁属于他人；
- `deleted_target`：mutation target 已删除；
- `incompatible_schema`：输入无显式兼容路径。

UI 显示 code、文字和 blocking 状态，不依赖颜色，也不把失败层显示成空层。
