# 本机 UI 诊断

应用栏「诊断」由 `DebugPanel` 提供。`installUiDiagnostics()` 引用计数安装 window error / unhandledrejection 监听；组件卸载需调用返回的清理函数。

宿主可使用 `recordUiEvent(type, fields)` 与 `recordUiError(error, fields)`。字段执行白名单投影，不传聊天内容、URL 查询、请求或密钥。禁止在 pointermove / 每帧布局通知中直接记录，以免同步 localStorage 写入影响拖拽。

最近 200 条保存在同源 localStorage，面板展示最近 80 条，复制/导出包含全部。记录只用于调试，不是业务审计或服务端日志。渲染进程崩溃可能只留下最后操作，没有错误堆栈。

定向检查：`node --experimental-strip-types --test apps/web/src/debug/tests/diagnosticState.test.ts`（应用根执行）。
