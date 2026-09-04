# 渲染与 AI 变体独立工作台

React + Vite 前端与 FastAPI 入口仅负责装配。业务、审批、队列、缓存规划与固定样本位于 `modules/render-ops`，不建立第二套领域服务。

## 安装与启动

在本 worktree 的应用根目录执行（需要 Node 22.12+、pnpm、uv）：

```sh
cd /Users/isduanna/.codex/worktrees/1b38/10w/sceneops_forge_codex_full_pack_v3
pnpm --dir apps/labs/render-ops install --ignore-workspace
uv venv apps/labs/render-ops/.venv
uv pip install --python apps/labs/render-ops/.venv/bin/python -r apps/labs/render-ops/requirements.txt
pnpm --dir apps/labs/render-ops dev
```

Web：<http://127.0.0.1:4316>。API：<http://127.0.0.1:8316/api/render-lab/health>。
一个 dev 命令启动两端；Ctrl+C 只终止该命令创建的进程。仅监听 loopback。端口冲突时显式设置 `RENDER_WEB_PORT`、`RENDER_API_PORT`，不自动换端口。自定义 Python 可设置 `RENDER_PYTHON`。

前端从模块公开 index 引入工作台，通过生成的 OpenAPI 类型与 openapi-fetch 调用 API；TanStack Query 管理服务状态。根 workspace 和根 lockfile 留给 Shell 集成，本入口可独立安装。未引入 Dockview，独立入口使用固定工作区布局。

修改 HTTP 契约后执行 `pnpm --dir apps/labs/render-ops generate:api` 更新模块内生成类型。

## 手动操作

1. 左侧选择配方、CodeBuddy CLI 模型，编辑提示词、Seed 和采样数，创建本地任务。
2. 队列查看复用/待采集通道，载入固定样本；可取消和重试。
3. 在变体比较页选择原图与候选，计算固定像素差异、显示门体保护区；AOV 页检查通道与场景身份。
4. 来源链区分请求的 AI 模型与实际固定样本来源。
5. 审批提案页先确认变体，再填写灯光强度与理由，创建并审批本地提案。审批不会写回工程。
6. 重置演示只清除当前标签页会话的内存记录。API 重启也会清空记录。

## AI 约定与边界

需要 AI 时采用 CodeBuddy CLI；本机命令名为 `codebuddy`，通过 `--model <model-id>` 选择会话模型。下拉选项来自 2026-09-05 本机 `codebuddy --help`，实际账号权限尚未验证。`cli-default` 表示未来调用时省略 `--model`，不是传给 CLI 的模型 ID。该列表是会话模型，不是 `--text-to-image-model` 或 `--image-to-image-model` 的候选列表。

当前轮次不调用 CodeBuddy、ComfyUI、Blender 或 Unity，不执行任何外部渲染或生成。模型选择保存在任务输入和 mock 来源参数中，`ai_invoked=false`；实际 provider 始终为 `deterministic-local-fixture`，不能把样本冒充所选模型的输出。尚未实现 CLI 执行适配器。

16×16 单通道固定像素仅用于展示差异测量，Normal 也是示意图。提示词、Seed、采样数和版本修改用于记录与缓存规划，不改变样本图像。来源 checksum 沿用既有 mock 占位值。状态在本地 API 内存中，非生产持久化；会话 UUID 与固定请求头用于演示隔离，不构成生产身份认证。

## 本轮验证记录

2026-09-05：FastAPI 导入/OpenAPI 类型生成成功，dev 启动 Web 4316 与 API 8316，浏览器成功加载页面。

仅执行一次最小本地主路径：前端选择 `glm-5.3` → 创建任务 `lab-job-1a4c6c1469a6` → 载入两份固定样本 → 来源链显示 `codebuddycli / glm-5.3` 未执行、实际 provider 为固定样本。任务从 queued 进入 waiting_approval，缓存规划复用 5 个 AOV、待采集 0 个。

未新增测试；未运行完整单元、集成、E2E、安全、性能、构建、Unity/Blender、渲染或 playtest 套件。未调用 AI、未执行真实作业、未写回生产工程。差异计算、审批、取消/重试等其余路径本轮留待手动检查。
