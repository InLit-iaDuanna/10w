# 来源与采用范围

本技能为 SceneOps 按本地导出场景编写，不执行远程 skill 的安装脚本。

- [Capawesome 官方 Capacitor 开发 skill](https://github.com/capawesome-team/skills/blob/cc8319c70de1fdb02d99823a359ecaf3bf4db960/skills/capacitor-app-development/SKILL.md)，MIT；采用先发现项目/版本再路由的方式。
- [Android sdkmanager 官方说明](https://developer.android.com/tools/sdkmanager)，该页在 2026-09-02 更新后列出 Android CLI 的 `android sdk [install|list|update|remove]`，同时保留 sdkmanager 使用说明。按工程和已安装工具选择，不自动迁移；许可交互由用户与运行时授权决定。
- [Electron Builder 多平台构建](https://github.com/electron-userland/electron-builder/blob/0d47ef5c4dda24939e5a6b02927440bdc2da1cd1/website/docs/features/multi-platform-build.md)，MIT；采用目标架构与原生依赖限制。

检索日期：2026-09-08。源码链接固定 Git commit，仅作版本引用，无新增摘要算法。没有照搬上游清空全局缓存、全量环境变量传输、固定 SDK 数字或云迁移步骤。
