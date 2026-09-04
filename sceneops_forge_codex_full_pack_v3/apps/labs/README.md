# 独立功能工作台

应用根首次执行 `pnpm install`，之后执行 `pnpm lab <lab-id>`，等价于 `pnpm --dir apps/labs/<lab-id> dev`。Node 22.12+；pnpm 11.13.0。每个入口自己管理所需本地 API 子进程，退出时只关闭自己启动的进程。

## 接入约定

- 在 `apps/labs/<lab-id>/package.json` 声明自己的 `dev` 和依赖；入口仅组合业务公开 `frontend/src/index.ts`，不复制模块实现。
- 共享 React/ReactDOM 19.2.8、TypeScript 6.0.3、Dockview 8.2.0。Vite 8.0.0 位于根工具链，前端使用自动 JSX 转换。
- Vite 必须 `host: '127.0.0.1'`、`strictPort: true`；端口按派发表。API 同样只绑定 localhost。占用即清晰失败，不终止其他进程。
- 每个 lab 的 README 列出首次安装、独立启动、URL、演示数据位置、真实/mock 状态、手动路径、精确烟测与未执行测试。
- workspace 已覆盖 `apps/labs/*`、`modules/*/frontend`、`packages/*/frontend`。业务模块包使用 `workspace:*` 引用公开导出。
- 根 workspace/锁文件/工具链由 Shell 组维护。其他组在自身 README 记录公共变更请求，供整合时加入。
- 公共 core/runtime 复用原提交 `477e673`；不另建 kernel。统一启动器不自动加载业务、不自动安装、不运行测试。

仅运行启动/导入检查和一条最小本地主路径；其他测试 not run / pending approval。
