# Conversation Home

`conversation-home` 提供 SceneOps Forge 的首屏：只有 `assistant.conversation`、简洁的项目/场景上下文、对话记录与输入框。它不实现 Dashboard，也不实现工具本身或 Dockview 布局引擎。

## 面向用户

- 首次创建或导入项目的制作人、设计师与美术；
- 通过对话召唤专业工具的日常用户；
- 需要明确审批、执行模式与失败原因的审核者。

## 公共 Editor

| ID | 标题 | 默认位置 | 最小尺寸 | 实例 |
|---|---|---|---|---|
| `assistant.conversation` | 对话 | center | 320 × 280 | singleton |

Editor 通过 `frontend/src/index.ts` 懒加载。Home fixture 只包含这个 Editor；左、右、上、下 Drawer 初始均为 `hidden`，并明确禁止额外模块自动打开。

公开入口还导出 Assistant action 类型/validator/coordinator、`ConversationController`、`ConversationRepository`、typed `ConversationTransport`、`ConversationAttachmentStager`、`createConversationEditorRuntime` 和 Home startup fixture。其他源码路径均为模块内部实现。

## Assistant action 合同

本模块验证并转交以下已有/预期 Workbench 命令：

- `workbench.open_editor`；
- `project.create`；
- `feature.create`；
- `workflow.run`；
- `artifact.open`；
- `issue.open_backpin`；
- `changeset.approval.request`。

Action 的 `type` 就是 Workbench command ID。模块不解释自然语言来执行工具，也不复制命令 handler。聊天卡片、普通按钮、菜单和命令搜索都通过注入的同一个 `WorkbenchCommandBus`。

打开工具时总是先请求布局预览。只有显式确认后才会调用 `execute`，并且执行前再次检查权限、集成状态和审批条件。

`project.create`、`feature.create` 和 `workflow.run` 的 input 必须引用已经建立的 `changeSetId`；本模块不会把 AI 文本直接升级成生产写操作。是否需要人工批准继续由 Core 的审批策略决定，且在真正执行前重新检查。

## 拥有的数据

- 版本化 `ConversationRecord`；
- 消息、附件元数据与结构化卡片；
- Project scope 与临时 Pre-project scope 的存储键；
- 当前 `live` / `cached` / `mock` / `planned` / `blocked` 模式。

对话记录由 `ConversationRepository` 管理，不复制到 Dock layout；Editor local state 只保存未发送草稿和已暂存的附件元数据。浏览器 `File` 或目录入口先交给注入的 `ConversationAttachmentStager`，React 组件不读取文件内容、不访问项目文件系统，也不自行生成附件 ID。集成健康与 Workbench context 由组合根按公开 runtime 端口注入。

项目对话写入注入的持久存储（浏览器集成为 `localStorage`）；未选择项目时写入注入的临时存储（浏览器集成为 `sessionStorage`）。损坏或不可写的记录会返回结构化失败，不能悄悄重置。

## 结构化卡片

支持进度、产物、错误、审批、打开工具和 Assistant action 卡片。错误卡片保留结构化错误码、可重试标记、缺失权限/集成以及有效的后续命令；产物卡片保留 provenance 和执行模式。

## 集成与降级行为

| 能力 | 当前模式 | 行为 |
|---|---|---|
| 模块逻辑、fixtures、测试 | `mock` | 确定性本地运行，始终显示 MOCK |
| LLM 对话 | `blocked`（本独立起点） | 需要 `llm-provider` 的 typed `ConversationTransport`；不可用时显示原因 |
| Core 命令与权限执行 | `planned` | 等 01 的公开 `WorkbenchCommandBus` 合同落地后接线 |
| Dockview / 四边 Drawer | `planned` | 由 `forge-shell` 消费 Home fixture；本模块不实现其内部机制 |
| Cached replay | `planned` | 合同和显示已支持，尚无真实历史 run 可回放 |
| Live run | `blocked` | 当前工作树没有 API、凭据或外部 adapter，未声称执行过 Live |

## 可访问性与键盘

- `Enter` 发送，`Shift+Enter` 换行；
- 流式响应期间 `Escape` 取消；
- `Ctrl/⌘+K` 转交 Workbench command search；
- 空输入框键入 `/` 转交 slash command search；
- 焦点环、文本状态和 ARIA live region 不依赖颜色表达状态；
- 文件按钮与拖放提供同一附件入口。

## Setup

当前模块测试只依赖 Node.js 22，不安装或调用外部工具：

```bash
cd modules/conversation-home/frontend
npm run smoke
npm test
```

完整应用接线见 `docs/integration.md`。模块运行时合并后，由生成器读取 `module.yaml`，不得手工添加 shell switch case。

## 示例

`contracts/examples/open-scene-view-right.action.json` 展示“在右侧打开 3D 视图”。该 action 只能得到布局预览；确认前不会执行命令。

`frontend/src/fixtures/chat-only-home.fixture.json` 是 fresh launch 的确定性布局 fixture。

## 已知限制

- 独立起点缺少 01 的 core contracts/module runtime 和 03 的 Forge Shell，因此全应用注册、React 挂载、Dockview 交互和真实权限/集成检查尚不能在本分支完成验证。
- 当前没有后端、LLM provider 或真实 cached run；所有测试传输均为明确标记的 `mock`。
- 浏览器组件的 DOM 测试需要主 workspace 的 React、Testing Library 和 Vitest 依赖；本模块先通过同一纯函数和控制器测试覆盖键盘、状态、动作与持久化合同。
