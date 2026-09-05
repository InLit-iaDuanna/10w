# V5 启动与空态烟测

此页保留初始空态烟测。用户之后对 GLM/HY4 明确追加了真实 AI 验证授权，见 [AI 真实连通记录](AI_LIVE_VERIFICATION.md)；不能把两个阶段的授权与结果混为一谈。

2026-09-05，本轮仅最小启动/导入/空态检查。未发送真实 AI 请求，未新建项目、保存配置或运行业务。

## 环境与隔离

- 本轮烟测用 4301/8301，临时空数据目录 `/private/tmp/sceneops-v5-smoke.fGvJlm`；没有读写原项目数据库。
- 收尾预览改用 `.local/v5-preview/` 持久空目录；这是预览数据隔离，不自动复制临时数据或旧演示数据。
- 烟测时保留原有服务，没有主动结束用户服务。收尾发现此前后台会话已失效、4300 不可连接，仅读取端口状态后重新启动 V5 持久预览，不重启或改动旧数据。
- 使用已有本机 CLI 仅读取候选目录及可执行文件存在性；未做登录验证。

## 结果

| 检查 | 结果 | 证据范围 |
| --- | --- | --- |
| `pnpm dev` 前后端启动 | 通过 | 本地 Vite 与 API；无自动作业 |
| `GET /api/health` | 200 | ready、SQLite、空态、external_execution=not_started |
| `GET /api/workspace/projects` | 200 | `projects: []` |
| `GET /api/ai/settings` | 200 | codebuddycli、cli-default、无 URL/Key |
| `GET /api/ai/models` | 200 | CLI 默认及 15 个候选；不是账户权限证明 |
| `GET /api/harness/catalog` | 200 | V5、16 能力、10 角色、5 层配置 |
| 浏览器首页 | 通过 | 对话空态、四边拉手、项目/计划入口 |
| 提供方弹窗 | 通过 | 切换未保存的兼容表单，检查字段和布局，Esc 关闭；不保存 |
| 生产计划和本地项目面板 | 通过 | 原生分栏、空态与未选择项目提示；不创建项目 |
| Console | 有已知许可提示 | Dockview Enterprise 评估许可提示；未绕过 |

持久预览重启时，仍打开的浏览器在 API 就绪前发生短暂 502；API 启动完成后重新加载，接口恢复 200，Console 仅剩现有许可提示。没有把启动窗口中的失败隐藏为全程无错误。

启动过程中发现并修复：Python editable `.pth` 未加载（统一显式源码入口）；旧模块读取相对资源（统一源码环境）；integration-center 缺失直接依赖 `openapi-fetch`；内核方法名与类型注解同名（延迟注解）；提供方弹窗裁切（原生 modal 和视口滚动）。同一轮重启/空态复查，不扩大为测试套件。

OpenAPI 与前端类型已从后端公开模型重新生成，这是模式生成，不是测试通过证据。

## Limitations / not run

没有执行：任何 demo 案例、Mock 业务流程、真实 AI 推理、聊天/提案提交、创建/保存项目、配置写入、运行启动/审批/取消/重试/回滚、模板提取、完整测试、类型检查、生产构建、Unity、Blender、渲染、AI playtest 或发布。上述行为的代码未经过本轮业务验证。

空态截图保存在 Git 忽略的 `output/playwright/`：`v5-home.png`、`v5-provider-settings.png`、`v5-pipeline-empty.png`。截图只能证明可见布局，不能证明执行链。
