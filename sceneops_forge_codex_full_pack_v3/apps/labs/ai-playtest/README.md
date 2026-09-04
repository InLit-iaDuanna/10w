# 工作台 10：AI 测试与问题定位

独立 Web 入口只组合 `modules/ai-playtest/frontend/src/index.ts` 的公开懒加载接口 `loadAIPlaytestWorkbench`。业务视图、样例投影与本地草稿位于模块 `frontend/src/workbench/`。没有复制 core kernel，也不依赖其他工作台启动。

## 启动

环境：Node 22.12+、pnpm 11.13.0。首次从应用根安装本 lab 的依赖：

```bash
cd /Users/isduanna/.codex/worktrees/0395/10w/sceneops_forge_codex_full_pack_v3
pnpm --dir apps/labs/ai-playtest install --ignore-workspace
pnpm --dir apps/labs/ai-playtest dev
```

打开 http://127.0.0.1:4319/ 。此入口只浏览静态证据并维护内存草稿，不需要 API，8319 不监听。Ctrl+C 停止自己启动的开发服务。端口占用即报错，不会终止其他进程。显式换端口：`pnpm --dir apps/labs/ai-playtest dev --port 14319`。

依赖固定为 React/ReactDOM 19.2.8、TypeScript 6.0.3、Vite 6.1.0、Zod 3.25.76。React/Vite/TypeScript/Zod 均为 MIT。安装脚本保持禁用；本 lab 的 `allowBuilds.esbuild=false` 明确拒绝 esbuild 安装脚本，开发转换使用包附带的平台二进制。没有运行应用生产构建。

## 手动验证

1. 搜索并切换“家门修复前 / 修复后 / Warehouse Escape”样例。
2. 点击问题卡，观察轨迹、观察编号、时间线和回钉详情联动。
3. 在“场景配置”选择 CodeBuddy CLI 模型、调整目标、种子、最大步数，保存当前页面草稿；原始快照保持不变。
4. 在问题详情填写意见，模拟确认或拒绝。未解析的回钉不允许确认；审阅不会覆盖已保存的决定。
5. 模拟确认唯一回钉后，填写变更前值、建议值、理由、预期、验证/回滚计划，保存 PLANNED 提案草稿。
6. 选择 Live/Cached 查看缺少连接或真实历史证据的说明，再返回 Mock。查看“来源与限制”和原始观察。

页面草稿隔离于生产数据，刷新即清空；这是明示的模拟交互，不是对后端 Issue 的正式审核。提案未提交到 CommandRegistry 或 owning module。真实审核必须使用现有 `AIPlaytestService.review_backpin` 的认证上下文，正式提案必须使用 `propose_issue_change` 和 owning module 的 ChangeSet 审批。新入口没有 runner、Unity 或测试启动路径。

## 数据与真实性

AI 接入约定：如需真实 AI，使用 CodeBuddy CLI。本机可执行命令为 `codebuddy`，不是 `codebuddycli`。场景配置固定 `aiProvider=codebuddy-cli`，按 TestCase 在页面内保存 `aiModel`；空值代表使用 CLI 默认模型。模型选项来自 2026-09-05 本机 `codebuddy --help` 的 `--model <model>` 列表，并非实时账号授权查询。未来服务端调用应将所选模型作为独立的 `--model` 参数（默认模型则省略），不能在浏览器执行命令或拼接 shell。此轮没有增加 CLI 调用端点、凭证、权限绕过或 AI 执行路径。

- Mock：读取模块原有 `contracts/examples/*.runtime.json`、TestCase 与 source catalog。问题卡是明确标注的手工审阅样例，不是本次 detector 输出。
- 轨迹：静态帧的坐标投影；物体图形为示意，没有真实截图。
- 场景配置与修复建议：当前页面内的 Planned 草稿，未派发。
- Live：Blocked；没有 Unity 连接。Cached：Planned；没有真实历史 PlaytestRun。
- “修复后样例”只是已有 fixture，不表示本工作台执行过修复或验证了改善。

## 本轮精确验证

2026-09-05：

- 启动/导入：`pnpm --dir apps/labs/ai-playtest dev` 成功；Vite ready，监听 `127.0.0.1:4319`；React 懒加载界面可见。
- 唯一最小展示/选择路径：打开首页 → 点击“钥匙在手，家门交互被碰撞体遮挡”。通过：观察 4 被选中；时间 `2026-09-04T01:00:04Z`；位置 `7.5,0,0 m`；时间线第 4 行选中；源目标 `component.home-door-interaction`、所属模块 `logic-studio` 可见。
- 初始入口交付时未执行配置保存、模拟审阅/拒绝、提案表单等其余交互。
- CodeBuddy 模型选择补充验证：Vite 热更新后打开“场景配置” → 选择 `deepseek-v4-pro` → 保存本地配置草稿；下拉框显示所选模型，并出现“配置草稿已保存到当前页面；尚未提交测试。”。只执行这一条新增 UI 路径；未调用 AI，未查询账号模型权限。
- 原 hero 测试未重跑。完整单元、集成、E2E、安全、性能、类型检查、生产构建、AI playtest、Unity：**not run / pending approval**。
- 上轮 hero 的缺失 `UtcDatetime` 导入已修复并保留，但未将上轮结果当作本入口通过证据。

## Shell 组合说明

本 lab 对齐公共 `dev` 接口，未改根 workspace/启动器/锁文件。独立 lockfile 与局部 pnpm 配置只服务本入口。后续 Shell 统一接入时可使用共享 Vite 8.0.0/根 workspace 依赖；请由 Shell 组处理根锁文件及本 lab 独立锁文件的归并。根 `pnpm lab ai-playtest` 由共享启动骨架提供，本工作树直接使用上面的独立命令。

新入口没有挂载完整 Dockview Shell，也没有接通正式 API/持久化、鉴权、事件总线和跨模块审批；它是可独立手动验证的证据工作台。正式操作应复用既有模块服务，不将浏览器模拟标记迁移为生产审核结论。
