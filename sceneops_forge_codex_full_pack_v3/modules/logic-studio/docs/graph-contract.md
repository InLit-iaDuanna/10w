# GameplayGraph 合同与确定性验证

`GameplayGraph` v1 是 Logic Studio 的唯一玩法状态源。磁盘合同位于
`contracts/manifests/gameplay-graph.v1.schema.json`，运行时网络模型由
`backend/src/logic_studio/models.py` 的 Pydantic 模型定义。

## 组成

- 状态变量：布尔、整数、数值、字符串或字符串集合，以及确定的初始值。
- 事件：图内条件、任务完成和反馈所引用的稳定事件 ID。
- 节点：开始、状态、交互、任务、对话、反馈与结局。
- 边：源/目标节点、可选事件、条件、效果和发出事件。
- 交互关系：两个已声明 `sceneops_id` 之间的有向语义关系。
- 验收标准与生成测试引用：用于证明每项已批准要求有节点映射和测试覆盖。

显示名、层级路径和文件路径不会作为对象身份。对象重命名只更新
`SceneObjectRef.display_name`；节点和关系仍引用原 `sceneops_id`。

## 验证顺序

确定性验证器运行以下规则，不调用模型：

1. 重复 ID、唯一开始节点和至少一个结局节点；
2. 节点、事件、变量、验收标准和场景对象引用；
3. 条件运算符、效果操作和值类型；
4. 同一动作中的冲突效果；
5. 从开始节点的可达性；
6. 可达但无法到达结局的死支路；
7. 没有出口的强连通循环；
8. 验收标准到节点和生成测试的覆盖。

诊断按 `location`、`code`、`message` 排序，因此相同输入产生相同报告。
错误使 `valid=false`；未来可添加不阻止构建的警告规则。

## 版本与差异

序列化使用排序键和紧凑 JSON。只接受 `schema_version: 1`。同一图的提议版本
必须严格大于基础版本；差异按状态变量、事件、场景对象、节点、边、关系、
验收标准和测试引用输出 `added`、`removed` 或 `modified` 条目。

## 模板与示例

`workflows/interaction-templates.v1.json` 保存数据驱动模板，编译器只替换显式
绑定并拒绝缺失或未解析的占位符：

- `inventory-token-opens-target`：Find My Way Home 的收集物、背包、锁、任务、
  三类反馈、对话和结局；
- `switch-opens-target`：Warehouse Escape 的开关、门、反馈和出口。

两个确定性绑定位于 `contracts/examples/`。模板使用绑定的稳定 ID，不硬编码
项目对象名。
