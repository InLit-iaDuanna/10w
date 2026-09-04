# 工作台 02：项目设计与生产计划

可独立运行的中文 React Web，组合 project-intake、design-room、production-planner 的公开入口。新项目草稿、隔离扫描示例、结构化 FeatureSpec、版本差异、生产任务图、任务编辑/分配、依赖、blocker 和里程碑在同一工作台中。

## 首次安装与启动

要求 Node 22.12+、pnpm 11.13.0、Python 3.9+。本工作树已安装前端依赖，宿主已有匹配 Python 包。

从应用根 `sceneops_forge_codex_full_pack_v3/` 执行：

```sh
pnpm --dir apps/labs/project-planning install
python3 -m venv apps/labs/project-planning/.venv
apps/labs/project-planning/.venv/bin/python -m pip install -r apps/labs/project-planning/requirements.txt
PYTHON="$PWD/apps/labs/project-planning/.venv/bin/python" pnpm --dir apps/labs/project-planning dev
```

若宿主已安装 requirements 中的 Python 依赖，直接执行：

```sh
pnpm --dir apps/labs/project-planning dev
```

Web：http://127.0.0.1:4311；API：http://127.0.0.1:8311/docs。一条 dev 命令启动两者；Ctrl+C 仅结束本命令启动的进程。
端口占用会报告错误。可显式指定 `WEB_PORT=4411 API_PORT=8411 pnpm --dir apps/labs/project-planning dev`，不会终止其他进程。

Vite 8.0.0 与 Shell 工具链对齐。初次尝试 Vite 7 时 pnpm 拒绝 esbuild 安装脚本；升级至 Vite 8 并重新生成本 lab 自有锁文件后，依赖安装成功，无 esbuild，无权限配置修改。旧安装目录与锁文件保留在 `/tmp/project-planning-*`；pnpm 自动产生的待决脚本配置未提交。

## 手动验证

1. 填项目名、brief、平台和目录，点击“从 brief 创建草稿”；字段先显示 inferred。
2. 确认名称、平台和目录，进入设计规格。也可用“导入仓库逃脱扫描示例”，查看明确 mock 的扫描结果并确认字段。
3. 编辑目标、玩家价值、输入/输出、Given/When/Then、边界情况、交付物和测试要求。确认模板假设；保存版本可展开最近差异。
4. “确认设计 → 创建生产计划”：本地 API 生成 12 个专业任务、21 条依赖、6 个里程碑。
5. 点击任务图或任务列表，编辑任务标题/说明与负责人。展开依赖编辑，增删依赖；结构错误会显示 blocker 并阻止确认。
6. 调整里程碑名称与必需任务；确认当前计划（mock 审批）。推进任务仍使用原领域状态机和证据要求。
7. 输入 blocker 原因，关联解决记录后再恢复就绪。外部执行没有伪造成功入口；缺少证据时完成操作显示错误。

## 实现与公共接口

- lab 仅做启动、React/Suspense/QueryProvider 组合与视觉主题；业务组件都在所属 module 内。
- `loadIntakePanel`、`loadDesignPanel`、`loadPlanningPanel` 是新增的公开 React loader；不会让旧 Node headless API 强制加载 React。
- 项目与设计调用原 runtime 的 typed commands（包含模块权限、用户/assistant 区分、假设确认、准备度、版本）。没有复制业务 kernel。
- `projectFeatureForPlanning(DocumentVersion<FeatureSpec>)` 消费 design-room 公开类型，输出 planner 的 Pydantic 生成投影；固定全专业模板是明确的规划选项，不声称 LLM 自动理解专业拆分。
- `create_planning_lab_app` 组合原 `ProductionPlannerService`、公开 FeatureSpec provider 端口及隔离内存 repository。新路由包含 expected_version；锁保护版本检查与变更。原有 ChangeSet/审批/证据和依赖规则均保留。
- Pydantic 源：`modules/production-planner/backend/src/sceneops_production_planner/lab.py`；生成合同、OpenAPI 与唯一 lab transport：`backend/scripts/export_lab_contracts.py`。组件注入 `PlanningClient`，不直接 fetch。
- API 前缀 `/v1/planning-lab`：create、edit、assignment、dependencies、milestones、approve、transition、resolve。查询复用 `/v1/production-planner/plans/{id}` 与 `/graph`。
- 后端计划和图由 TanStack Query 管理；浏览器本地设计会话由原内存 runtime 管理。
- 确定性内容：project-intake 的 `warehouseEscapeScanReport`、设计面板显式固定模板和 planner 既有 generation。用户新会话 ID 使用 UUID，内容与规划算法不依赖随机生成。

## 精确验证记录

2026-09-05，本工作树：

- 依赖安装：pnpm install 成功（Vite 8.0.0）；Python 导入 FastAPI 0.128.8 / Pydantic 2.13.2 / Uvicorn 0.39.0 成功。
- 三个模块公开 TypeScript 入口的 Node strip-types 导入检查：通过。
- 启动：`pnpm --dir apps/labs/project-planning dev` 成功，Web 4311、API 8311 仅绑定 127.0.0.1；浏览器真实 React 初始页可见。
- **唯一最小主路径烟测：通过。** 浏览器从默认钥匙与家门 brief 创建草稿 → 看见 inferred → 确认关键字段 → 编辑玩家价值为“找到钥匙并获得明确的开门反馈” → 确认模板假设 → 确认设计并创建生产计划。真实 UI 显示 `mock / v1 / draft_unconfirmed`、12 任务、21 依赖、6 里程碑、关键路径 60h predicted、0 结构 blocker。
- 主路径结果截图已目视检查；最后把公开入口改为懒加载后，只重新确认初始页可加载，没有重复跑主路径。
- DTO/OpenAPI/client 生成已执行，属于代码生成，没有执行导出脚本中的既有测试/fixture suite。
- 新增 `test_lab.py` 覆盖创建编辑、旧版本冲突与禁止冒充 live，**not run / pending approval**。
- 原单元、合同、集成、E2E、安全、性能、typecheck、编译构建、Unity、Blender、渲染、AI playtest 均 **not run / pending approval**。任务编辑、审批、依赖与里程碑等其他交互留给用户手测，没有扩大烟测范围。

## Limitations

- 全部会话明确标记 mock；本地命令和领域计算实际执行，但没有可信生产身份或真实外部审批服务。live/cached 创建仍由原服务阻断。
- 新建/导入记录存在浏览器内存，刷新会清空；计划存在 API 内存，重启清空。本 lab 不写用户项目文件，没有生产持久化。
- 导入仅提供 deterministic mock scan；未接 Unity/Blender 实际扫描。外部构建、资产生成和测试为 planned/blocked。
- 设计面板当前编辑一条主路径验收、一个边界情况/交付要求；完整 Bible/GDD 仍保留原公开 headless 服务，未扩展为本 lab 页面。
- 原正式 editor registry/contribution 描述保持原样；Shell 注册和统一核心 context/client 需 Shell 组后续接入，未声称完整主应用已集成。
- 本 worktree 未引入/更改根 workspace、共享锁文件或核心 runtime；Shell 只需复用本 lab dev 接口，并在统一锁文件纳入声明的依赖。可删去整合后的 lab 锁文件，由 Shell 组决定。
