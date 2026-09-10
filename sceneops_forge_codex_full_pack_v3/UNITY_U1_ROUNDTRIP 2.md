# Unity U1 阶段交付与待验收项

2026-09-08。**U1 尚未完成。** 本次保存资产派生、独立 Unity 工程、Editor 编辑接口、产品入口及定向测试；不是整体验收通过记录。Blender 上轮已收口，不在这里重做。

## 实现与数据边界

沿用 `UnityAgentSession` 和认证 mailbox。SceneOps 从登记的 Blender 源版本派生真实 FBX，保留 Web GLB；Unity 用稳定外层 Prefab、版本化模型和源节点 ID 关联两个实例。工作台与 Agent 调用相同 Editor 接口，实例字段以 Editor 为准。新增 Unity Project Engineer 产品技能。

独立 Unity 目标使用明确的有限授权。过期快照标记 cached；历史回执不能冒充当前 live 回读。未知写入先核查绑定 task/grant/action/request 的持久回执，不重放。续授保留历史，需先关闭本任务 Editor 并确认新授权卡；不延长旧授权。

## 实际验收进度

| 项 | 实际入口与操作 | 结果与证据 | 状态 |
|---|---|---|---|
| A 工程与 Editor | 登记隔离目标，启动本机 2022.3.62f3c1；实际初次导入 | 正确工程有真实回读；后续 Editor 明确提示无有效许可证。跨项目/范围拒绝另有单元测试 | 部分通过，许可证阻塞 |
| B 真实资产 | 既有真实 Blender v2 → FBX → Editor 导入 | 门框、门扇、铰链、碰撞节点及源 ID 有真实回读；完整视觉检查仍待做 | 部分通过 |
| C 两个实例 | 初次导入建立 x=0 与 x=5 两实例 | 两个不同实例 ID、同一外层 Prefab/模型 GUID；定向修改未验 | 部分通过 |
| D 手工 Inspector | 尚未完成手工修改、保存及重开 | 旧重开请求因场景不匹配在写入前拒绝；修复后未复验 | 待完成，许可证阻塞 |
| E 真实 Agent | 已接当前配置 CodeBuddy CLI / GLM-5.3 的产品工具入口 | **没有执行新的 U1 模型修改**；初次导入为显式脚本操作，不算 Agent 证据 | 待完成，许可证阻塞 |
| F 源版本升级 | 已实现新 FBX 版本与外层 Prefab 保留 | 未实际制作 v3 并升级两个实例 | 待完成，许可证阻塞 |
| G Unity 玩法 | 已实现 Player、钥匙、交互距离、开门与碰撞 | 尚无真实 Unity Play Mode 通行验收；没有引用 Web 试玩结论 | 待完成，许可证阻塞 |
| H 异常 | 回执核查、版本/节点/权限等定向测试 | 真实旧重开请求核查为失败/NONE，无写入开始标记；完整取消、重载及导入失败组合未跑完 | 部分通过 |
| I Shell | 真实 Shell 选择资产、准备 Unity 目标并显示初次导入结果 | 完整编辑、打开实例和运行链尚未走完 | 部分通过 |
| J Web 不回归 | 在旧工程状态副本登记 Unity 根；原源版本和 GLB 保留 | 单元测试检查旧授权与源保留；未完成本轮完整 Web 试玩回归 | 部分通过 |

## 本机原始证据索引

以下为本机 `.local/unity-u1/` 中的验收数据，不提交用户游戏工程、数据库或本机运行产物。

- `active-context.json`：当前任务、源资产、独立工作区和数据库定位。
- `initial-import-final.json`：初次实际 Editor 导入记录；后续当前状态以 `reconciled-task.json` 为准。
- `reconciled-task.json`：任务 `task_0129a3bc28e7430a9a3a97c3166549e3` 已恢复为 review_required；最后旧请求为 failed/NONE，其余成功结果保留。
- `license-blocked.png`：Editor 的无有效许可证提示。
- `isolated-backend-tests.log`：从提交 9f0433c 独立重建本轮改动后，36 项 Python 定向测试通过。涵盖产品范围、回执、会话、工程初始化和 Blender 派生；不是 36 项真实 Editor 体验。
- `isolated-frontend-tests.log`：独立重建后 3 项组件测试通过，覆盖选定资产、准备失败和续授计数；不是人工操作。
- `compile.log`：9 个 Runtime、20 个 Editor、1 个 fixture C# 源文件引用程序集编译通过；不是 Editor NUnit 或 Play Mode 通过。
- `isolated-vite-latest.log`：独立前端构建通过。
- `isolated-types-latest.log`：全仓 TypeScript 检查未通过，仍报告 Shell、pipeline 等模块错误；本轮 Unity 入口的类型错误已修复，最新报告未再列出这些文件。构建成功不等于全仓类型检查通过。

原始模型 GUID：`0a82907c6dd864b979c40f3cf67f3fbb`；Prefab GUID：`150f3016e98c542ed910e977c7f14334`。

## 接续顺序

按任务文件禁止自动修改许可证/全局设置的要求，等待用户在 Unity Hub 恢复现有许可。随后从现有任务申请新的有限授权，不重放旧失败请求。继续 Inspector 单实例修改 → 产品内真实 Agent 修改另一实例 → Blender 新版本升级 → Unity Play Mode → 关闭重开 → Shell 全链与异常/旧 Web 回归。

## Limitations

独立 Player、iOS、DOTS、全角色动画、任意格式和任意 idea 自动生成不属于 U1。上表未通过项属于本轮待完成工作，不是范围外限制。阶段源码可独立审阅；未推送，未提交用户游戏工程。
