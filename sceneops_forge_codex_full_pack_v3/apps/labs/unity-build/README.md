# 工作台 08 — Unity 与构建发布

此入口组合 `engine-unity`、`build-release` 和仓库内 Unity Package。打开即进入用户明确选择的 Build 工作台，不替代总 Shell 的纯对话首页。

## 独立启动

工作树：`/Users/isduanna/.codex/worktrees/d13d/10w`。
要求 Node 22.12+、pnpm 11.13.0、Python 3.9+。

首次安装（在应用根 `sceneops_forge_codex_full_pack_v3`）：

```bash
pnpm --dir apps/labs/unity-build install --ignore-scripts
python3 -m venv apps/labs/unity-build/.venv
apps/labs/unity-build/.venv/bin/python -m pip install -r apps/labs/unity-build/requirements.txt
```

启动：

```bash
pnpm --dir apps/labs/unity-build dev
```

- Web：[http://127.0.0.1:4317](http://127.0.0.1:4317)
- API / OpenAPI：[http://127.0.0.1:8317/docs](http://127.0.0.1:8317/docs)
- 一条命令启动所需 Vite 和 FastAPI，无需启动其他工作台。
- Ctrl+C 只结束本命令创建的两个子进程。
- 端口占用时明确报错，不结束占用进程。可以显式配置：`WEB_PORT=4417 API_PORT=8417 pnpm --dir apps/labs/unity-build dev`。
- 已有 Python 依赖环境可设置 `PYTHON=python3`，本轮烟测采用该方式。

本 lab 有独立 `pnpm-workspace.yaml` 和锁文件，避免 pnpm 11 的自动安装改动应用根锁文件。根 `pnpm lab unity-build` 也可转发启动。共享骨架来自 `4f3416e`；未提交任何本地生成的根锁文件。

## 手动检查

1. “构建矩阵与产物”：切换 Remember Home / Warehouse Escape；查看四 profile、A/B 记录、固定完成进度、构建来源与测试证据；展开清单或导出 mock JSON。
2. “Unity 能力与命令”：查看 disconnected/blocked 原因、固定版本、白名单、对象稳定 ID；按 build / inspect 等词筛选原始 mock 命令记录。
3. “候选与发布提案”：查看 ReleaseCandidate、A/B 一致性、七类 mock 证据、待审批角色。编辑标题、目标、发布说明和 ChangeSet JSON；点击“仅预览 ChangeSet”查看原服务 dry-run；“保存本地提案”会更新 revision 并持久化。
4. 页面刷新后重新进入提案可查看保存内容。两个示例的草稿分别保存。
5. 手动错误检查（本轮未执行）：把 JSON 改坏应显示格式错误；把 base_version 改为旧版本应显示校验错误；两个窗口保存同一旧 revision 应返回 409；停止 API 后刷新应出现断连和重试入口。

“发布 / 部署”始终 disabled / blocked；没有外部执行路由。本工作台不会授予真实批准，也不会把 mock 候选转为生产候选。

## 数据和接口

- `modules/build-release/fixtures/workbench-records.mock.json`：两套完整 A/B 构建记录，来自原模块 fixture 构造函数的静态导出，包含 matrix、run、manifest、artifact、gate 和 mock 批准变更锚点。没有运行测试函数、Unity 或构建任务。
- `modules/engine-unity/fixtures/mock/command-results.json`：原始 Unity 对象/命令 fixture。
- `.local/proposals.sqlite`：此 lab 的本地持久草稿，不进 Git。`UNITY_BUILD_DB` 可显式指定另一数据库路径。
- `GET /api/unity-build/snapshot`：经既有 `BuildReleaseService.record_build/create_candidate` 校验/分析后的读模型，组合 engine 公共工作台服务。
- `POST /api/unity-build/preview`：经原 `UnityEngineService.preview` 的真实本地校验，结果 `planned`，没有外部 runner。
- `PUT /api/unity-build/proposals/{slug}`：校验 ChangeSet 后以 SQLite 事务和 revision 比较保存；始终 `planned/pending`。
- FastAPI/Pydantic 为网络合同源；`api.generated.ts` 由 OpenAPI 生成，组件通过唯一 `openapi-fetch` client 和 TanStack Query 访问 API。

重新生成类型（不是测试或应用构建）：

```bash
npm install --prefix apps/labs/unity-build/contract-tools --workspaces=false --ignore-scripts --no-audit
pnpm --dir apps/labs/unity-build generate:api
```

`openapi-typescript 7.13.0` 只接受 TypeScript 5 peer，故生成工具独立安装 TS 5.9.3；实际前端仍使用 TS 6.0.3。没有强制忽略 peer 冲突。

## 本轮验证记录

2026-09-05（Asia/Shanghai）：

- 导入/启动：FastAPI application startup complete，Vite 8.0.0 ready；默认 4317 / 8317 启动成功。OpenAPI 类型生成成功。随后完成隔离 .venv 安装，使用文档默认启动命令再次确认两个服务 ready（只检查启动，未重跑主路径）。
- 浏览器启动：显示中文 BuildMatrix、四 profile、两条 mock A/B 记录、产物和 blocked 提示。
- **唯一最小主路径**：打开“候选与发布提案”，将标题改为“本地主路径烟测 · 未执行构建”，点击一次“保存本地提案”。UI 显示 revision `0 → 1`、保存时间 `2026-09-04T20:46:59.657048Z`，状态继续 `planned / pending`；发布按钮保持 `blocked`。请求返回 HTTP 200，保存后 Query 重新读取。
- 未重复执行该路径，未运行测试 runner。第一次浏览器请求早于服务 ready，返回 connection refused；服务 ready 后重新打开成功。
- `git diff --check`：无空白错误。
- 首次安装曾因 uvicorn 0.40.0 不支持宿主 Python 3.9 失败；已固定为本轮实际启动使用的 0.39.0，隔离环境安装成功。
- 完整单元/集成/E2E/安全/性能测试、typecheck、前端 production build、C# 编译、Unity、打包、构建、渲染、AI playtest、发布、部署：**not run / pending approval**。
- 旧模块提交中的测试结果不作为本轮组合验证证据。依赖安装的默认 npm 输出曾附带审计摘要，不代表运行过安全测试套件；未执行 audit fix。

## Limitations

- 所有构建与证据为 mock；固定 100% 是历史 fixture 展示，不是实时进度。产物 URI 和大小为元数据，没有可玩程序或真实下载。
- 原 release fixture 使用 Unity 6000.0.15f1，engine package 固定 2022.3.62f3c1；界面保留各来源真实声明。这两套旧 fixture 不是相同 Unity 构建链的 live 证明。真实构建 intake 仍需后续 Unity 版本对齐和可信来源适配。
- Unity 对象/ChangeSet 的钥匙来自原 engine fixture，与项目下拉的 release 构建记录分别标示；新提案未被加入候选的已批准变更。
- 真实 Unity、Git/source authority、审批服务、部署适配器、SSE 均未连接。所有外部执行保持 blocked，不影响本地提案。
- 候选在进程内由不可变 fixture 重建；只有可编辑提案持久化。不是生产数据库或多人发布系统。
- 入口没有复制 core/runtime，也没有运行全局模块 catalog；总 Shell 可通过本模块公共 export 组合。根共享工具链只引入既有公共提交，没有自行修改。

## Shell 合并说明

本 lab 的独立 workspace/锁文件仅用于隔离首次安装。总 workspace 合并时可以由 Shell 负责人统一锁文件并取消这个局部 workspace；需要保留 React/ReactDOM 19.2.8、TS 6.0.3、Vite 8.0.0、TanStack Query 5.90.21、openapi-fetch 0.17.0。模块公开的 `UnityBuildWorkbench` 是显式 Build 入口，不能自动打开到全局 chat-only 首页。

## 第三方依赖

React、ReactDOM、Vite、TanStack Query、openapi-fetch、openapi-typescript、FastAPI、uvicorn 为 MIT；TypeScript 为 Apache-2.0；Pydantic 为 MIT。前端依赖用于既定 React/Vite 技术路线及类型化 API，不引入另一套 UI 框架。
