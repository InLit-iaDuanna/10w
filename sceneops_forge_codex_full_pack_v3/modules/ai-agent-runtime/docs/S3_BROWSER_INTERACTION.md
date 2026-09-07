# S3：命名起点与有限真实输入

沿用 S2 的浏览器执行、运行记录、产物存储和构建绑定。新增的是局部输入行为检查，不是自动玩家、视觉模型评审或完整观察—修复循环。没有调用真实模型；测试任务使用确定性动作调度，但游戏构建和 Chromium 执行是真实的。

## 用户路径

在卡片开发的执行范围中勾选「允许测试构建、状态重置及有限键盘输入检查」，审阅并确认新任务授权卡。任务结束后，在任务卡的「受控输入检查」中：

1. 点击「生成测试构建」，得到独立登记的 `sceneops-test` 构建。
2. 点击「检查移动与收集」：从 `start` 出发，向下 400ms、松键 160ms、向上 400ms、再向下 400ms。
3. 展开结果，查看每段真实回读、断言、构建／预览 ID 和截图。
4. 「普通构建输入检查」只读取原有 DOM 位置诊断并输入，不调用状态 hooks；结果标为交付构建证据。

该按钮配方适用于两种现有收集模板，不承诺任意游戏的同名起点都有相同含义。已有无 hooks 工程继续使用 S2 的 current-view，不自动覆盖或迁移源码。需要迁移时应另行明确授权源码修改。

## 工具与协议

`code.project.build_test` 的空输入调用原构建服务，固定增加 Vite 模式 `sceneops-test`。`code.browser.interact` 与 `POST /api/agent/tasks/{task_id}/game/interaction` 使用同一个 `BrowserInteractionRequest` 和服务方法。

请求只允许检查类别、状态 ID 和有限键盘序列：最多 8 段、每段 16–2000ms、合计不超过 8000ms、每段最多两个白名单按键。没有 URL、命令、JavaScript、浏览器参数、输出目录或断言 DSL。状态目录最多 32 项／8 KiB，单次游戏诊断最多 32 KiB。

两种模板只在测试模式公开 v1 `__sceneopsTest`：`states`、`setState`、`pause`、`resume`、`diagnostics`。重置操作复用原对象或 ECS 实体，清空输入、速度、分数、收集状态和计时；暂停只跳过原循环的游戏逻辑，RAF 仍绘制并更新上一帧时间。没有随机源，因此明确报告固定场景，不提供虚假的 seed 控制。

浏览器在导航前安装 [Playwright Clock](https://playwright.dev/docs/clock)，通过 [Keyboard](https://playwright.dev/docs/api/class-keyboard) 的 down/up 进入原输入监听器。重置在原 RAF 的帧边界执行，随后独立读取诊断，避免首次移动拿到依赖机器时序的半帧。没有直接调用移动／收集系统，没有用 setState 的返回值代替玩法证据，也没有给输入结果作位置修正。

检查先实际移动并收集，再带着残留按键重置并回读；随后检查暂停／恢复，最后从起点执行输入配方。结果分别保留设置确认、实际状态、输入轨迹、最终状态和局部断言。`behavior_checks_verified` 仅表示列出的局部断言通过，`gameplay_verified`、`visual_reviewed` 始终为 false。

## 授权与隔离

`allow_browser_interaction` 默认 false，与 `allow_browser_observation`、`allow_playtest` 分开。旧卡片不增加能力，不延长旧授权。交互授权绑定当前任务、项目、工作区、分支和卡片，沿用本次期限；单独撤销交互授权不撤销观察授权。任务取消会撤销两者。

测试构建、普通构建分别登记并保留输出。测试输入使用本次检查专用预览；关闭该预览不会停止用户原有预览。普通构建输入也使用新浏览器上下文，而不是附加到正在试玩的页面。沿用 S2 的精确来源网络策略、禁用 Cookie／工作台 Token／用户 profile、弹窗和子资源限制。检查前后核对目标及输出版本；变更、缺授权、未知状态、缺 hooks、取消、超时和加载失败分别记录，不把旧状态作为新证据。

## 可复验方式

离线协议与授权测试不需要模型或新依赖：

```bash
node scripts/python.mjs -m unittest discover -s modules/project-intake/backend/tests -p test_game_test_adapter.py
node scripts/python.mjs -m unittest discover -s modules/ai-agent-runtime/backend/tests -p test_browser_interaction.py
node scripts/python.mjs -m unittest discover -s modules/ai-agent-runtime/backend/tests -p test_browser_observation.py
```

真实验收需显式设置 `SCENEOPS_S3_GAME_DEPENDENCIES` 为已有游戏依赖目录，`SCENEOPS_PLAYWRIGHT_MODULE` 为已有 Playwright 模块；不会安装浏览器或依赖。设置 `SCENEOPS_S3_UI=1` 后，还会启动隔离 API 和实际 `AgentTaskWorkbench`，点击按钮、等待实际执行响应并验证截图已显示。`SCENEOPS_S3_EVIDENCE_DIRECTORY` 可指定本地测试证据目录。

## 本轮验证记录

使用仅含本次暂存改动的隔离副本，复用已安装依赖和 Chromium 151.0.7922.34，没有模型调用：

- 模板协议：2 项通过。
- S2 回归：6 项执行通过、3 项按环境条件跳过，不计作 9 项浏览器验收。
- S3 授权／输入合同、过期与跨项目拒绝、注入超时与取消清理、真实无 hooks 拒绝与进程取消均通过。
- 两种架构均通过实际工具调度、HTTP 重复回放、普通构建无 hooks 输入及真实工作台点击。联跑时对象／组件工程有一次最终类型核验失败；该架构定向复跑 6 项通过，ECS 在联跑中的验收通过。该次失败不计为全绿联跑，也不归因于已经证明不存在的原因。
- 暂存版本的任务工作台、交互面板及关联客户端定向 TypeScript 检查通过；没有宣称全仓 TypeScript 检查通过。

两种模板从 `(0, 0.5, 0)` 出发，首段回读 Z 为 `2.0000000000000004`，分数为 1；松键后位置不变；返回起点附近后再次经过，分数仍为 1，原收集物仍隐藏。重复任务的初态、每段诊断和终态使用完整相等比较。重置前已实际得到 1 分，重置后独立读到零分、全部收集物恢复和计时清零。

实际 Agent 工具链为 `code.file.write → code.project.check → code.project.build → code.project.build_test → code.preview.start → code.browser.interact → agent.finish`，其中选择动作的是测试调度器，不是真实模型。工作台按钮随后再次调用同一交互服务。

本地证据保存于 `.local/s3-evidence/`：两种架构各有初次／重复／普通构建 JSON，以及实际工作台截图。任务与游戏运行记录位于隔离测试项目内，测试结束清理；这些截图和 JSON 是留存验收记录，不冒充仍在运行的产品任务。

## Limitations

真实模型冷却任务未执行，也未使用过期授权。确定性动作调度不证明模型自主选对工具或制作成功率提升。工作台验收针对隔离服务中的真实任务组件，不代表全部 Shell 导航路径已回归。局部键盘行为、浏览器加载、截图采集、完整玩法和视觉质量分别报告；本轮不实施 S4–S6。
