# Design Room

Design Room 把项目意图组织成 Project Bible、结构化 GDD 和可执行的 Feature Spec。三者都使用显式字段、稳定 ID 和状态，而 Bible 与 Feature Spec 另外提供版本与结构 diff；它们都不是不可检查的 Markdown 大字段。

## 公开编辑器

- `project.bible`：游戏目标、目标玩家、核心循环、视听/交互/命名规则、平台预算、禁止修改项和已批准决策。
- `design.gdd`：设计支柱、玩家体验目标、结构化玩法系统、进程、世界结构、经济、失败恢复和依赖。
- `design.feature_spec`：目标、输入/输出、依赖、边界情况、验收标准，以及资产、场景、脚本、UI、音频、VFX、测试需求。

## 命令与安全

对话命令 `design.feature_spec.draft_from_conversation` 只创建草稿，并把模型推断放入 `assumptions`，初始状态一律 `unconfirmed`。它返回统一的 `workbench.open_editor` 动作，不创建生产任务。

AI 修改已有 Bible 或 Feature Spec 时先通过 `design.change.propose` 产生 `DesignChangeSet`，其中包含 base version、前后值、理由、影响、风险、验证与回滚计划以及审批要求。只有持有 `design:approve` 权限的 `design.change.approve` 才能应用；base version 已变化时拒绝应用。

Feature Spec 通过项目入口、内容完整性和未确认假设检查后，才会发出 `design.feature_spec.marked_ready@1`。该 event 是给 Production Planner 的数据边界，本模块不复制排期、任务拆分或里程碑逻辑。

## 公开合同

- Commands：见 `module.yaml`
- Events：`design.project_bible.versioned@1`、`design.feature_spec.versioned@1`、`design.feature_spec.marked_ready@1`、`design.decision.recorded@1`
- 权限：`design:read`、`design:write`、`design:approve`
- 依赖：只使用 `project-intake` 公开入口；不引用其内部文件

## 版本、diff 与决策

Bible 和 Feature Spec 每次保存产生不可变版本快照。diff 使用 JSON Pointer 路径返回 `added`、`removed`、`changed`，顺序确定。决策记录要求先逐项拒绝未选方案并写理由，再接受唯一方案；结果保留所有 alternatives 的处置与理由。

## 测试

```bash
cd modules/design-room/frontend
npm test
```

fixtures 包含 Find My Way Home 的钥匙开门分支，以及 Warehouse Escape 的开关/门/出口规格。JSON 合同示例位于 `contracts/examples/`。

## 当前集成状态

模块逻辑、mock fixtures 和独立测试可运行。由于起点尚无 core runtime、API persistence、ForgeShell 和 Production Planner，真实 React/Dockview 渲染、生成 catalog、服务端持久化和 planner 消费当前是 **planned/blocked by prerequisites**。本文不把它们描述为 live。


## 独立 Web 工作台（本轮新增）

现在可从应用根运行 `pnpm --dir apps/labs/project-planning dev`，访问 http://127.0.0.1:4311。
首次依赖安装、运行事实、手动路径及限制见 [工作台说明](../../apps/labs/project-planning/README.md)。
公开 `loadDesignPanel()` 返回真实 React 懒加载组件；旧 headless view model 与命令保持兼容。

以上旧文中的 React/跨模块规划 blocked 描述仅适用于原始模块交付；本轮独立工作台已连通。
正式 Shell 注册、统一身份与生产级持久化仍未接入，不能将独立 lab 当作已接入完整 Shell。
