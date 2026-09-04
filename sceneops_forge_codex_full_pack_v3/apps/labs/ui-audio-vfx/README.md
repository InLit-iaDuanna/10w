# 工作台 06 — UI、音频与特效

独立 React Web，将 `ui-studio`、`audio-studio`、`vfx-shader` 的公开入口组合到同一项目、目标事件和审批上下文。业务、Pydantic 路由与编辑面板仍属于各模块；此目录只负责启动、传输、查询组合与页面布局。不连接生产项目，不创建第二套 core/kernel。

## 首次安装与启动

在应用根 `sceneops_forge_codex_full_pack_v3` 执行。需要 Node ≥ 22.18、pnpm 11.13.0、uv；Python ≥ 3.10（本次 uv 选择 3.12.12）。

```sh
pnpm --dir apps/labs/ui-audio-vfx install --ignore-workspace
uv sync --project apps/labs/ui-audio-vfx --frozen
pnpm --dir apps/labs/ui-audio-vfx dev
```

最后一条命令同时启动 Web 和 API。启动不会自动安装、构建或测试。

- Web：[http://127.0.0.1:4315](http://127.0.0.1:4315)
- API 文档：[http://127.0.0.1:8315/docs](http://127.0.0.1:8315/docs)
- 固定 localhost；占用端口直接报错，不换端口、不结束其他进程。
- `Ctrl+C` 只停止该启动器的子进程。API 退出会清空会话内存。
- 必要时显式设置 `LAB_WEB_PORT=4415 LAB_API_PORT=8415 pnpm --dir apps/labs/ui-audio-vfx dev`。
- 可显式设置 `LAB_PYTHON=/absolute/path/to/python`，必须已安装本目录 pyproject 锁定的依赖。

本工作树未引入共享根启动骨架，避免改动 Shell 的根 workspace/lock。接口已对齐公共骨架提交 `4f3416e830e1b99a0c2a2df18150d198ac7f21ae`；整合后根 `pnpm lab ui-audio-vfx` 可转发本 lab 的 `dev`。

### 共享修改请求（交 Shell 整合）

本 lab 为独立安装使用三个模块的 `file:` 公开包引用，Vite alias 指向相同模块的公开 `frontend/src/index.ts`，编辑源码可即时更新。整合进公共 workspace 时，可将这三个依赖改为 `workspace:*`，由 Shell 更新根锁文件；本提交不改根锁。独立依赖锁在本 lab 内。React/ReactDOM 19.2.8、TypeScript 6.0.3、Vite 8.0.0 已对齐公共版本。

## 手动体验路径

1. 顶部选择“寻找回家的路”或“仓库逃生”，再选择交互事件。三个编辑面板共用项目、事件和目标。切换上下文会重置未提交草稿，切换模块标签不会重置。
2. **UI 流程**：选择流程界面、改提示文案/字符预算/安全边距/元素偏移，点击“运行 UI 校验”。通过后可创建映射提案；创建时服务器也会重新校验。
3. **音频工作室**：加载演示信号或选择 ≤ 4 MiB 的 16-bit PCM 单/双声道 WAV，查看真实本地分析、波形包络、峰值及近似 RMS 响度。浏览器按用户操作试听；修改 Mixer 后可创建绑定提案。
4. **特效 / Shader**：修改颜色、强度、频率、边缘宽度、画质及预算估算，启用当前事件的可选高亮，点击“校验配方与预算”。超预算结果来自模块规则，不是渲染测量；可以创建带风险说明的提案。
5. 右侧展开提案，审阅目标、前后值、验证与回滚计划，点击“批准本地提案”。模块现有 ChangeSet 审批方法记录固定本地审阅人、UTC 时间与内容证据。没有 Unity/Render 发布按钮或执行端点。

## 数据、API 与状态

- UI 数据复用 `modules/ui-studio/frontend/src/fixtures/keyDoorVisualFixture.json`、`modules/ui-studio/contracts/examples/warehouse-escape-ui-flow.json`；布局元素是模块内生成的可编辑演示草稿，不宣称已发布来源。
- 音频演示函数位于 `modules/audio-studio/backend/src/audio_studio/lab_api.py`，复用原确定性测试信号设计。上传音频仅在本地 API 内解析，不落盘、不上传第三方；返回分析记录，无伪造来源/已发布资产状态。
- 特效数据复用 `modules/vfx-shader/fixtures/{hero_home_highlight,warehouse_escape}.json`。仓库事件统一为既有音频模板的 `gameplay.switch.activated` / `gameplay.exit.unlocked`。
- `live`：UI 本地规则、用户 WAV 的本地分析确实执行；不表示 Unity 在线。
- `mock`：内置信号/配方、SVG 或 CSS 结构示意及特效预览计划。已有 fixture checksum 只描述原始 mock，不是当前编辑产物来源。
- `planned`：提案保存和本地批准后，外部发布仍未执行。
- `blocked`：Unity、Render、音频生成未连接。
- `cached`：本入口不产生此业务执行状态；TanStack Query 仅用于普通页面查询缓存。
- 写入请求仅接受 JSON，浏览器来源限所配置的 localhost URL。随机 `X-Lab-Session` 标识由当前标签页 sessionStorage 保存；分析/提案按此 ID 在 API 进程内隔离。它不是生产身份验证。

每个模块通过公开的 `create_lab_router()` 组合 FastAPI 路由；主入口不导入模块私有服务。Pydantic/dataclass OpenAPI 是网络数据结构的源头，`openapi-fetch` 使用自动生成的类型，不手写第二份网络接口。

```sh
pnpm --dir apps/labs/ui-audio-vfx generate:api
```

此命令从各公开路由生成对应模块 `frontend/src/lab-api.ts`。不是测试或构建。修改 API 后需重新生成；Python 开发服务不自动热重载，修改后应手动重启。前端由 Vite 热更新。

## 本轮验证记录

2026-09-05（Asia/Shanghai）只执行了启动/导入检查与一条最小本地主路径：

- 安装本 lab 依赖；公开路由导入与 OpenAPI 客户端类型生成成功。
- `pnpm --dir apps/labs/ui-audio-vfx dev` 启动 Web 4315 / API 8315 成功。初次沙箱内启动不可绑定端口，经授权在 localhost 启动成功。
- 浏览器载入三个模块入口，首页和项目/fixture/提案初始查询成功。
- 唯一动作烟测：选择 `prompt.key-picked` → 改为“已获得钥匙，可以回家了。” → UI 校验通过 → 创建提案 → 展开审阅 → 本地批准。
- 提案 `chg_54a817a9f8cc4f4089039298b67284df`；页面与 API 返回 `approved`、`local-reviewer`、`2026-09-04T20:59:30Z`。相应三个 POST 都返回 200；页面明确仍为 planned 外部发布未执行。
- 此前模块历史测试不计作本轮证据。无新增测试文件。

## Limitations

- **Not run / pending approval**：音频分析/上传/绑定动作，特效参数/预算/提案动作，仓库项目切换；完整单元、集成、E2E、安全、性能、类型检查和构建。启动时导入成功不等价于这些路径通过。
- 没有执行 Unity、Blender、Render、设备截图、playtest 或任何生产发布。CSS 高亮不模拟粒子渲染，RMS 不等于 LUFS，字符预算不等于真实字体排版测量。
- 会话数据不持久化，重启 API 后不可恢复。本地 reviewer 仅用于单机演示，不能作为生产审批授权。
- 安装提示 peer dependency 范围警告；本轮客户端生成与 Vite 启动成功，不声称完整工具链/类型兼容性已验证。
- 当前功能不需要 AI，因此没有执行 AI 命令，也未提供假的模型列表。用户指定：后续若需要 AI，必须使用 **CodeBuddy CLI**，并在前端提供实际可用模型选择；AI 接入和模型选择尚未实现。
