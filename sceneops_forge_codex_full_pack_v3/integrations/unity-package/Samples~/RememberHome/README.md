# Remember Home sample

`modules/engine-unity/fixtures/unity-projects/smoke-template` 中的 source-only builder 使用本包生成两个版本：

- Build A：保留钥匙可见度问题；
- Build B：同一 `sceneops_id` / 资产版本 / Prefab 身份上的批准可见度调整。

两者都连接 key pickup、inventory、entrance door、goal exit 与 runtime telemetry。生成的 scene、Prefab、material 和 standalone build 只存在于临时 smoke 工程或 `.artifacts`，不作为源文件提交。
