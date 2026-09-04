# E2E 状态

模块本地 API、命令和 React 编辑器集成已由后端/前端测试覆盖。真正的 Playwright 工作台 E2E 需要尚不存在的 ForgeShell、生成模块目录、core command/event bus、Asset Library 和 Unity adapter，因此当前为 `blocked`，不是 skipped/passed。

集成具备后应验证：从 Conversation 调用 `character.inspect`；打开六个编辑器；切换 follow/pinned context；显示离线状态；审批版本和 ChangeSet；用真实/缓存证据捕获固定相机预览；执行 Unity Mapping；重载布局后恢复本地状态。
