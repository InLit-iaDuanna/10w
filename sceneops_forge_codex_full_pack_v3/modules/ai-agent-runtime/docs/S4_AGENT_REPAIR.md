# S4 诊断、修复与复查交付

## 用户路径

1. 在已登记的卡片工程中创建游戏执行任务，开启“受控浏览器操作”。
2. 如果需要模型读取截图，单独开启“将当前任务截图传给模型”；选中对象或浏览器权限不会自动开启它。
3. 确认授权卡中的工作区、Provider、模型、浏览器范围、截图输入和 16 次模型请求上限。
4. Agent 使用已登记的构建和预览执行局部行为检查，读取结构化失败证据，增量修改原游戏源码，重新检查、构建并复跑同一行为检查。
5. 任务界面分别显示每个检查的 `pass`、`fail`、`not_run`、`stale` 或 `unknown`，以及构建/预览/浏览器运行 ID、失败断言和截图输入状态。

## 实际 Agent 验收

- 日期：2026-09-07（Asia/Shanghai）
- 隔离项目：新建 Object / Component 测试项目与新卡片工作区，不复用历史授权。
- Provider / 模型：`codexcli` / `cli-default`，未在运行中切换。
- 用户指定的固定输入：`ArrowDown 400ms -> release 160ms -> ArrowUp 400ms -> ArrowDown 400ms`，检查 `movement-collection` / `start`。
- 修复前：`same-items-not-scored-twice` 失败；首次经过后得分 1，再次经过后得分 2。
- Agent 自主工具序列：工作区检查 -> 测试构建/预览与浏览器复现 -> 读取 `Game.ts` -> 读取 `Collectible.ts` -> 写入修复 -> TypeScript 检查 -> 测试构建 -> 同一浏览器检查 -> 交付构建/预览 -> `current-input` -> 完成。
- 修改位置：`src/game/objects/Collectible.ts`；删除了玩家离开碰撞半径时对 `collected` 的错误复位。
- 修复后：同一 `movement-collection` 检查全部断言通过；首次和再次经过后得分均为 1。
- 普通交付构建：`current-input` 的移动与松键停止断言通过，且交付页未暴露测试 hooks。
- 保护项：`src/game/sceneops-test.ts` 字节不变；未改断言、起点或检查脚本。
- 模型请求：16 / 16。Codex CLI 本次未报告 Token 数，因此 Token 用量记为未知，不估算。
- 截图输入：已传入。服务端根据当前任务、构建和浏览器运行解析不可变 PNG 制品，将实际图像路径传给 Codex CLI；模型提示词只含制品引用，不包含本地路径。

本地机器可复查记录位于 `.local/s4-evidence/real-agent-repair.json`，修复后截图位于 `.local/s4-evidence/post-fix-current-view.png`。

## 确定性与浏览器回归

- 诊断投影、技能选择、请求压缩、新旧证据、完成摘要和截图权限/路径校验使用离线测试。
- Object / Component 和 ECS 两种现有架构均使用真实 Chromium 通过 `movement-collection` 和交付 `current-input` 回归。
- 真实模型闭环在 Object / Component 架构上执行；ECS 的模型修复流未重复执行，但其真实浏览器回归已覆盖。
- 当前工作区与本轮提交的定向 Python 组合中，46 项通过、3 项按显式环境条件跳过；前端相关 9 项通过。

## Limitations

- 通过的是明确的局部行为检查和基础输入回归，不是全局 `gameplay_verified`。
- 本轮虽将截图像素传给了支持的模型，但不将其表述为已完成画面质量或视觉风格评审。
- OpenAI-compatible 自定义 Provider 的图像能力在没有明确模型元数据时保持 `unknown`，不自动试探、切换模型或扩大预算。
- wheel 资源隔离导入测试仍被 S3 基线中 `task_tools.py` 对未打包 `engine_unity` 的顶层导入阻塞；该导入在本轮基线 `a1072cd` 已存在，本轮不将无关打包修复混入 S4。
