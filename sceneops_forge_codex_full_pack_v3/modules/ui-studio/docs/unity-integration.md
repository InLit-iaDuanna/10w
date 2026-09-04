# Unity UI 接入约定

`UiMappingRequest` 只含稳定的项目、`sceneops_id`、流程、界面、预制体与 Canvas 路径标识。engine-unity 消费这些字段时必须实现 `UnityUiAdapter` 的 capability、dry-run 和 publish 方法；UI Studio 不导入其内部实现。

先调用 `ui.mapping.propose` 获取 `mock`、`planned` 或 `live` 的预览，映射仍为 `proposed`。只有 `ui.changeset.approve` 后，才允许 `ui.changeset.publish`；审批身份与时间由可信宿主上下文注入，而不是命令参数。审批后若 request、目标或变更值发生变化，发布会被拒绝。发布结果必须回填 adapter 版本和真实 execution mode，并由宿主生成完整 SHA-256 溯源记录；其模式、来源项目/版本和关联 `sceneops_id` 必须与获批请求一致。
