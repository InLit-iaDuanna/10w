# Unity U1 阶段交付与验收记录

2026-09-08。**Unity U1 已完成。** 同一份真实 Blender 门资产已进入独立 Unity 工程，并完成手工编辑、产品内 Agent 编辑、源版本升级、Unity Editor 实际运行以及关闭重开。Blender 上轮已经收口，本轮没有扩成 Unity U2、Player 发布或苹果目标。

## 最终用户路径

```text
SceneOps 选择真实 Blender 资产
→ 准备隔离的 Unity 编辑工作区
→ 导入模型、稳定外层 Prefab 与两个场景实例
→ Unity Inspector 手工修改实例并保存
→ 产品内 Agent 读取另一个实例、修改并回读
→ Blender 产生源版本 3，再次导入 Unity
→ 外观更新，实例覆盖、行为、节点绑定和 Prefab 身份保留
→ Unity Play 中取钥匙、碰门、开门并穿过
→ 关闭 Editor、重新启动、再次回读
```

最新工作台界面已与 U1 后端合并验证。资产选择后直接显示“用 Blender 编辑”和“打开 Unity 编辑工作区”，不再以孤立技术任务页作为主要入口。Unity 卡片默认显示“已同步并保存”、源版本、场景、实例数和保存状态；工程路径与内部 ID 收在技术信息中。界面也明确区分 SceneOps 本次编辑权限与 Unity Hub 许可证状态。

## 实现与数据边界

沿用 `UnityAgentSession` 和认证 mailbox。SceneOps 从登记的 Blender 源版本派生真实 FBX，同时保留 Web GLB；Unity 使用稳定外层 Prefab、版本化模型和源节点 ID 管理两个实例。工作台、Inspector 和 Agent 通过同一 Editor 服务读写，实例字段以 Unity Editor 回读为准。

写入使用绑定 task、grant、action 与 request 的持久回执。导入派生失败时不派发 Editor 写入；结果不明时先核查回执，不直接重放。Unity 关闭后，缓存会话会在下一次操作前重新启动并回读实际状态。

## 实际验收结果

| 项 | 实际操作与结果 | 状态 |
|---|---|---|
| A 工程与 Editor | 本机 Unity 2022.3.62f3c1、Unity Personal 许可启动隔离工程；真实导入、编译和状态回读完成 | 通过 |
| B 真实资产 | Blender 源版本 3 导入 Unity；门框、门扇、铰链、碰撞节点、材质与源节点 ID 可回读 | 通过 |
| C 两个实例 | x=0 与 x=5 两个独立实例共享同一外层 Prefab；实例 ID 与各自参数分别保存 | 通过 |
| D 手工 Inspector | 在真实 Unity Inspector 将 x=0 实例交互距离从 2 改为 2.75，保存、回读和重开后仍为 2.75 | 通过 |
| E 产品内 Agent | CodeBuddy / GLM-5.3 读取两个实例，只把 x=5 实例交互距离改为 1.25；保存并回读 | 通过 |
| F 源版本升级 | 真实 `.blend` 产生版本 3；门框变橙、尺寸变为 1.2 × 2.2 × 0.15；模型 GUID 更新，Prefab GUID、行为和两个实例覆盖保留 | 通过 |
| G Unity 玩法 | Unity Play 中取得钥匙；关门时碰撞计数增加；交互后门打开；角色从门前穿过门框，碰撞计数不再增加 | 通过 |
| H 异常恢复 | 派生前失败记录为 NONE；未保存场景禁止重开；Editor 完全关闭后的结果核查为 NONE 且未重放；旧成功结果和源版本保留 | 通过 |
| I Shell | 在真实产品 Shell 中选资产、准备 Unity、Inspector/Agent 编辑、保存、源升级、运行与结束任务 | 通过 |
| J 关闭重开 | 完全关闭并重新启动 Editor 后，源版本 3、Prefab/模型 GUID、两个实例参数、节点绑定与场景路径均保持；无编译错误、场景未脏、未处于 Play | 通过 |

任务 `task_0129a3bc28e7430a9a3a97c3166549e3` 最终处于 `review_required`，这是产品结束流程要求人工审阅的状态，不表示执行失败。最终原因是“Unity 当前实例已保存并回读；玩法结果以单独的实际运行记录为准。”

## 关键身份与最终状态

- SceneOps 资产：`libasset_68790872d4444e7e8e940c633412efe2`
- Blender 源版本 3：`aver_blend_3544d582e2a64282b7f3588269e87621`
- Prefab GUID：`150f3016e98c542ed910e977c7f14334`，版本升级前后保持不变
- 模型 GUID：版本 2 的 `0a82907c6dd864b979c40f3cf67f3fbb` 更新为版本 3 的 `bbc46cb4adecf4ed8af13be030bc89c1`
- x=0 实例：`inst_b2d7e39ef5b942659c1c8d4c59a7ba94`，交互距离 2.75，需钥匙
- x=5 实例：`inst_4b544d93b13141e498ac79cd7b53bcfa`，交互距离 1.25，需钥匙
- 门框节点：`node_25bd3c1323544ddeb7ec29c7d573c622`
- 门扇节点：`node_065f0cb3b5ba431cbfa5cbdcda0de2c5`
- 铰链节点：`node_18aacd2a23ae472c83195c55871f1da3`

## 验证

- 后端 Unity U1 定向测试：42 项通过。
- 前端 Unity 工作台组件测试：4 项通过。
- 隔离分支前端构建通过。
- 合并其他方向最新 UI 后的完整前端构建通过：948 个模块完成转换。
- Unity Editor 实际编译：0 个编译错误。
- 实际 Play 证据：取得钥匙后 `has_key=true`；关门碰撞计数从 0 增至 153；开门并穿过后角色 z 从 -0.42875 移至 1.875，碰撞计数保持 154。

## 本机原始证据索引

原始证据保存在主工作目录 `.local/unity-u1/`，不提交用户 Unity 工程、数据库、许可数据或本机运行产物。

- `active-context.json`：任务、源资产、隔离工作区和证据数据库位置。
- `command-import-v3-fixed.result`：版本 3 的实际 Unity 导入结果。
- `command-agent-finalize.result`：产品内 Agent 修改并保存后的结果。
- `command-route-01-key.result` 至 `command-route-18-through.result`：Unity Play 取钥匙、碰撞、开门和通行过程。
- `command-reopen-final-fixed.result`：完全关闭后重新启动并回读的最终状态。
- `finish-final`：任务结束结果。
- `isolated-backend-tests.log`、`isolated-frontend-tests.log`、`isolated-vite-latest.log`：定向测试与隔离构建记录。

## Limitations

独立 Player 打包、iOS、DOTS、角色动画、任意格式导入和“任意 idea 自动生成 Unity 游戏”不属于 U1。主工作目录还包含其他方向未提交的并行改动；本轮只提交 Unity U1 自己的文件，并保留这些并行成果。没有推送远端。
