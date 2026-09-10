# 本地可玩包导出

`ExportService` 与 `create_export_router` 提供独立于正式发布候选的项目级导出流程。APK 和桌面 ZIP 是本地试玩产物，不代表商店发布、签名、公证或设备验收完成。

## 公共接口

基础路径为 `/api/projects/{project_id}/exports`：GET 列表、POST 创建；`/{task_id}` 获取详情。创建参数含 platforms（android、mac-arm64、mac-x64、win-x64）及 settings（app_name、app_id、orientation、allow_dependency_install）。依赖安装默认不授权；模型不能提升该授权。

- `/{task_id}/refresh-source`：POST 从当前已保存源码创建关联的新任务，沿用设置和平台并复制对话；previous_task_id 关联原记录。仅由用户明确触发，旧日志、产物和验收保留在旧任务。
- `/{task_id}/settings`：POST allow_dependency_install，仅由用户设置后续执行的依赖下载授权；不修改历史执行授权，不自动重试。
- `/{task_id}/messages`：POST content、可选 provider_id/model；调用宿主注入的真实 Agent 回调，持久化消息与模型调用元数据。未配置模型会显示明确消息，不模拟回复。
- `/{task_id}/platforms/{platform}/continue` 与 `/cancel`：POST 继续失败/中断/取消的执行，或请求取消当前执行。
- `/{task_id}/platforms/{platform}/verification`：POST status、attempt_id、device、notes，记录当前成功产物的人工设备验收；通过/失败均需实际设备与说明。新一轮执行清除当前验收。
- `/{task_id}/artifacts/{artifact_id}`：GET 项目与任务范围内的下载。
- `/{task_id}/events`：SSE `snapshot` 事件为完整 ExportTask，事件 ID 为持久 revision；重连即发送当前状态。

网络模型来自 `export_models.py`，运行 `backend/scripts/export_playable_contracts.py` 生成 OpenAPI，再通过 openapi-typescript 生成 `frontend/src/export/api.generated.ts`。

## 执行与恢复

宿主通过 resolve_project 返回已登记项目的 root_path/name，不能让请求直接指定任意路径。导出根目录独立于源码目录，SQLite 保存任务、各平台全部执行轮次、日志、聊天和产物定位。每个执行轮次记录实际使用的设置。

创建任务对复制前后源码的相对路径、inode、大小、修改时间与 Git HEAD 进行比较，检测到并行保存时移除未完成快照并提示重试。复制当前已保存源码，并以 Git commit（如果存在）与独立 snapshot ID 记录来源；工作副本允许包含尚未提交的保存内容，因此它不是正式 release 的 clean attestation。排除依赖、构建目录和凭据文件，拒绝源码符号链接，防止读取源工程之外的文件。Web 构建成功后供所有目标共享，失败准备通过新目录重试；平台构建使用各自执行目录。

Agent 只可调用 continue、cancel、configure（应用名称/方向）或提出 request_development。开发建议保存在消息中，由现有开发入口处理，不能通过导出执行任意命令或修改游戏源码。宿主注入 redact_text 后，在持久化日志与执行错误前脱敏；模型桥负责对调用上下文、响应及调用记录脱敏。

平台独立失败，已完成产物保留。取消保留 cancel_requested；进程重启将未知的 queued/running 执行标为 interrupted，等待用户继续。服务生命周期应调用 close 停止活动构建。

## 验证

`backend/tests/test_exports.py` 使用明确标为 mock 的确定性适配器覆盖共享源码、部分失败及重试、下载范围、取消、SQLite 恢复、模型动作范围、人工验证记录和 HTTP 合同。它不证明 Android/macOS/Windows 工具可用或游戏可玩；实际设备验收在相应平台上完成后单独记录。

## Native computer-operation bridge

New UI calls create with `execution_mode: native, accept_full_access: true`. Legacy
create requests remain fixed-adapter exports. Messages explicitly select `native`
(with full-access consent) or `discuss`; discussion never executes structured
build actions. Native exports start immediately in the isolated persistent
`native-workspace/source`, can install missing local tools through the existing
native Agent runtime, and preserve repairs between turns. `/agent/cancel` stops
the actual native worker. Fixed builds and native work cannot run concurrently
within the same export. Restarted native runs are marked interrupted, never
silently replayed.

`ExportService.native_agent` is an injected port: prepare receives trusted context
and returns an Agent task ID; run receives the ID, a stage/message event callback,
and a cancellation event. The API composition uses public AgentTaskService
prepare/run methods, including its authorization and real native execution path.
Native IDs, logs, errors, and completion are durable and streamed by existing SSE
snapshots. Runtime completion alone does not change package success.

The Agent writes `sceneops-export-result.json` under its workspace with
`artifacts: [{platform, path}]` and optional `platforms: [{platform, status,
message}]`. Paths are relative; only nonempty in-workspace APK/ZIP files with
expected archive entries are accepted. Accepted packages are copied to a separate
per-run artifact directory so later repairs cannot replace earlier downloads.
Device verification always remains pending. Tests use a controlled native port;
no SDK installation, real provider invocation, or device validation is implied.
