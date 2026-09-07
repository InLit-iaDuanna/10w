# S2：观察当前已登记构建

基线：S1 技能请求接入在 `5800305`；旧授权历史兼容、摘要语义和 observations 投影已独立提交于 `e977b4b`。本轮直接沿用，未混入其他工作区改动。S1 的真实模型冷却修改仍是独立待补验项，本轮没有调用真实模型，也没有延长旧授权。

## 用户路径和授权

在卡片开发范围中勾选「允许独立浏览器运行当前构建并采集截图与错误」，再确认任务授权卡。任务构建并启动预览后，执行流中的「当前构建观察」提供「观察当前画面」「取消本次观察」「撤销观察授权」。Agent 在同一确认范围内可调用无参数的 `code.browser.observe`。

浏览器会执行游戏代码，因此此选项默认关闭。旧卡片、旧 grant 和旧任务反序列化后都不获得此能力。确认时在原任务记录中保存单独的 `browser_authorization`，精确绑定 task/project/card/workspace/branch，截止时间等于此次代码授权的截止时间。代码任务结束照常撤销代码 grant；只观察范围可在原 20 分钟期限内重复使用。撤销观察授权不会撤销或改写已完成代码任务，也不会停止原预览；取消本次检查只停止本次会话。没有授权、已过期或已撤销时，在浏览器启动前拒绝。

## 执行与证据

入口仍为 `POST /api/agent/tasks/{task_id}/game`，新增 operation `observe`。状态仍由 `GET .../game` 返回。专用取消和撤销端点分别是 `POST .../game/observation/cancel`、`POST .../game/observation/revoke`。产品按钮和 TaskTools 调用同一服务。

成功构建将输出保留在应用自有 `game-runtime/builds/<build-run-id>/dist`，预览通过 `build_run_id` 绑定并服务该输出版本。观察只使用当前任务、本卡片工作区的成功构建与活动预览，拒绝同卡片另一任务的输出。旧版本若没有独立构建输出和预览关联，返回 `CURRENT_BUILD_REQUIRED` / `CURRENT_PREVIEW_REQUIRED`；需要正常重新构建/启动预览，不修改旧记录来假定关联。

观察结果保存在既有 `game_project_runs`，包括 task、workspace、branch、build run、preview run、时间、加载状态、console/page/network 错误、受限请求、截图状态和基础 DOM 诊断。PNG 使用现有生产步骤、产物表和内容接口登记；没有另建验证数据库。构建目录在采集前后的文件身份/大小/修改时间改变，或构建/预览关联改变，结果标记失效，不发布为当前截图。源码写入使旧观察失效。

检查最长 35 秒（含等待工程锁），进程清理另有最多 5 秒终止等待后强制结束。缺 Node/Playwright/Chromium 为 `BROWSER_UNAVAILABLE`；授权问题、预览问题、`BROWSER_TIMEOUT`、`BROWSER_CANCELLED`、`BROWSER_LOAD_FAILED` 和执行器故障分别记录。取消、超时和失败都会等待本次 worker 清理，不附加用户页面、不停止既有预览。

## 浏览器访问范围

每次启动新 Chromium 和无存储状态的 context。没有工作台 Token、用户 Cookie、用户 profile、已有页面或调用方 JS。模型和 HTTP 请求均不接受 URL、命令、浏览器参数、输出目录。

仅允许服务端选定预览的精确 HTTP origin、主页面的 GET/HEAD 请求；请求由受控 route 获取，不自动跟随跳转，跳转目标再次检查。请求头不继承用户会话。外部域名、其他 localhost 端口、WebSocket、子框架、worker、弹窗和下载不开放，CSP 同时限制子资源。被阻止的资源和错误保留在记录中；不会因此自动扩域或修改项目。

固定基础诊断读取 document title、ready state、viewport 和 canvas 数量。没有要求游戏实现新 hooks；未提供游戏诊断时明确标记 `dom_only_game_diagnostics_missing`。没有按键、seed、命名状态、玩法通关、像素评分或视觉模型反馈。

`passed=true` 只表示本次采集完成。`loaded`、`screenshot_collected`、错误数组分开；`gameplay_verified=false`、`visual_reviewed=false`。页面存在运行错误时仍可保存截图和错误供查看，不能将采集完成等同于游戏无错误。

## 本机执行器配置

随包提供 `browser_worker.mjs` 和可选 Node 依赖声明（Playwright `1.62.1`）。执行器默认解析已安装的 `playwright`；也可由服务端部署配置 `SCENEOPS_PLAYWRIGHT_MODULE` 指向受信任的已有安装。`PLAYWRIGHT_BROWSERS_PATH` 可指定已有浏览器缓存，否则采用当前服务用户的标准缓存目录。它们不属于模型/HTTP 输入。

运行时不调用 npx、不安装 npm 依赖、不下载浏览器。缺少时报告不可用，由操作者按部署方式显式配置。本轮验收复用了本机既有 Playwright 1.62.1 / Chromium headless shell；没有修改游戏模板或安装依赖。

## 本轮验证

- 最终独立暂存区快照定向回归：24 项中 21 项执行通过，3 项需要显式 live 环境的检查跳过；覆盖 S2、原工程运行流程和 S1 请求上下文。此结果没有借用工作区其他未提交修改。
- 真实浏览器取消另行执行通过：连续取消同一次观察后 worker 已回收，进程登记清空，原预览保持 running。
- 定向运行 S2 与原 GameProjectRuntime 测试：13 项中 12 项执行通过，1 项双架构 live 检查因未指定现有依赖路径而跳过。包括真实无 hooks 页面截图、console/page/404 错误、缺浏览器、缺授权、过期/撤销、取消、超时、构建变化、任务归属及输出保留；部分边界使用注入执行器，不能视为真实浏览器验证。
- 双架构 live 检查单独执行通过：通过 workspace 公开服务创建临时对象／组件式与 ECS 工程，复用已有依赖，执行真实 TypeScript/Vite 构建，再从产品 HTTP 观察端点调用真实 Chromium。两者均取得 1280×720 PNG、canvas_count=1、page_errors=[]，保留各自 build/preview/task 关联。
- 对象／组件式：观察 `game_run_566a28edb93c45f6919388cf07d54ad4`，构建 `game_run_d6a2aa7492be44499f5f52d35758c877`，预览 `game_run_75e798a441e04d68b7331b95dfedfd5e`。
- ECS：观察 `game_run_652139bc40a74264a1edb0a386f7180d`，构建 `game_run_d903f52369fb4359965d4e3760445f00`，预览 `game_run_42d1227291fa45b8baa0bd0e0309cf24`。
- 以上工程和浏览器均为临时隔离验收，已清理。没有执行 S1 的真实模型冷却任务，没有声称 Agent 制作成功率提升。
- 前端全仓类型检查仍有既有错误；本轮相关前端文件经定向诊断过滤无错误。产品 HTTP 路径已验收，完整工作台的人工点击和视觉布局回归尚未执行。

不把不同范围的测试数量相加成独立验收总数。S3–S6、视觉理解和观察—修复循环不在本轮交付内。
