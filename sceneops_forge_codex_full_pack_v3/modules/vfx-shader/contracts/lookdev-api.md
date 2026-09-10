# 原生材质接口

契约由 `backend/src/vfx_shader/lookdev_models.py` 和 FastAPI 路由生成。运行根目录的 `node scripts/python.mjs scripts/export-lookdev-contracts.py` 后，以 `openapi-typescript` 生成前端网络类型。

- `GET /api/lookdev/{project_id}/assets/{asset_id}/source?version=N` 返回登记资产的固定版本 GLB。首次读取补齐对象、材质及多图元身份并持久化，后续读取保持相同身份；保留原始二进制数据。
- `GET /api/lookdev/{project_id}/documents` 可按 `asset_id`、`scene_instance_id` 筛选最新文档。读取单文档支持历史 `version`。
- `POST /api/lookdev/{project_id}/documents` 接收文档与 `expected_version`；初次为 0。校验、编译成功后在 SQLite 事务中生成下一版本。409 保留客户端草稿。`schema_version=1` 描述持久化格式，`version` 描述文档修订。
- `POST /api/lookdev/{project_id}/proposals` 只生成提案。复用统一提供方、规范节点图提示与固定 Node 校验器；强制材料范围，默认禁止灯光修改。返回 `applied`、`declined` 或 `noop`，不会自动保存或应用。
- `POST /api/lookdev/{project_id}/apply` 接收已保存文档版本与资产预期版本；若场景引用受影响，还需场景预期版本。后端在原始 GLB 上仅修改材质数据并保存新资产版本，保持几何、动画和二进制内容。实例目标只更新该实例；资产目标更新匹配版本的现有引用。客户端不上传替换模型。
- `GET /api/lookdev/{project_id}/bindings` 返回已应用文档及确定性生成的 `runtime_module`。游戏制作服务将其作为普通工程文件导入并实际构建。`needs_build=true` 只表示需要更新试玩，不表示已构建成功。

公开 Python 服务提供 `get`、`list`、异步 `save`／`propose`、同步 `apply`、`source`、`bindings` 和 `runtime_bindings`。HTTP 入口沿用本地主机、Origin 与令牌保护。应用代码不执行模型提供的源码、命令或文件路径。

## 主对话记录

提案请求可携带客户端生成的 `turn_id`。后台在调用提供方前持久化 `pending`，生成提案后为 `proposed`，这两个状态都不声称画面已更新。`GET /turns` 返回完整记录。编辑器仅在 GPU 试渲染接受后，调用 `POST /turns/{turn_id}/finish`，提交 `applied`；失败、取消、拒绝和无需修改分别提交对应状态。完成后通过公开 `AIRepository.append_exchange` 写入原有主对话记录，固定消息 ID 防止重试重复。服务重启将未完成请求明确标记为中断。HTTP 断开取消正在等待的提供方任务。

## 已保存版本导出

`POST /api/lookdev/{project_id}/exports` 接收 `document_id`、`document_version`、`format`（`pbr-glb`、`shader-zip` 或 `luma-zip`），返回制品 ID、格式、字节数、创建时间、明确警告及受认证下载 URL。导出不会创建资产版本或更新场景引用。`GET /exports/{artifact_id}/download` 只读取同一项目登记的制品，不接受文件路径。

PBR GLB 从固定源数据确定性生成；Shader ZIP 包含规范运行模块及各材质图包；Luma ZIP 复用规范工程编码器，保存原始 GLB、当前状态及历史。PNG 仍由编辑器截图。公开 Python 方法为异步 `export(project_id, ExportLookdevRequest)` 和同步 `export_file(project_id, artifact_id)`。
