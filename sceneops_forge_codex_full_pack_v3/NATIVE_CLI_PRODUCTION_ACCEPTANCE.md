# SceneOps 原生 CLI 制作验收 · 2026-09-09

新制作已接入「对齐目标 → 确认简报和权限 → 原生 CLI → 工作台接回 → 准确会话续改」。本轮真实执行只使用 CodeBuddy 2.147.0、当前配置模型 `kimi-k3-1`、medium、常规权限（acceptEdits）；没有切换模型或升级完整权限，没有提交、合并或发布。

## 已实现

- 简报可读、可编辑、按版本确认，带已确认方向、架构、用户原话节选及素材推荐来源；推荐与早期表达不自动升级为必做项。修改清除确认，普通续改继承已确认版本。
- 新项目为轻量 Three.js / TypeScript / Vite / pnpm 工程，支持对象／组件与 ECS / Miniplex，已有工程增量修改。统一投放 Gameplay、Graphics、UI、Debug、QA 技能及引用资源。
- 两种 CLI 独立选择权限、新建／准确会话恢复，恢复原生技能和规则读取。保存真实会话 ID、执行器版本、模型与权限、父轮次和候选；取消停止进程组，保留事件及文件，中断不自动重放。
- 任务绑定的 stdio MCP 桥复用资产、场景、物化、检查、构建、试玩与观察服务，不开放数据库。CodeBuddy 只精确允许当前 SceneOps MCP 的延迟工具调用；不允许整个延迟包装器。
- D4 使用工作区真实文件身份，记录新增、修改、删除及明确确认的重命名；手工保存与 CLI 共用数据库占用。共享文件资产可显式更新实例引用。工作台更新只物化和重建，不调用模型。
- 每轮交付重新物化托管内容，并接回构建候选；构建失败保留上一成功候选。

## 真实作品与运行证据

验收工程：[风暴灯塔岛](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/storm-lighthouse)。独立验收库和证据位于同级目录，未改动用户已有游戏工程。

固定提供仓库内的 `watchtower.glb`、`rock-cluster.glb`，通过工具登记为两个资产，放置一座灯塔和三组岩石。游戏实际加载物化的 GLB 与实例变换，玩家、岛面、海面与安全区由 CodeBuddy 原生编写。

真实会话：`01a084a7-3eeb-7afd-b762-b43bb6eb6780`。前两次执行暴露 MCP 发现和常规权限问题，取消记录与实际修改保留；修复适配后按该准确 ID 恢复，未使用最近会话。

| 验收项 | 结果与证据 |
| --- | --- |
| 首版制作 | 检查、构建、试玩通过；最终首版候选序列 3、场景 v4。[首版记录](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/first-evidence.json) |
| 开始、移动、点灯、返回、重开 | 使用真实浏览器按钮与键盘，看到交互提示、点灯反馈、胜利页并重开；未直接设置游戏完成状态。[首版操作记录](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/first-final-play.json) |
| 同会话“移动太慢” | 同一执行器、模型和会话 ID；速度 4.2 → 5.9（约 +40%）。一秒受控时钟键盘输入的真实位置读回为约 4.17 米 → 5.95 米，含帧边界差异；完整玩法再次通过。[续改记录](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/followup-evidence.json)、[输入证据](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/followup-play.json) |
| 工作台实例位置 | 调用实际内容保存服务，将一组岩石从 (-6,0,0) 改为 (-5,0,3)，保持实例 ID；保存后显示未构建。 |
| 共享资产引用 | 登记真实岩石 GLB 的新材质／缩放版本 v2，调用工作台保存服务将三处引用全部更新，场景 v4 → v6。[保存结果](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/manual-after.json) |
| 重建与实际效果 | 固定重建未启动 CLI，生成候选序列 6、场景 v6。三处岩石在画面中实际变为橙色并变大，实例位置发生变化；移动、点灯、返回和重开再次通过。[重建记录](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/manual-rebuild-evidence.json)、[实际操作](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/manual-play.json) |
| 宽窄窗口 | 1280×720 与 390×844 开始和游戏画面实际检查，无横向溢出、页面错误；窄窗目标文本换行。 |
| 画面 | 人工查看真实截图，暖色安全区、冷暗环境及点灯后暖光变化可见；不以构建成功替代视觉判断。 |

[首版点灯画面](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/first-final-lit.png) · [工作台修改后画面](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/manual-lit.png) · [窄窗开始页](/Users/isduanna/Documents/10w/.sceneops-acceptance/native-20260909/manual-narrow-start.png)

## 本地验证

- 43 项后端定向回归通过：两种 CLI 参数与会话、原生指令、授权、简报、取消、桥接领域操作、源码登记、内容编辑、轻量工程、历史示例资产兼容和对齐上下文。
- 随后新增的已扫描文件重命名回归：源码登记 4 项通过；最后简报／制作续接回归再次通过。
- 前端 11 项交互测试通过：简报显式确认、失败保留草稿、执行器选择、准确会话目标、源码冲突、共享引用更新。
- 既有“构建失败保留上一可玩候选”专门用例通过。
- 工作台生产构建通过；后端 OpenAPI 已重新生成前端类型。
- Codex 仅本地适配验证，覆盖支持版本、参数、真实 ID 事件解析和恢复，未调用真实 Codex 模型制作游戏。

## 验收中修复的问题

1. CodeBuddy MCP 已连接但工具发现入口未开放：恢复 Skill、ToolSearch 与延迟调用相关工具。
2. 常规权限下延迟 MCP 调用被拒：仅授权当前 SceneOps 工具名范围，不扩大为完整权限。
3. GLB 物化类型缺少 `glb`：修复生成器，工作台再次物化与真实重建通过。
4. 每轮候选需要自己的内容版本：补齐每轮自动物化。真实提速轮使用修复前已运行的服务，候选场景版本为空；最终工作台重建的 v6 记录完整，本地续改测试同时验证新代码不会遗漏场景版本。旧证据未被改写。
5. 工作台保存与制作并发竞态：使用数据库占用覆盖完整保存期间。

## Limitations

- 真实 CodeBuddy 的旧 `browser.interact` 检查未通过：它依赖旧游戏测试协议，原生作品没有该协议。没有把这些失败改成通过；本报告玩法依据独立 Playwright 的真实按钮、键盘、DOM 反馈与截图。已在技能和工具描述写明该工具的适用范围。
- MCP 观察返回截图路径；CodeBuddy 本身未成功读取工作区外截图。本轮由主代理独立查看图片并记录结果，未声称模型已经看过画面。
- 视觉为最小可玩作品：整体偏暗，使用瞭望塔素材作为灯塔，窄窗仍需要键盘，没有验证触屏玩法、真实移动设备性能或音频。没有与独立原生 CLI 做质量优劣比较。
- 工作台回流通过真实后端内容服务执行，前端按钮路径由组件测试验证；未运行完整 SceneOps 页面中的端到端点击验收。
- 全仓 TypeScript 检查仍有既有模块解析与历史夹具错误；较广旧 Codex 测试中两条命令事件预期与当前已有事件格式不一致。未宣称全仓测试全部通过，未为本轮修改无关历史预期。
- 验收使用独立 SQLite 与临时本地试玩服务。会话、工程、版本与截图证据已落盘；本地预览需服务进程存活。
