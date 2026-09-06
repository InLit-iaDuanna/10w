# 任务授权的 Unity 常驻会话

公开入口为 `engine_unity.UnityAgentSession(workspace_root, state_root, executable=None)`。
`workspace_root` 必须为服务端分配的 `agent-workspaces/<project_id>` 绝对规范路径；调用方先执行
`bind_authorization(grant)`，再调用同步 `start()`、`inspect()`、`import_asset(...)`、`stop()`。
`start()` 只创建 `workspace_root/unity` 中的专用空工程，并以可见、非 batch 的 Unity
2022.3.62f3c1 打开。已有非 SceneOps 工程会被拒绝。工程的 UPM manifest 引用应用固定 bundled package
的绝对 `file:` 路径；该代码路径来自应用，不接受模型或客户端输入，不扩展任何资产读写根目录。
不会修改全局配置。任务服务负责将公开连接元数据保存到 SQLite；私有 transport 凭据留在工程
`.sceneops-agent` 的 owner-only 文件中，不返回到 API。

授权包含 `task_id/grant_id/project_id/workspace_root/allowed_capabilities/expires_at`；导入每次还需
`action_id/capability_id/change_set_id/approval_id`。调用方从可信任务服务生成这些值，不能透传模型授权。
导入 capability 为 `unity.asset.import`，读取为 `unity.scene.inspect`。桥接两端均校验实际工程、
会话、任务、授权范围与 UTC 到期时间。导入生成完整 ChangeSet 并复用原有 C# command router 的
审批和 payload 绑定检查；对已存在的不同产物拒绝覆写。

IPC 为工程内部 0700 目录中的认证 JSON mailbox，无网络监听端口；配置/请求文件为 0600。
Unity 的 `EditorApplication.update` 在主线程消费固定的 inspect/import 请求，编译和
AssetDatabase 更新期间等待。domain reload 后从同一目录重新读取请求。每个请求 ID 对应持久化
请求与结果，复用 ID 但改变输入会被拒绝；已保存实例按稳定身份恢复，重复请求不会重复实例化。
取消中断仅由会话拥有的编辑器进程，保留工程、请求和产物供恢复与审查。

`import_asset(request_id, asset_id, sceneops_id, fbx_path, manifest_path, authorization)` 的关键字参数
接受专用工作目录内 FBX 与现有 Unity schema v1 sidecar（一个对象）。sidecar 必须包含
`source_asset_id/source_asset_version_id/objects[{source_object_id,sceneops_id,display_name}]`。
适配器将来源暂存到此 Unity 工程，调用原有 `unity.asset.import`，在固定
`Assets/SceneOpsAgent.unity` 保存实例并回读 `asset_id/sceneops_id/scene_instance_id`、实际 Unity GUID、
GlobalObjectId、`dimensions_m`（Unity XYZ 世界坐标，米）和错误日志。Blender 的 XYZ 尺寸与 Unity 的
XYZ 尺寸通过 X,Z,Y 对应。重复导入的原执行标记 cached，回读单独标记 live。

定向测试：

```sh
PYTHONPATH=modules/engine-unity/backend/src .venv/bin/python -m unittest engine_unity.tests.test_agent_session -v
```

编译/资源更新尚未就绪时，原请求保持排队且不会留下执行标记，恢复连接后仍可处理相同请求。
一旦开始导入，先持久化 started 记录。若写入阶段失败或进程中断而没有可靠结果，则返回
`UNITY_OUTCOME_UNCERTAIN`，保留原失败与原因，不自动重放潜在部分完成的变更。应先回读实际工程再由
任务服务决定恢复；失败不是成功缓存。成功返回之前，已有实例和新实例都必须完成场景保存验证。

2026-09-05 验证：15 个会话测试通过（空工程、安全路径、已有工程拒绝、授权过期、请求重放/冲突、取消、
许可证分类、token 脱敏、action 记录、编译等待、未确定结果、结果 symlink、固定bundle配置与readiness诊断）；既有 14 个安全合同测试通过；Unity installed reference assembly 编译通过。
新增 C# Editor 回归测试覆盖 scene/result symlink、已有结果保留和已存在实例保存；尚未执行 Editor 测试套件。
可见真实启动记录 `Batch mode: NO`，随后返回 `No valid Unity Editor license found. Please activate your license.`。
工程和日志保留于 `/Users/isduanna/Library/Application Support/SceneOps/agent-workspaces/prj_unity_connection_7539c7c3b0ad/unity`，
日志为 `.sceneops-agent/editor.log`，仅此会话拥有的 Editor 进程已停止。

用户激活许可证后，同一独立空工程再次可见启动并完成两次实际 inspect：Unity 2022.3.62f3c1、
`connected=true`、`compiling=false`、`objects=[]`、`errors=[]`，实际会话 PID 81325。
此次经过修复的 bundled package 已在真实 Editor 中编译并启用，脚本 exit 0；该专用进程随后停止。
当前 `editor.log` 为成功启动证据，原许可证日志保留为
`.sceneops-agent/editor.461d52d27b674aaaa998c03e6999c8d9.log`。

联合任务发现 `.local` 下 embedded package 的 Editor/Runtime 目录实际具有 macOS hidden flag，
Unity 只注册 package 顶层而不导入 C#（ScriptCompilationData 的 Assemblies 为空），导致常驻桥接未加载。
配置已统一改为固定 bundled package 引用，bundled 目录提交标准稳定 `.meta`。
旧任务 start 时把其自有 embedded package 移入同工程私有 mailbox 备份，再修改自有 manifest；
不迁移 workspace，不使用 symlink，不修改授权路径。
同一真实任务于 2026-09-05 11:52:11 UTC 恢复并完成联合验收：两端身份一致、Unity 尺寸为
`[1,3,2]` 米（对应 Blender `[1,2,3]`）、控制台错误为空。隐藏的 Assets 目录没有阻断此次显式 FBX 导入。
最终独立审查补齐 launcher.log 的现有路径校验，并用定向测试确认外部 symlink 不会被追加写入。

## Limitations

可见 Editor 编译、常驻 readiness、主线程 FBX 导入、场景尺寸与身份回读已真实验证。
适配器不会自动签署协议或激活许可证。此验收仅覆盖独立简单资产闭环。
未运行游戏、生产构建、渲染、AI playtest 或 Editor 测试套件。
