# 适配器接入与故障排查

## 公开边界

实现 `sceneops_character_animation.CharacterToolAdapter`，不要把 Blender Python、Unity C# 或厂商 SDK 类型暴露给领域服务。允许的操作只有：

- `preview.capture`
- `retarget.preview`
- `unity.character.map`

协议要求 health/capabilities、dry-run、超时、取消、显式 retry policy、幂等 request ID、进度事件、结构化日志、结果校验、provenance 和 rollback/compensation。该协议不接受文件路径、脚本或任意命令，因此不存在任意 shell/Python/C# 执行入口。

## 版本与连接

- Python：`>=3.9`；FastAPI `0.128.8`；Pydantic `2.13.2`；PyYAML `6.0.3`。
- 前端依赖版本由 `frontend/package-lock.json` 固定。
- 当前没有 Blender/Unity vendor adapter、端口或凭据要求。
- 未来 adapter 应默认仅连接 localhost，并在自己的集成模块文档中固定 Blender/Unity package 版本、端口、工程根目录和许可证。

## 权限与审批

- 读取/检查：`character:read`、`animation:read`。
- 版本更改：`character:write`、`animation:write`。
- 人工审批：`character:review`、`animation:review`。
- Unity 执行：`unity:write`，且 ChangeSet 必须为 `approved`。

## 模式

- `OfflineCharacterToolAdapter`：默认；所有外部操作 `blocked`，导入检查仍可用。
- `DeterministicMockCharacterToolAdapter`：仅测试/演示；输出和 provenance 都是 `mock`。
- `live`：未实现，必须由真实工具 adapter 当次执行并返回真实证据。
- `cached`：未实现，必须来自已记录的先前真实执行并保留原始 provenance。
- `planned`：dry-run 和未执行的 Unity Mapping proposal。

## 常见错误

| Code | 处理 |
|---|---|
| `INTEGRATION_OFFLINE` | 打开 Integration Health，连接相应 adapter 后重试；不要改写为 live |
| `APPROVAL_REQUIRED` | 在 ChangeSet/Approval 编辑器完成审批，再用同一 mapping/changeset ID 执行 |
| `INVALID_VERSION` | 检查 previous version、角色归属、审批与稳定 ID |
| `ADAPTER_TIMEOUT_INVALID` | 将 timeout 调整到 capability report 范围内 |
| `OPERATION_CANCELLED` | 保留已有日志和中间 artifact；使用相同输入和新 request ID 重试 |
| `ADAPTER_RESULT_INVALID` | 检查 adapter 输出身份、mode、相机与 provenance，不得发布结果 |
