# 脱敏与诊断安全

## 两道边界

脱敏在两个位置执行：

1. 日志进入 Gateway、获得序列之前；
2. 诊断包写入 ZIP 之前。

这保证查询、重连和下载都只接触安全内容。诊断导出不能依赖“上游应该已经脱敏”的假设。

## 被移除的内容

- Bearer token；
- token、password、secret、API key、Authorization、Cookie、credential、signature 和 session key 字段/赋值；
- URL 中的用户名、密码、完整路径、全部 query value 与 fragment；
- POSIX 与 Windows 绝对本地路径；
- 带有 `path`、`root`、`cwd`、`directory`、`filename` 或 `file` 语义键的字符串值。

结构化字段必须同时通过 allowlist。未经批准的自由字段会被拒绝。

Manifest 记录 redaction policy version 与 `recognized_secrets_removed`，不声称可以推断完全无标记的随机秘密。生产者授权与“秘密不得进入日志”的合同仍是第一道边界。

## 被保留的内容

- project/run/job/correlation/causation ID；
- 模块、集成与 Worker 的稳定 ID；
- allowlist 状态码、操作名、持续时间和队列深度；
- Artifact ID 与经过脱敏的显示标签；
- URL 的 scheme、非敏感主机与端口；路径和参数值不会保留。

本地文件不能作为 Artifact 链接。先由 artifact-store 创建稳定 Artifact ID，再记录该 ID。

## 下载授权

`DiagnosticBundleService` 只负责组装安全字节。路由同时要求 `observability:export` 与项目级授权。生成时间来自服务端 UTC clock，execution mode 从实际纳入的日志推导，健康快照只能由可信 provider 注入；HTTP 请求不能自行声明 Live provenance。生产组合还必须由 core-storage 决定 Artifact provenance、校验和、保留与下载 URL。
