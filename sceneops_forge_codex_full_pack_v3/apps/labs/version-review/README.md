# 09 · 版本评审工作台

工作树：`/Users/isduanna/.codex/worktrees/1000/10w`。业务 UI、HTTP transport、演示适配器属于 `modules/version-collaboration`，本目录只组合公开入口并启动进程。

## 安装与启动

Node 22.12+、pnpm 11.13.0、Python 3.9+。应用根：

```sh
cd /Users/isduanna/.codex/worktrees/1000/10w/sceneops_forge_codex_full_pack_v3
pnpm --filter @sceneops/lab-version-review... install --lockfile=false
python3 -m venv apps/labs/version-review/.venv
apps/labs/version-review/.venv/bin/python -m pip install -e modules/version-collaboration/backend 'uvicorn>=0.30,<1'
PYTHON="$PWD/apps/labs/version-review/.venv/bin/python" pnpm --dir apps/labs/version-review dev
```

已安装 FastAPI/Pydantic/Uvicorn 的环境可以直接运行 `pnpm --dir apps/labs/version-review dev`。等价共享入口：`pnpm lab version-review`。

- Web：<http://127.0.0.1:4318>
- API / OpenAPI 文档：<http://127.0.0.1:8318/docs>
- 端口覆盖：`PORT=4418 API_PORT=8418 pnpm --dir apps/labs/version-review dev`

只绑定 `127.0.0.1`；占用明确报错，不杀其他进程。Ctrl+C 只关闭本启动器创建的 Web/API 子进程。不会自动安装、部署、合并或运行测试。

## 数据与操作

数据源：`modules/version-collaboration/contracts/examples/remember-home-review.json` 与 `warehouse-escape-review.json`。输入固定，服务生成的会话 ID 与审计时间为本次运行的新值。存储为进程内 SQLite，不写真实 Git 仓库或远端。刷新页面保留当前进程数据，重启 API 恢复演示初始状态。

1. 左侧选择项目；查看基线 / 目标提交及文件、语义、视觉、行为差异。
2. 点击语义对象或右侧选择锚点，输入评论并发布。记录保留精确版本、修订和 diff ID。
3. 填写理由并记录接受 / 要求修改 / 阻断决策；查看决策历史。
4. 填写理由后点击 MOCK 通过或拒绝，查看审批历史及绑定证据。正式审批规则仍由现有服务校验，阻断原因显示在界面。

视觉视图将 fixture 的 2×2 灰度像素原样放大，并显示实际差异指标，不是新渲染画面。文件视图是统计和 LFS 指针，不提供不存在的源文件补丁。行为视图是预置记录及本地差异计算，没有运行游戏。

## 边界

评论、决策、差异计算和审计存储是真实本地执行，但因输入与身份为演示数据，领域记录统一标为 MOCK。审批来源为隔离的 MOCK 注册表，只接受精确 binding；没有正式审批系统。远程锁、回滚执行、自动提交、发布、Unity、Blender、真实 Git 操作均未启用。API 不授予 `version:lock` 或 `version:rollback`。

无需 AI 即可完成此工作台的评审流程，因此没有伪造 AI 输出或模型下拉框。以后接入 AI 时遵循用户要求：codebuddycli + 前端模型选择，禁止 bridge/cbridge。

## 本轮验证

2026-09-05，本机 Node 22.22.0 / pnpm 11.13.0：

- 生成 OpenAPI 与 TypeScript 操作签名成功；没有执行 contract check 或测试套件。
- 默认启动命令成功：Uvicorn application startup complete；Vite 8.0.0 ready；Web 4318 / API 8318。
- 一条最小本地主路径：打开 Remember Home → 选择 `hero.door` → 发布锚定评论 → 页面返回评论与审计事件。POST comments 返回 201，随后 GET comments/activity 返回 200，活动数 1 → 2。已观察桌面布局。
- 首次沙箱端口探测被系统权限限制；在授权环境启动成功，没有实际端口冲突。
- not run / pending approval：单元、集成、E2E、安全、性能、完整类型检查、构建、其他项目/差异页/决策/审批交互验证、Unity/Blender/render/playtest。未把这些路径合并进烟测。

## 共享集成

已引入 Shell 公共启动骨架 `4f3416e830e1b99a0c2a2df18150d198ac7f21ae`（本工作树 cherry-pick 为 `8dbe0d5`）；没有重写根启动器或根锁文件。独立包使用 `workspace:*` 公开依赖，React/ReactDOM 19.2.8、TypeScript 6.0.3、Vite 8.0.0。后续由 Shell 在共享安装时收录锁文件；本轮没有根锁文件更改。

本机 pnpm 在工作树顶层生成了未跟踪 `.pnpm-store/` 缓存，本轮不提交、不删除，也不改其他组的根 ignore。需要统一忽略规则时交由 Shell 处理。
