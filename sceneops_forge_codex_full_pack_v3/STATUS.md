# 当前状态：V5 AI Harness 主干与 UI/UX 已落地，完成空态烟测

## 追加：统一界面视觉重做

按用户允许调整旧视觉规范的要求，重做石墨灰/蓝色工作台外壳、紧凑对话与输入面板、模型设置弹窗、中文分组工具选择器和生产计划空态。保留原位承载、四边拉手、上下文和 AI 接口。仅做独立空数据目录的启动与 UI 烟测；未发起 AI、保存设置或运行业务。说明见 `UI_REFRESH_SMOKE.md`。

## 追加：拉出区域原位选择与承载

按用户明确的交互要求，四边空区域统一显示功能选择器，默认在当前面板切换功能，位置、尺寸与上下文保留。修复原生空抽屉反馈覆盖用户拉出指令，以及先向中心创建面板的问题；选择已打开的单例保留既有实例。补充窄面板响应式排版。此次只做 UI 空态路径烟测，不调用 AI 或运行业务。结果见 `DRAWER_UI_SMOKE.md`。

## 追加：用户授权的 AI 真实连通修复

修复 CLI JSON 数组结果解析及本机原生结构化模式挂起依赖；保持全部工具禁用，采用应用严格 JSON Schema 校验。GLM 已实际完成聊天、模块建议、结构化计划与单专家分析；最终计划专项返回 completed，读回 5 条持久事件；4301 页面已显示并保存真实连通回复。12 项专项离线回归通过。GLM 复查有格式拒绝，HY4 有超时，不宣称稳定性完成。详情与失败记录见 `AI_LIVE_VERIFICATION.md`。

## 初始 V5 交付记录

当前用户要求详见 `HARNESS_MIGRATION_DECISIONS.md`。V5 内核由 Astra、Provider 由 Sol、统一 UI/UX 由 Terra 实现；主代理串联 AI 模块、生产计划界面和统一后端，另由 Astra 独立只读审查高风险边界。上一次整合提交 `34121bf` 及其记录保留。

V5 空态启动、健康接口、空项目、模型候选列表及目录注册已通过最小烟测：16 项能力、10 个产品角色、5 层模型配置。未运行测试套件、生产构建、业务操作、外部工具或真实 AI。不能据此声明完整 V5 或生产链完成。交付与未验证项见 `V5_HANDOFF.md`、`V5_SMOKE.md`、`PROTOTYPE_GAP_MATRIX.md`。V5 预览为 4301/8301、独立 `.local/v5-preview` 数据；未主动停止旧服务，收尾发现此前后台进程已结束后仅重启 V5 预览。

## 上一版整合结果

2026-09-05：11 个工作台历史已合入 `codex/integrated-workbench`。统一 `pnpm dev`、Web 4300/API 8300、原生工作台注册、SQLite 项目/草稿和统一 CodeBuddy 接口已实现。启动烟测确认健康、11 组注册、空项目、空聊天、模型目录及10个业务面板空态；未运行业务测试或案例。完整记录与已知限制见 `INTEGRATION_SMOKE.md`。真实 AI 尚未成功验证，可见页面的手动请求出现 503，代理未发起或重试。

本轮用户已批准将 11 个工作台合入主项目整合分支。默认空工作区，本地 SQLite 保存，AI 统一 CodeBuddy CLI。只授权一次启动/导入/空态烟测；禁止 demo 案例、业务操作测试、真实 AI 请求、完整测试及生产构建。原工作树与历史数据保留。

## 本轮写入所有权（已收尾）

- 主代理：apps/web、packages/core-ui、packages/api-client、前端共享 workspace 客户端、根依赖/锁文件/启动脚本、生成目录、根文档与最终启动烟测。
- ai_adapter：integrations/codebuddy-cli、modules/conversation-home（后端、统一聊天/建议前端与模块文档）、concept-lab/design-room 中已有 CodeBuddy 后端适配器的兼容委托。禁止修改主应用或项目存储。
- workspace_backend：modules/project-intake/backend、services/api、其余业务模块后端的统一组合/空态/按项目存储适配（不改 AI 适配器），后端 requirements。先发布公开接口供前端消费。
- workbench_editors：除 conversation-home 外的业务模块前端、apps/labs 中用于提取的前端组合入口，负责公开可嵌入编辑器、空态/项目上下文和草稿保存对接。禁止修改主 Shell、公共包、后端或根依赖。

所有代理不创建新任务、不用 Bridge、不提交、不启动服务或测试。主代理统一验证并提交。

## 先前 Shell 交付记录（不是本轮验证证据）

2026-09-05：整合原 01 `477e673`、02 `1a14081`、03 `1eca516`；公共骨架提交 `4f3416e` 已先完成。

当前交付：`apps/labs/shell` + `apps/web` 公开组合、真实 conversation-home、Dockview 四边抽屉/工具库/命令搜索、统一 pnpm workspace 和生成模块目录。`core-ui` 是旧 Shell UI 类型的唯一公共位置，Shell 保持转导；core kernel 未重写。

新增用户要求已接入：CodeBuddy CLI 文本 API（8310）及前端 15 模型选择，默认 MOCK；真实请求由用户发送时执行。本地 CLI 版本 2.144.0；登录、额度和模型推理未运行。

验证：启动和公共导入通过；唯一最小路径“对话提案→预览→确认→右侧工具库”通过；刷新启动恢复布局；本地模型目录 GET 和下拉框可用。许可证 console 提示为本地 Enterprise 评估水印的预期行为。

完整单元、集成、类型、构建、E2E、安全、性能、外部模型、Unity/Blender/渲染/AI playtest：not run / pending approval。未启动暂停的演示/审计/SDK/验收任务；未修改来源工作树、未自动合入主工作树、未部署。

详细操作、限制与验证记录见 `apps/labs/shell/README.md`。
