# 新建项目身份、工程基线与卡片基线

日期：2026-09-07

## 结果

SceneOps 新建文件夹项目现在先排他创建目录和 `.sceneops/project.json`，再初始化并验证独立 Git 根目录，最后用一个 SQLite 事务登记项目及路径。创建接口只有在这些步骤全部成功后才返回项目。文件系统与 SQLite 不能组成同一事务；中断后保留的身份文件会被识别为可恢复项目，用户可从“本地项目”显式恢复。

架构确认仍不安装依赖。对象／组件式或 ECS · Miniplex scaffold 生成后，系统在 `codex/integration` 上创建选择性工程基线提交。提交只包含 `.sceneops/project.json`、`.sceneops/game-architecture.json` 和本次模板的明确文件，不使用 `git add .`，不包含 `pnpm-lock.yaml`、`node_modules`、缓存、运行日志或用户额外文件。正式策划快照来自父提交，本次 diff 不重复修改它。

```text
正式策划 v1
    │
    ▼
游戏工程基线
    │
    ▼
后续已采纳的 integration 提交
    │
    └── 第一次打开新卡片：从此刻最新 HEAD 创建
```

已存在卡片继续使用登记的 branch、worktree 和 `base_commit`，不会随集成分支前进而被重建或改基线。卡片 worktree 通过 Git 历史获得 scaffold，旧的“复制主目录未跟踪文件”实现已删除。

## 项目身份与恢复

`.sceneops/project.json` 只保存 schema 版本、SceneOps 项目 ID、名称和 UTC 创建时间；副本另存 `copied_from_project_id`。文件中没有绝对路径、本机用户名、数据库路径、端口、进程或密钥。

“本地项目”可检查当前浏览目录，并显示以下结果：

- 身份与本机登记一致：直接打开；
- 有身份但无本机登记：显式恢复；
- 原登记路径已消失：选择“移动后的原项目”或“作为副本”；
- 原登记路径仍存在：禁止移动，只允许显式登记为副本；
- 没有身份文件：显示已有工程采用流程尚未接通。

本机登记仍在但根目录已经消失时，最近项目会显示“原登记目录不可用”，并引导用户浏览移动后的目录检查身份，不会新建同名目录。

确认移动会验证独立 Git 根目录、保留原项目 ID、更新 SQLite 路径，并且不重写身份文件或 Git 历史。确认副本会分配新项目 ID、记录来源并登记为 `existing_unadopted`。该状态不能进入现有开发旅程，界面明确说明不会自动提交、重建或复制源码；完整的已有工程采用属于下一里程碑。

旧数据库记录迁移为 `legacy`，即使没有 `project.json` 仍可按原路径读取。系统不会为它静默生成身份、基线或重写工作树。

## 公开接口

- `POST /api/workspace/folder-projects/inspect`：读取目录身份和本机登记关系；
- `POST /api/workspace/folder-projects/recover`：执行明确选择的 `restore`、`move` 或 `copy`；
- `FolderProject.project_kind`：`sceneops_created`、`existing_unadopted` 或 `legacy`；
- `GameProjectScaffold`：保存架构版本、策划版本、项目来源和工程基线提交。

## 验证

23 项定向后端烟测通过，覆盖：Git 初始化失败不返回项目、SQLite 登记中断后恢复、重复身份冲突、移动保留 ID、副本分配新 ID、旧项目兼容、选择性 baseline diff、新卡使用最新 integration HEAD、旧卡保持原 base，以及 worktree 只继承 Git 跟踪内容。

6 项定向 UI 烟测和 2 项 Project Intake 合同测试通过，覆盖副本未采用状态、显式“查看项目身份”入口和版本化身份 Schema。OpenAPI 和 TypeScript 网络类型已重新生成。4301/8301 本地预览使用原数据目录重启后，浏览器实际调用检查接口并显示无身份目录状态。

## Limitations

- 已有工程采用、已有仓库接管、历史元数据迁移和依赖管理尚未实现。
- 架构确认不运行 `pnpm install`、类型检查、构建或预览；这些仍由后续明确授权的运行步骤执行。
- 已有卡片吸收新的 integration 内容需要以后提供明确 merge 或 rebase 操作，本轮不会自动执行。
- 本轮没有重新执行真实 Agent、生成工程依赖安装、游戏构建或游戏预览；这些能力的既有验证记录仍见 `GAME_CODE_ARCHITECTURE_MILESTONE.md` 和 `GAME_PROJECT_RUNTIME_MILESTONE.md`。
- 根 TypeScript 全量检查仍被仓库已有跨模块诊断阻断；本轮修改文件的过滤结果没有新增诊断。Project Intake 的全量 Node 测试入口仍受既有 `.tsx` ESM 加载配置阻断，合同测试已用其独立入口通过。
