# SceneOps Forge Codex 全量提示词包

本包针对以下已确认要求：

1. **首页初始只有对话框**，不做传统Dashboard。
2. **屏幕上下左右都可以拖拽拉起工具**，工具可停靠、拆分、标签、浮动、弹出、最大化和保存布局。
3. **采用模块化开发**，每个独立功能位于 `modules/<module-id>/` 单独文件夹。
4. **目标是完整3D游戏生产链**，包含策划、任务、概念、资产、角色动画、场景、逻辑、UI、声音、VFX、AI渲染、Unity、版本协作、AI试玩、构建发布。
5. **Codex作为主代理**，可新开对话、调用Subagent，并按难度路由模型。
6. **代码简洁明确**，前端有完整接入和新增工具文档。

## 最快使用方法

### 1. 把根文件复制到仓库

至少复制：

```text
AGENTS.md
product.md
design.md
architecture.md
MODULE_CONTRACT.md
FRONTEND_INTEGRATION.md
MODEL_ROUTING.md
SUBAGENT_ORCHESTRATION.md
DEFINITION_OF_DONE.md
.codex/
.agents/
PROMPTS/
TEMPLATES/
```

### 2. 打开仓库并发送总任务

将 `MASTER_CODEX_PROMPT.md` 全文发给Codex。

主任务会要求Codex：

- 审计仓库；
- 创建状态与执行计划；
- 调用Subagent；
- 先建立模块运行时和聊天首页；
- 再按依赖实现完整生产链；
- 持续测试和集成；
- 最终完成主Demo、其他游戏Demo和比赛交付。

### 3. 允许多代理

项目内已经包含：

```text
.codex/config.toml
.codex/agents/*.toml
```

如当前Codex客户端支持项目级自定义代理，它会加载这些Agent。若某个模型在你的账号暂不可用，让Codex按照 `MODEL_ROUTING.md` 使用对应Fallback，不要改任务难度标准。

### 4. 新开对话时

不要只说“继续”。复制：

```text
TEMPLATES/NEW_CONVERSATION_HANDOFF.md
```

填写当前分支、目标模块、失败命令、允许修改文件和验收标准。

### 5. 分阶段手动推进时

按 `PROMPTS/` 数字顺序执行。每个文件都可以独立用于一个新Codex对话。

建议顺序：

```text
00 审计
01 核心合同与模块运行时
02 只有对话的首页
03 四边拉起与Dock工作台
04-06 项目、策划、计划、概念
07-13 资产、角色、场景、逻辑、渲染、Unity
14-16 版本、AI试玩、构建发布
17 主Hero Flow集成
18 其他游戏Demo
19-21 运行监控、前端SDK、Judge Mode
22 安全性能QA
23 最终审计
```

## 关键文件说明

| 文件 | 作用 |
|---|---|
| `MASTER_CODEX_PROMPT.md` | 一整个大任务，交给主Codex持续执行 |
| `AGENTS.md` | 每次任务都会遵守的长期仓库规则 |
| `design.md` | 聊天首页、四边拉起、Dock工具窗口及视觉规范 |
| `architecture.md` | 系统层次、模块运行时、事件、Adapter与数据线程 |
| `MODULE_CONTRACT.md` | 每个功能单独文件夹的强制结构与依赖规则 |
| `FRONTEND_INTEGRATION.md` | 新增Editor、模块、命令、事件、Context和API的方法 |
| `MODEL_ROUTING.md` | Astra/Sol/Terra/Luna/Spark难度路由与Fallback |
| `SUBAGENT_ORCHESTRATION.md` | 并行边界、Worktree、交接和审查方式 |
| `DEFINITION_OF_DONE.md` | 防止只做页面却宣称完整 |
| `PROMPTS/` | 24个可独立新开对话的阶段提示词 |
| `SUBAGENTS/` | 手动调用各专业Agent时的角色提示词 |
| `TEMPLATES/` | 新对话交接、模块实现、审查、Bug恢复模板 |
| `.agents/skills/` | 可重复调用的模块、Editor、Adapter、Hero Flow和审查Skill |

## 最重要的架构约束

```text
apps/web：只负责启动和组合
services/api：只负责启动和注册
packages/core-*：只放跨模块核心原语
modules/<module-id>：每个功能完整自包含
integrations：Blender/Unity/ComfyUI等宿主工具桥接
examples：具体游戏项目，不放平台逻辑
```

## 首页验收

第一次打开必须满足：

```text
只有对话
+ 四边很轻的拉起热区
```

不得默认出现：

- Dashboard；
- 左侧导航；
- 右侧Inspector；
- 底部Console；
- 功能卡片矩阵。

工具通过对话、拖拽边缘、快捷键、菜单或Tool Library加入工作区。

## 开发纪律

- 先让Mock完整链跑通，再逐边界替换Live；
- Mock、Cached、Live始终可见；
- AI修改必须先生成ChangeSet；
- 不允许任意Python、C#和Shell；
- 每个模块自己带测试、Fixtures和文档；
- 公共合同由主代理负责；
- Subagent不能同时改同一文件；
- UI与后端接口变化时同步更新前端接入文档；
- 最后必须跑主Hero Flow和Warehouse Escape。
