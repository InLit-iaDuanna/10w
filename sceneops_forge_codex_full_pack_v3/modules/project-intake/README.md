# Project Intake

Project Intake 把“一句项目想法”或“扫描现有项目”的结果转换为可检查、可确认的项目入口记录。它不接触生产文件；扫描器必须先通过公开的 `ProjectScanAdapter` 把 Unity、Blender 或其他工具的数据归一化。

## 用户与数据

面向制作人、游戏设计师和技术负责人。模块拥有项目入口草稿、字段来源/确认状态、扫描摘要和准备度问题。它记录：目标平台、引擎、DCC、项目根目录、团队角色、风格目标、性能预算和集成需求。

关键字段 `targetPlatforms`、`projectRoots` 只有用户明确输入或执行确认命令后才是 `confirmed`。对话提取和扫描检测到的值都是 `inferred`；没有值则是 `missing`。

## 公开能力

- Editor：`project.intake`
- Commands：`project.intake.create_new_draft`、`project.intake.draft_from_conversation`、`project.intake.scan_existing`、`project.intake.confirm_field`
- Events：`project.intake.drafted@1`、`project.intake.field_confirmed@1`
- 公开入口：`frontend/src/index.ts`
- 权限：读取 `project:read`；新建/确认 `project:write`；扫描还需 `project:scan`

对话命令返回结构化 `workbench.open_editor` 动作。它创建的只是应用内草稿，不会改写项目文件，也不会启动生产任务。

## 扫描与降级状态

扫描 adapter 必须报告健康状态和真实执行模式：`live`、`cached`、`mock`、`planned` 或 `blocked`。离线、缺权限、模块关闭、路径无效和 adapter 失败都有中文可见状态。fixture adapter 是确定性的 `mock`，绝不标记为 live。

当前规格起点没有 `core-kernel`、`module-runtime`、ForgeShell 或生成式模块目录，因此本模块提供可独立测试的公开贡献对象和无框架 editor view model。接入真实 Dockview/React editor、生成 catalog 与统一命令总线属于前置模块恢复后的 **planned** 集成，不在这里伪造。

## 运行测试

```bash
cd modules/project-intake/frontend
npm test
```

fixtures：`findMyWayHomeNewProject` 覆盖新项目；`warehouseEscapeScanReport` 覆盖现有项目的部分扫描。JSON 合同示例位于 `contracts/examples/`。

## 已知限制

- 仓库尚无持久化/API 组合根，当前 repository 是可替换的内存实现。
- 本模块不实现 Unity/Blender 扫描；真实扫描由后续 integration adapter 实现公开协议。
- 本模块不创建生产任务，准备完成后仅发出 typed event 供 `production-planner` 消费。
