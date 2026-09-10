# D3 真实模型项目 Demo 验收

## 实现边界

`project-demo-agent` 是新的项目级 typed-tools 任务。它与 D2 的 `project-demo` 使用同一个项目 Demo 工作区、资产服务、场景服务、源码写入器、构建运行时和候选记录，但由现有 `AgentRuntime`／`task_loop` 请求真实模型选择下一动作。D2 任务继续保持零模型、固定钥匙门夹具语义。

授权卡限定一个 `project_id + workspace_id`，累计最多 28 次模型请求、32 个类型化动作和 30 分钟。追加目标保存在同一任务的 `demo_goals` 中，沿用原授权与计数；相同追加请求 ID 重放会返回现有任务，不同正文复用同一 ID 会被拒绝。

普通物化只读取当前场景及其引用的资产版本，输出 `.sceneops/demo-content.json` 和 `src/game/sceneops-demo-content.ts`。它不会创建门、补行为或覆盖普通行为源码。两个架构适配器都会呈现无行为的程序化实例；只有带 `KeyDoor` 的实例进入交互系统。

## 确定性接线验证

`test_project_demo_agent.py` 使用脚本化决策提供方验证请求、工具和状态机，不把它当作真实模型证据：

- 空项目准备和普通物化不会隐式创建夹具。
- 模型动作通过公开服务创建一个共享门资产、两个实例，并只给出口实例配置 `KeyDoor`。
- 重复创建相同门配方返回幂等成功，不新增资产或误算为失败；派生源码路径被拒绝，普通行为模块仍可编辑。
- 项目与工作区身份必须成对，内容动作要求先读取工作区资产和准确场景版本。
- 编译失败结果进入历史后，后续动作修改同一普通源码；物化保留该源码。
- 追加目标继续同一任务、工作区、期限和累计预算，并产生新的候选；服务重开后保留目标历史、实际源码和候选引用。

本批同时保留并执行 D1/D2 与 S1–S3 的相关定向回归：陈旧场景版本与跨项目对象写入不落盘；过期授权不会静默续期；失败构建保留当前可玩候选；较早结束的候选不能覆盖较新请求；关闭并重新创建服务后，任务、可编辑来源和当前候选仍可读取。

两种架构的模板分别执行依赖准备、`tsc --noEmit` 和 Vite 构建。对象／组件与 Miniplex ECS 都从同一物化内容读取共享资产、逐实例变换和可选行为。

## 真实模型与工具结果

2026-09-08 在隔离工程中使用已登录的 CodeBuddy CLI 执行了两条真实模型链。调用费用和 token 未由 CLI 报告，记录为未知。

### 钥匙门

- 模型：`glm-5.3-flash`。
- 结果：18 次决策内创建一个程序化门资产和两个共享外观的实例，只给出口实例配置 `KeyDoor`；第二次放置先遇到真实场景版本冲突，模型重新读取场景后重试成功。
- 工具：真实 TypeScript 检查、Vite 构建、登记预览和 Chromium 观察均成功；观察记录 1 个 canvas，控制台、页面和网络错误均为 0。
- 玩法检查：真实键盘输入取得钥匙后到达出口 0.92 米处，界面显示开门提示；按 Enter 后出口从 `open=false` 变为 `open=true`。无行为的装饰实例保持关闭。

### 顺序机关与追加修改

- 模型：`glm-5.3`。
- 初始目标：ArrowLeft → ArrowRight 开启出口。隔离工程预先放置一个含 `BROKEN_SWITCH` 的可定位普通源码问题；模型第一步运行真实 TypeScript 检查，读取 TS2304 诊断后自行重写 `OrderedSwitches.ts` 并接入 `main.ts`。开发者没有在产品外代修。
- 追加目标：同一任务把顺序改为 ArrowUp → ArrowDown，并同步独立的 `#switch-prompt`。全链共 26/28 次模型请求；初版和追加目标分别生成候选，服务重开后仍指向第二个候选。
- 工具：两轮物化、类型检查、Vite 构建、登记预览和 Chromium 观察均成功。最终真实浏览器输入中，错误键保持 0/2，ArrowUp 后为 1/2，ArrowDown 后宿主状态变为 `open`；等待 100 ms 后完成提示仍存在，控制台错误为 0。

真实试跑还发现并修正了两项接线问题：CodeBuddy 打印模式会回显大请求并在终态前截断，因此结构化调用现在统一读取流式消息的唯一终态结果；行为提示最初与游戏循环争写同一 DOM 节点，因此产品技能现要求确认状态所有者并检查下一动画帧后的稳定状态。

## 定向命令

```text
pytest test_project_demo_agent.py test_project_demo_task.py test_skill_context.py
pytest provider streaming/completion tests and harness call-budget tests
pnpm generate:agent && pnpm generate:harness
pnpm test:frontend modules/ai-agent-runtime/frontend/src/tests
pnpm --filter @sceneops/web exec vite build
```

只运行与 D3、D2 内容回流和 S1–S3 相关的定向套件。全仓 TypeScript 历史错误不作为本批门槛；改动文件、生成契约、前端生产构建和两个隔离游戏工程单独验证。

## Limitations

真实模型只在对象／组件架构执行；ECS 只做确定性服务回归和真实工程构建。浏览器内置观察不会自动理解任意新玩法，顺序机关的按键与稳定 UI 状态由独立真实浏览器检查确认。

本批不包含付费素材、Blender 往返、通用行为编辑器、完整 D4 工作台、所有游戏类型或所有引擎。程序化门和 `KeyDoor` 仍是首批领域工具；新的玩法行为位于可继续编辑的普通项目源码。

独立提交复核：在 `190f43b` 上仅加入 D3 差异，重新生成公开契约、通过 Web 生产构建和定向服务测试。S2/S3 扩展测试中的继承夹具有两类既有错误（已创建 dist 后再建同名链接、子类 prepare 不接受父类 execution 参数），已在原提交复现；不把它们计为通过。Shell 的两项旧资产导入类型不匹配也在未修改的 Shell 上复现。新增任务组件与生成类型未报对应 TypeScript 错误。
