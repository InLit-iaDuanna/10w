# 工作台 01：对话与工作台基础

本入口整合原 01 core/runtime、02 conversation-home 和 03 Forge Shell。业务位于原 modules；`apps/web` 是公共浏览器组合，`apps/labs/shell` 只负责 localhost 启动。不是模拟的聊天页面，也没有第二套停靠系统。

## 首次安装与启动

从应用根 `sceneops_forge_codex_full_pack_v3/` 执行，Node 22.12+、pnpm 11.13.0、Python 3.11+：

```bash
pnpm install
python3 -m venv .venv
.venv/bin/pip install -r apps/labs/shell/requirements.txt
pnpm lab shell
# 等价：pnpm --dir apps/labs/shell dev
```

一次启动 Web 和 API：

- Web： http://127.0.0.1:4310/
- API/OpenAPI： http://127.0.0.1:8310/docs
- 模型列表： http://127.0.0.1:8310/api/conversation/models

默认优先使用应用根 `.venv/bin/python`，否则使用宿主 `python3`。显式配置：

```bash
LAB_WEB_PORT=4410 LAB_API_PORT=8410 LAB_PYTHON=/absolute/path/to/python pnpm lab shell
```

占用端口会报错退出，不杀其他服务。Ctrl+C 关闭本启动器创建的子进程。CLI 接入无需启动其他 lab。

## 手动操作

1. 新浏览器会话/首次本地存储只有对话和四边拉手，没有侧栏或仪表盘。
2. 默认选中 **MOCK · 确定性演示**。输入“打开工具库”，点击“预览布局”→“确认布局并执行”。真实工具库停靠在右侧。
3. 输入框输入 `/`，或点击“命令搜索”，选择工具、撤销布局、保存、重置为纯对话首页。聊天、工具按钮和搜索共用 WorkbenchCommandBus handler。
4. 双击任意边缘拉手，或键盘聚焦拉手按 Enter；Shift+Enter 固定。也可向内拖动边缘打开抽屉；Esc 关闭 Peek。顶部默认命令搜索，其余边缘默认工具库。
5. 工具库可选标签、四向拆分、浮动或弹出。拖动 Dockview 标签可重新停靠。区域“更多”提供浮动、最大化和跟随/固定；关闭后可由搜索重新打开。
6. 刷新恢复布局和临时对话。输入“模拟错误”查看可重试的显式 MOCK 错误。
7. 在输入框下方“对话模型”选择 CodeBuddy 模型并发送，才会发起真实 CLI 请求。未安装/未登录/模型无权限/超时会显示 blocked 原因，不悄悄切换 MOCK。

## CodeBuddy CLI

按用户要求接入 CodeBuddy CLI。当前宿主命令为 `codebuddy`（`cbc` 别名），检查版本为 **2.144.0**。模型选项来自该版本 `--help` 明确列出的 15 个 ID，后端使用 Pydantic Literal 白名单。前端不会提交任意命令、CLI 参数或路径。

CLI 尚未安装时，先按 CodeBuddy 官方方式安装并在终端登录；API 不读取或向浏览器返回凭据。启动模型列表只确认可执行文件存在，**不宣称账号/模型/额度可用**。真实请求使用 `--print --output-format json --model <id> --tools '' --strict-mcp-config --mcp-config '{"mcpServers":{}}' --no-session-persistence --max-turns 1`；在独立临时目录执行，保留宿主权限规则，没有 skip-permissions/沙箱放行设置。取消浏览器请求或 120 秒超时会终止本次子进程。

API 由 conversation-home 的公开 router 提供。网络类型由 Pydantic/OpenAPI 生成，HTTP 使用共享 `@sceneops/api-client`，模型目录由 TanStack Query 管理。

```bash
python3 apps/labs/shell/generate-api.py
pnpm exec openapi-typescript modules/conversation-home/contracts/codebuddy.openapi.json -o modules/conversation-home/frontend/src/generated/codebuddy-api.ts
python3 scripts/module-generate
```

## 执行模式与隔离

- live：当前浏览器真实 Dockview 操作、本地 API 模型目录读取；CLI 回复仅在真实完成后显示 live。
- mock：默认确定性 transport；“打开工具库/打开命令搜索/模拟错误”是固定演示输入。
- planned：CodeBuddy 模型未发送；未接入的其他工作台业务。
- blocked：API/CLI 不可用、未登录、权限错误、附件导入未接入等。
- cached：当前没有真实历史模型/工具结果回放。

布局存储键：`sceneops.lab.shell.layout.v3`。临时对话 scope 为 `pre_project/lab_shell`，由原 ConversationRepository 写入 sessionStorage；不会扫描生产项目。浏览器只连接同源 `/api`，API 仅接受当前本地 Web Origin 的 POST。

## 本轮验证（2026-09-05，Asia/Shanghai）

- 启动/导入：统一 `pnpm lab shell` 启动成功，Web 4310、API 8310；对话和 Shell 公共入口 Node import 成功；API model GET 返回 15 个 planned 模型；浏览器模型下拉框已呈现。
- 唯一最小本地主路径：纯对话 → 输入“打开工具库” → 预览 → 明确确认 → 右侧真实工具库。页面显示 `命令已由 WorkbenchCommandBus 执行`；随后启动刷新仍显示保存的两栏布局。
- 修复启动检查发现的企业扩展缺失和 Dockview 可选字段 JSON 序列化错误；取消宿主重复裁剪，工具内容与底部输入栏均可见。
- 当前页面唯一预期 console error：Dockview 无许可证的本地评估提示；没有将其写成“零错误”。
- 原模块完整测试、类型检查、构建、全量 E2E、安全/性能套件、外部 LLM 请求：**not run / pending approval**。新增成功/失败用例已维护但未执行；没有沿用原任务结果冒充本轮通过。

## Limitations

Dockview 8.2 自动隐藏边缘功能属于 Enterprise 扩展。本地评估允许不带 key，保留 **Unlicensed 水印**；生产部署需要许可证。见 [官方 Enterprise setup](https://dockview.dev/docs/overview/enterprise-setup/)。本任务没有购买、修改许可或部署。

CodeBuddy 真实推理、登录及所有模型权限未验证。当前 CLI 文本模式一次返回完整结果，尚未转接 token 级流；每次只发送当前消息，不恢复 CLI 历史 session。真实回复仅作为文本显示，不直接执行布局或生产工具。MOCK 提案验证/确认链路已接入真实 handler。

附件上传/项目导入、3D/Unity/Blender/渲染/构建/AI playtest 在相应工作台操作。复杂拖拽、跨窗口 popout、所有布局动作和异常分支未跑完整浏览器测试。
