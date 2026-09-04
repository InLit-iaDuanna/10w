# 当前状态：独立 Shell 工作台

2026-09-05：整合原 01 `477e673`、02 `1a14081`、03 `1eca516`；公共骨架提交 `4f3416e` 已先完成。

当前交付：`apps/labs/shell` + `apps/web` 公开组合、真实 conversation-home、Dockview 四边抽屉/工具库/命令搜索、统一 pnpm workspace 和生成模块目录。`core-ui` 是旧 Shell UI 类型的唯一公共位置，Shell 保持转导；core kernel 未重写。

新增用户要求已接入：CodeBuddy CLI 文本 API（8310）及前端 15 模型选择，默认 MOCK；真实请求由用户发送时执行。本地 CLI 版本 2.144.0；登录、额度和模型推理未运行。

验证：启动和公共导入通过；唯一最小路径“对话提案→预览→确认→右侧工具库”通过；刷新启动恢复布局；本地模型目录 GET 和下拉框可用。许可证 console 提示为本地 Enterprise 评估水印的预期行为。

完整单元、集成、类型、构建、E2E、安全、性能、外部模型、Unity/Blender/渲染/AI playtest：not run / pending approval。未启动暂停的演示/审计/SDK/验收任务；未修改来源工作树、未自动合入主工作树、未部署。

详细操作、限制与验证记录见 `apps/labs/shell/README.md`。
