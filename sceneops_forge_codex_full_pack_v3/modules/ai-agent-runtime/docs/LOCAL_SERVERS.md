# 本地运行服务

`GET /api/agent/local-servers` 返回 `LocalServerList`：`servers` 与 UTC `observed_at`。每项 `LocalServerInfo` 包含 `id`、`pid`、进程名称 `name`、UTC `started_at`、`endpoints[{host,port}]`、已知托管预览的 `project_id`、`managed`、`can_stop` 和只读原因 `stop_reason`。同一进程的监听端口合并展示，因为停止进程会一起关闭这些端口。

服务端调用本机固定 `lsof` 与 `ps` 读取当前 TCP 监听信息，只输出可执行文件名称，不输出命令参数、环境或凭据。列表读取不停止进程。应用原有同源、回环与身份验证中间件继续保护这两个入口。

`POST /api/agent/local-servers/{id}/stop` 只停止用户明确选择的一个进程。返回 `LocalServerStopResult`：`id`、`state=stopped|still_running`、`remaining_endpoints` 和中文 `message`。只发送一次 SIGTERM；不会升级到 SIGKILL、重试停止、结束进程组或子进程树。仍在监听时如实返回 `still_running`。

选择 ID 绑定 PID、进程开始时间、所属用户和当前端口集合；停止前重新读取并核对，进程或端口变化时拒绝请求并提示刷新。只允许当前用户拥有的 Node、Python、Bun、Deno、Ruby、PHP 开发运行时。其他进程只读；工作台自身进程、祖先进程和 `SCENEOPS_WEB_PORT` / `SCENEOPS_API_PORT`（默认 4300 / 8300）以及当前请求与 Origin 的端口受到保护。进程类别来自可执行文件名称，不声称识别其业务用途；用户仍应核对名称与全部端口再确认。

托管游戏预览被停止后，其既有运行状态在下一次游戏状态读取时记为 `stopped`，不再提供运行中的预览。非托管进程没有项目关联时保持空值，不猜测工程。

聚焦测试：`node scripts/python.mjs -m pytest -q modules/ai-agent-runtime/backend/tests/test_local_servers.py`。只创建并关闭专用临时 Python TCP 服务；另用注入进程信息验证 PID 复用、用户和监听变更拒绝，不停止现有服务。完整套件及真实现有进程停止未执行。
