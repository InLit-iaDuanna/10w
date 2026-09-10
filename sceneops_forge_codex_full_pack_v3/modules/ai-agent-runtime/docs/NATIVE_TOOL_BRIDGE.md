# 原生制作领域工具桥

`NativeToolBridge(service, task_id)` 在任务运行期间作为异步上下文管理器存在。它提供临时环回 HTTP 端点，由 CLI 启动的轻量 stdio MCP 进程转发请求；`mcp_servers` 可直接加入执行器的临时 MCP 配置。令牌只在本次进程配置传递，不写入任务事件、简报或工程。退出时关闭端点并取消在途请求。

工具清单是固定领域能力与当前任务授权的交集，每次调用重新检查授权及工作区占用。项目和工作区来自服务端任务，工具参数不能指定其他项目。领域调用复用 `TaskTools.dispatch` 的公共资产、场景、构建及浏览器服务，不伪造源码动作历史。开始、失败和完成事件保留真实领域操作证据。普通源码使用 CLI 原生能力。

`native_tool_capabilities(card)` 分别按游戏执行、依赖安装、浏览器观察与交互开关筛选能力。CLI 完整权限不自动扩大领域工具授权。资产查询及场景返回数据限制在任务工作区。

## 可编辑资产

`project.asset.register` 接受 `path`、`title`，更新已有版本时还须提交 `asset_id` 和 `expected_version`。路径必须指向工作区内的自包含 GLB 2 文件。首次登记分配新资产身份；更新保持资产身份并创建新版本。服务读取真实几何及节点变换，计算静态姿态尺寸和几何数量，复制不可覆盖的 GLB 运行文件，并通过资产目录公共服务登记 `source_kind: glb`。不伪造 Blender 或 FBX 源。

首轮支持嵌入二进制、非压缩 float VEC3 位置属性；稀疏或压缩几何需要先通过原生工具导出为上述格式，错误会明确返回，不猜测尺寸。实例放置、变换、删除和共享资产重绑定使用已有版本冲突语义。完成后调用 `code.demo_content.materialize`；运行源码必须实际读取物化模块，构建成功不能替代运行回流验证。

## 技能投放

`stage_native_skills(workspace_root, executor)` 从同一套产品技能复制 Gameplay、Graphics、UI、Debug、QA 及引用资源，Codex 使用 `.agents/skills`，CodeBuddy 使用 `.codebuddy/skills`。只更新 SceneOps 所有的同名技能；其他技能保留，同名用户技能冲突明确报告。技能目录不允许符号链接。制作简报保持任务输入，技能不覆盖原生系统提示词。

本地回归覆盖 stdio 通信、令牌和授权拒绝、实际资产版本与场景服务回流、版本冲突、物化以及技能引用投放；不代表真实模型、浏览器玩法或画面已验收。
