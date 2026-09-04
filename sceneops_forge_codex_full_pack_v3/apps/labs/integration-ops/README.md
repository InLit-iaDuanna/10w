# 集成状态与运行日志

工作台 11，`lab-id=integration-ops`。独立 React Web + FastAPI 组合入口，复用 `integration-center`、`observability` 公共服务。界面与业务代码位于原模块中；本目录只负责依赖、启动、鉴权组合和 Web 挂载。

## 首次安装

需要 Node 22.12+、pnpm 11、Python 3.10+ 和 uv。从应用根 `sceneops_forge_codex_full_pack_v3/` 执行：

```bash
pnpm --dir apps/labs/integration-ops install --ignore-workspace
uv venv apps/labs/integration-ops/.venv
uv pip install --python apps/labs/integration-ops/.venv/bin/python -r apps/labs/integration-ops/requirements.txt
```

首次安装需访问软件包仓库；后续启动不下载依赖。React/ReactDOM 19.2.8、TypeScript 6.0.3、Vite 8.0.0 与 Shell 骨架版本一致。React、Vite、TanStack Query、openapi-fetch、openapi-typescript 使用 MIT 许可；FastAPI、Pydantic 为 MIT，Uvicorn 为 BSD-3-Clause。TanStack Query 管理服务状态；openapi-typescript 从后端 OpenAPI 生成网络类型。

## 独立启动

```bash
pnpm --dir apps/labs/integration-ops dev
```

- Web：<http://127.0.0.1:4320>
- API：`127.0.0.1:8320`，由 Web 的同源代理访问。
- Ctrl+C 只关闭本命令启动的 API 和 Web 子进程。
- 端口占用时明确失败，不结束其他进程、不自动换端口。可显式配置：

```bash
WEB_PORT=4420 API_PORT=8420 pnpm --dir apps/labs/integration-ops dev
```

`PYTHON` 可显式指定另一 Python 解释器的绝对路径。若宿主禁止监听端口，终端会显示实际权限错误，需要宿主允许本地监听；本脚本不更改权限配置。

## 可手动验证

1. 查看五类集成状态，点击 Unity / Git / ComfyUI 展开版本、能力、命令标识与原因。
2. 在 Worker 中点击“查看 Mock iOS build”，检查任务筛选、45% 固定进度及两条 Unity 日志。
3. 展开日志，检查 project/run/job/correlation/causation，点击“仅看此关联链路”或“查看本地证据”。证据在页面对话框中展示，按项目和固定 artifact ID 查询，不读取任意文件路径。
4. 切换“仓库逃脱”项目，查看独立的一条日志；任务/关联/搜索筛选会清除。该项目无 Worker 与进度，显示明确空态。
5. 搜索消息或结构化字段，切换日志级别；查看 Git 的 `token=<redacted>` 与路径脱敏样例。
6. 下载诊断 ZIP。服务端复用现有双重脱敏逻辑，包内包含 `health.json`、`logs.jsonl`、`manifest.json`。导出只受项目和 correlation 限制，不受任务、文本和级别限制，界面已明确说明。

## 数据与边界

- 全部外部集成、Worker、作业与日志为 **Mock**，固定模拟时间 `2026-09-04T00:01:00Z`；“已连接”表示该时刻样例状态，绝不代表当前本机工具健康。刷新不会推进模拟任务。
- API 的本地读取、筛选与 ZIP 生成是真实执行的本地服务操作；这不会把样例的执行模式改为 Live。
- Cached 合同保留，但未提供任何假冒真实历史运行的数据。真实适配器和持久传输为 Planned；工具操作在此工作台 Blocked。
- 数据在进程内隔离，重启恢复固定样例。健康与 Worker 复用模块 `contracts/examples/*.mock.json`；日志/进度及两项目注册位于 `integration_center/workbench_demo.py`。
- Vite 与 API 仅监听 127.0.0.1。启动器生成临时凭据，通过服务端代理注入；不打印、不写文件、不发送给浏览器。API 使用只读演示 principal，仅授权两个演示项目及查询/诊断导出。外部日志写入、Job 恢复与工具启动未授权。已有恢复状态机保持不变。
- 没有读取真实凭据，没有启动或探测 Unity、Blender、ComfyUI、Git 远端及无关服务。
- 本入口是用户主动打开的独立运维工具，不实现或替换 Shell 的纯对话首页、Dockview 或 core kernel。

## 公共接口与类型生成

新增 `integration_center.create_demo_workbench()`、`create_workbench_router()` 与 `OperationsWorkbench`；新增只读 `/api/v1/integration-ops/snapshot` 和 `/evidence/{artifact_id}`。

前端通过模块公共入口懒加载 `loadIntegrationOpsWorkbench()` 和 `loadLogPanel()`。网络调用集中在模块 workbench API client，不在组件中直接 fetch。Pydantic/OpenAPI 是网络类型来源，生成文件已提交：

```bash
pnpm --dir apps/labs/integration-ops generate:client
```

这是类型生成命令，不运行构建或测试。

## 本轮验证记录

- 启动检查：`pnpm dev` 成功，Uvicorn `Application startup complete`，Web 在 4320、API 在 8320；沙箱首次监听失败后使用宿主授权启动成功。
- **唯一最小本地主路径烟测，通过**：浏览器打开工作台 → 点击 Unity Worker 的作业 → Worker 3→1、日志 5→2、作业进度显示 45% → 展开日志 → 打开 `evidence_job_unity_build_mock_01`，显示同项目的两条 Mock 证据记录。浏览器截图确认日志布局正常。
- 诊断下载、其他项目切换、权限失败分支、完整单元/集成/E2E、安全、性能、类型检查和编译构建均 **not run / pending approval**。本轮没有执行外部工具测试，也未新增测试套件。此前模块测试结果不作为本入口验证证据。

## Shell 整合说明

已只读对齐共享骨架提交 `4f3416e830e1b99a0c2a2df18150d198ac7f21ae` 的 `dev` 接口和版本；未修改根 workspace、根锁文件或根启动器。

Shell 合入后可直接使用 `pnpm lab integration-ops`。请由 Shell 负责人将本 lab 的依赖纳入根锁文件，并为业务模块声明 React / TanStack Query / openapi-fetch 的共享依赖；独立入口当前使用本 lab 的依赖与 Vite 别名解析。无需引入第二套 core/runtime。
