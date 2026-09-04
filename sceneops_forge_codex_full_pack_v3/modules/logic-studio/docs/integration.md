# 集成说明

## 后端

在 API 组合根中导入 `logic_studio.router`。公开路由为：

- `POST /logic-studio/graphs/validate`
- `POST /logic-studio/templates/compile`
- `POST /logic-studio/graphs/test-plan`
- `POST /logic-studio/code-changes/propose`
- `POST /logic-studio/code-changes/{change_set_id}/approve`

应用和回滚不暴露为无适配器约束的默认 HTTP 路由。`engine-unity` 到位后，应由
控制平面注入 `UnityCodeChangeAdapter` 并经工作流/权限策略调用
`CodeChangeCoordinator.apply` 或 `rollback`。

## 前端

静态模块目录生成器读取 `module.yaml`，然后从 `frontend/src/index.ts` 导入
`moduleContribution`。六个编辑器都是懒加载，支持跟随全局或固定上下文，并有
loading、empty、ready、failed、offline、permission_denied 状态。它们不导入
Dockview、Unity SDK 或直接 `fetch`。

当前基线缺少共享 `EditorRegistry`、生成 API 客户端和 React 宿主，因此这里只
提供已测试的编辑器定义、序列化状态和视图模型。宿主渲染与 TanStack Query
绑定是 `blocked`；集成时必须使用生成客户端，不能在模块中新增私有 API 客户端。

聊天和按钮统一调用 `logic.editor.open`，由它生成需要确认的
`workbench.open_editor` 动作。Shell 负责权限、模块开关和布局变更确认。

## 事件与工作流

事件 JSON Schema 位于 `contracts/events/`。控制平面接入后，应保留核心事件信封
的 correlation/causation ID 与 UTC 时间。工作流定义位于
`workflows/logic-feature-to-validated-unity.yaml`，C# 分支包含显式人工暂停、
dry-run、编译测试门和失败补偿。
