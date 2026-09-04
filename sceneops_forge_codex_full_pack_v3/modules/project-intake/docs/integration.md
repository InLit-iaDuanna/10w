# Project Intake 接入说明

## 扫描边界

宿主 integration 实现 `ProjectScanAdapter`，提供 health、capability report 和可取消的 scan，并把 SDK 对象转换成带 adapter version 的 `ProjectScanReport`。模块只接收字符串、稳定 ID、预算和需求条目；不得把 Unity/Blender 类实例、枚举或路径对象放进报告。

调用顺序：命令权限检查 → adapter health check → 绝对根路径验证 → adapter scan → 归一化为 `ProjectIntakeRecord`。根路径来自用户选择，因此是 confirmed；扫描发现的其余字段始终 inferred。

## 与 shell 集成

将 `moduleContribution` 注册到未来的静态 module catalog。`load()` 延迟加载 editor view model。命令返回的 `openEditorAction` 应交给统一 `WorkbenchCommandBus`，模块不可直接操作 Dockview。

## 与 Design Room / Planner 集成

Design Room 只能从公开入口读取 `ProjectIntakeRecord` 和 `validateIntakeForActivation`。生产计划模块订阅设计模块的 ready event；它不应通过本模块内部 repository 做隐藏 join。

## 执行真实性

- fixture adapter：`mock`
- 以前真实扫描复用：`cached`
- 本次真实 adapter 扫描：`live`
- 尚未发起：`planned`
- 离线、权限或宿主错误：`blocked` 并附结构化原因
