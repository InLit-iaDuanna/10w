# 统一本地 API

应用根 `pnpm dev` 启动一个 FastAPI；入口 `services.api.app:create_app`。安装依赖为独立步骤：`python -m pip install -r services/api/requirements.txt`。默认端口 8300，Web 4300。只允许 localhost/127.0.0.1；私有 API 需要启动器注入的 `X-SceneOps-Token`，不在浏览器脚本中公开凭据。写入需要匹配 Origin 和 JSON。

## 公共接口

- `GET /api/health`：只报告本地 API 状态，不启动外部健康探测。
- `GET /api/workspace/projects`：`{projects: Project[]}`，初次为空。
- `POST /api/workspace/projects`：`{name}`，返回新 `Project`，不会加载示例。
- `GET /api/workspace/modules`：`{modules: WorkbenchRegistration[]}`，11 个工作台。
- `GET /api/workspace/projects/{project_id}/modules/{module_id}`：已保存草稿；首次 `revision:0,payload:{},sample_id:null`。
- `PUT` 同路径：`{expected_revision,payload}`，只保存草稿，版本冲突 409。
- `POST` 同路径 `/sample`：`{sample_id,expected_revision}`，人工导入静态 Mock 样例声明；不运行 demo 流程、测试、AI 或外部工具。已导入的样例不可被此操作覆盖。

旧领域 URL 保持兼容，统一入口必须增加 `X-SceneOps-Project`，不存在或未选择项目明确报错。每个项目拥有独立路由/服务实例，不能借用同一个 lab session UUID 读取另一个项目。UI/audio/VFX 提案字典为每个项目独立闭包；world/logic 提案计算无共享领域记录。旧独立工作台继续使用自己的组合根与权限。

AI 的 `/api/ai/*` 由 conversation-home 唯一实现，旧 `/v1/design-ai/*` 委托同一 CodeBuddy provider。概念旧 `/api/ai/*` 不重复注册。

## 本地保存边界

`SCENEOPS_DATA_DIR` 默认应用根 `.local`。主 `sceneops.sqlite3` 保存项目目录、显式草稿、制作计划、角色版本及聊天/模型设置（后两类表由 conversation-home 拥有）。评审沿用模块原 SQLite repository，构建提案沿用原 CAS repository，位于 `.local/projects/<project_id>/reviews.sqlite3` 与 `build-proposals.sqlite3`，防止旧表的无项目主键混用。OpenAPI 模板只使用临时目录，不建立虚构项目。

没有自动迁移旧 demo 数据。已保存的草稿不是审批、构建或测试证据。概念/渲染/UI/audio/VFX 的交互会话仍是模块原内存服务；用户显式保存的编辑器草稿可重启恢复，但运行时缓存/临时提案不作为持久生产记录。渲染集成初始 `jobs:[]`，仅显示静态 brief/配方，不自动 `plan` 或 `load_fixture`。评审/构建的手动样例来自明确标记 Mock 的记录，不是当前执行的证明。

## 验证

本后端代理没有启动服务、执行测试或业务动作。维护了项目持久化、项目隔离、版本冲突和未知项目测试，均未运行。由主代理仅进行一轮启动、健康、注册、空态和模型目录烟测；其余路径由用户手动测试。
