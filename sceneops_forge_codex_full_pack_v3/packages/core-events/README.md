# Core Events

SceneOps Forge 的事件版本公共规则。事件引用使用 `dotted.event.name@<version>`，从版本 1 连续递增。

发布后的同版本 payload schema 不可修改；任何变化都必须创建下一个版本。事件 schema 必须声明 `x-event-type`、`x-event-version` 且 payload 为 JSON object。

公共入口：`sceneops_core_events`。

```bash
scripts/module-test core-events
```
