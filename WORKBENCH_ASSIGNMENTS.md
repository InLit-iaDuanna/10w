# SceneOps 独立 Web 工作台派发

用户已同意按可独立启动、独立手动验证的工作台组织开发，复用已有模块，不再把每份提示词都做成孤立交付。任务仅通过 Codex 官方任务功能派发，统一使用 `gpt-6-astra` / `medium`；禁止 Codex Bridge、cbridge、GO！WORK！或额外嵌套派发。

## 用户约束

- 仅允许最小烟测：启动/导入检查加一条最小本地主路径。不得自动执行完整单元、集成、E2E、安全、性能、构建、Unity、Blender、渲染或 AI playtest 套件。可以编写测试；未执行必须标明 `not run` / `pending approval`。
- 完全权限不扩大测试授权，也不允许绕过产品已有的审批、安全、身份与来源链机制。官方派发接口没有权限模式参数，不得声称已由提示词设置完全权限。
- 保留原工作树及未提交代码；只在本任务工作树内整合。不得自动合入主工作树，不得删除旧任务/工作树，不得发布部署。
- 不增加没有明确必要性的哈希、冻结合同、基线、门禁或兜底。保留已有安全措施，以类型、版本、主键、事务和正常算法优先解决问题。

## 目录与协作

应用代码统一在 `sceneops_forge_codex_full_pack_v3/` 内。每个独立入口为 `apps/labs/<lab-id>/`；业务逻辑仍在现有 `modules/` 内，通过公开接口复用，不能复制出第二套业务实现。

各工作台必须有独立的前后端启动方式，用户无需启动其他工作台即可访问。推荐从应用根执行 `pnpm --dir apps/labs/<lab-id> dev`，一个命令启动该工作台所需的 Web 和本地 API。Shell 任务负责可选的统一 `pnpm lab <lab-id>` 入口和根工具链；其他任务只拥有各自 lab 的依赖/脚本，不争改根 workspace、锁文件或共享 runtime。若确需共享修改，在本 lab 文档列出具体请求。

Web/API 仅绑定 localhost；默认端口见下表，占用时明确报告或接受显式端口参数，不结束其他进程。提供清晰标注的确定性演示数据，真实调用复用业务服务，外部适配器用明确的 mock；未连接的 Unity/Blender/ComfyUI 等不得冒充 live。

公共实现优先复用原 01 任务的 core packages/module runtime，提交 `477e673e9c9daa8414da5c9e74b14ad0ff542bd7`。需要时引入同一提交，不另建 kernel。原 03 任务的 Shell 使用 React/ReactDOM `19.2.8`、TypeScript `6.0.3` 和 Dockview `8.2.0`，工作台前端优先对齐已有依赖。Smoke 政策提交为 `ecc532f0a3481a976e8a519b448fb4e042836855`。

## 本轮任务

| 工作台 | 原提示词 | 派发方式 | Web/API 端口 | 交付重点 |
| --- | --- | --- | --- | --- |
| shell | 01+02+03 | 新整合任务 | 4310/8310 | 共用运行时、纯对话首页、四边停靠、独立入口和统一启动说明 |
| project-planning | 04+05 | 新整合任务 | 4311/8311 | 项目导入/创建、设计规格、生产任务与依赖图 |
| concept-assets | 06+07 | 新整合任务 | 4312/8312 | 概念审核到 AssetSpec、资产库与生产队列 |
| character-animation | 08 | 继续原任务 | 4313/8313 | 角色、骨骼、蒙皮、动画时间线与映射提案 |
| world-logic | 09+10 | 新整合任务 | 4314/8314 | 场景对象、空间批注、玩法图与对象绑定 |
| ui-audio-vfx | 11 | 继续原任务 | 4315/8315 | UI、音频和特效编辑统一入口 |
| render-ops | 12 | 继续原任务 | 4316/8316 | 配方、队列、变体比较、来源链和写回提案 |
| unity-build | 13+16 | 新整合任务 | 4317/8317 | Unity 连接/命令状态、构建矩阵和发布提案 |
| version-review | 14 | 继续原任务 | 4318/8318 | 版本差异、评审、评论与审批 |
| ai-playtest | 15 | 继续原任务 | 4319/8319 | 测试场景、运行证据、Issue Backpin 和修复提案界面，不实际跑 playtest |
| integration-ops | 19 | 继续原任务 | 4320/8320 | 集成健康、Worker、日志、进度与诊断 |
| demo-judge | 17+18+21 | 本轮不启动 | 4321/8321 | 功能工作台完成后再讨论演示交付 |

00 和 23 不重跑；20、22 保持暂停。本轮不单开全局审计、验收、集成或文档任务；各功能自带必要启动说明与最小烟测记录。

## 既有成果位置

以下均为旧任务的源工作树，供只读读取或按提交整合；不得在来源工作树改写。

| 原任务 | 工作树 | 已确认 HEAD |
| --- | --- | --- |
| 01 | `/Users/isduanna/.codex/worktrees/3571/10w` | `477e673e9c9daa8414da5c9e74b14ad0ff542bd7` |
| 02 | `/Users/isduanna/.codex/worktrees/7f66/10w` | `1a14081609c6459aa86bdd5318d18078853084a7` |
| 03 | `/Users/isduanna/.codex/worktrees/4237/10w` | `1eca516fc1666919a81a567da5fef02613eb0609` |
| 04 | `/Users/isduanna/.codex/worktrees/112a/10w` | `8c9829219432c50bc9ee5c5177d817b47ceba266` |
| 05 | `/Users/isduanna/.codex/worktrees/7a1c/10w` | `6581d1f8d19df5cf6d482cad0345a4935400612a` |
| 06 | `/Users/isduanna/.codex/worktrees/eadd/10w` | `f98b18af6029409c42ca637909d7457678ad5cb4` |
| 07 | `/Users/isduanna/.codex/worktrees/97fc/10w` | `79c59c677c6c7311bbc1e837fae702cd5f1d9eae` |
| 08 | `/Users/isduanna/.codex/worktrees/8c8d/10w` | `e30adad84194bed6ecc0a65ce8f25f2f564e6686` |
| 09 | `/Users/isduanna/.codex/worktrees/cec6/10w` | `9fc484c86d31df81105768afc26d52233322df26` |
| 10 | `/Users/isduanna/.codex/worktrees/272e/10w` | `0bb6b75d8d5dd88f82428123130965ab8b939e64` |
| 11 | `/Users/isduanna/.codex/worktrees/fa66/10w` | `1409c4175704e6ecc6a42227308d8256b9d08e32` |
| 12 | `/Users/isduanna/.codex/worktrees/1b38/10w` | `9e64356027a1b934538dbb931a40f43b9cf44601` |
| 13 | `/Users/isduanna/.codex/worktrees/2bcb/10w` | `d723be4dc99424d7fe468afafec2315d277fe9f0` |
| 14 | `/Users/isduanna/.codex/worktrees/1000/10w` | `cb44f17f11e93d528d5a44a99a31c38a47d26cde` |
| 15 | `/Users/isduanna/.codex/worktrees/0395/10w` | 原始提交；`modules/ai-playtest` 实现尚未提交，继续原任务保留它 |
| 16 | `/Users/isduanna/.codex/worktrees/b295/10w` | `f6093ab71750693786ffde4310fbf6f6a519cbbf` |
| 19 | `/Users/isduanna/.codex/worktrees/0a18/10w` | `a5f29af65f446244a7fe951d034a135ef6a7f1af` |

注意：原 06 成果位于工作树根的 `modules/concept-lab/`，不同于其他模块的位置。Concept-assets 整合任务应保留实现并归位到应用根下，不可因路径不同遗漏。

## 交付说明

每个任务最终用中文报告工作树绝对路径、独立启动命令、localhost URL、可手动验证的操作、精确烟测结果、未执行的测试/外部功能和提交号。只有模块代码没有可启动 Web 不算完成。不要把原先测试结果当作这次组合入口通过的证据。

## 已派发的官方任务

本轮 5 个新整合任务与 6 个原任务均已收到派发并进入执行。任务执行参数为 `gpt-6-astra` / `medium`；权限模式未通过接口变更。下表用于后续继续任务，工作台尚不代表全部实现完成。

| 官方任务标题 | 任务 ID | 工作树 |
| --- | --- | --- |
| 工作台 01 — 对话与工作台基础 | `01a06e25-7647-7b93-81c5-fed94f6734c5` | `/Users/isduanna/.codex/worktrees/73a5/10w` |
| 工作台 02 — 项目设计与生产计划 | `01a06e25-814c-7a11-83ae-65790789b726` | `/Users/isduanna/.codex/worktrees/7ed0/10w` |
| 工作台 03 — 概念设计与资产制作 | `01a06e25-8dd0-7d72-92bb-122907a65067` | `/Users/isduanna/.codex/worktrees/9654/10w` |
| 工作台 04 — 角色与动画 | `01a06d10-32e2-7ee3-904b-7cf16f7950c5` | `/Users/isduanna/.codex/worktrees/8c8d/10w` |
| 工作台 05 — 场景与玩法逻辑 | `01a06e25-99b1-7181-93e0-faaf2cbaa55c` | `/Users/isduanna/.codex/worktrees/fe71/10w` |
| 工作台 06 — UI、音频与特效 | `01a06d10-5891-7942-9b32-1838a0e93033` | `/Users/isduanna/.codex/worktrees/fa66/10w` |
| 工作台 07 — 渲染与 AI 变体 | `01a06d10-648b-7b01-ad3a-ac35053a975c` | `/Users/isduanna/.codex/worktrees/1b38/10w` |
| 工作台 08 — Unity 与构建发布 | `01a06e25-a66b-74d3-83ab-41245ccc69bc` | `/Users/isduanna/.codex/worktrees/d13d/10w` |
| 工作台 09 — 版本与协作评审 | `01a06d10-81f7-7831-accb-4f54eeb48743` | `/Users/isduanna/.codex/worktrees/1000/10w` |
| 工作台 10 — AI 测试与问题定位 | `01a06d10-90b3-7e41-bedd-0f1271c4bcb0` | `/Users/isduanna/.codex/worktrees/0395/10w` |
| 工作台 11 — 集成状态与运行日志 | `01a06d10-c6bb-74c0-9898-70ef0b04c1b0` | `/Users/isduanna/.codex/worktrees/0a18/10w` |

共享启动骨架已由 Shell 任务提交：`4f3416e830e1b99a0c2a2df18150d198ac7f21ae`，来源 `/Users/isduanna/.codex/worktrees/73a5/10w`。其余 10 个任务已收到复用通知；是否需要引入由各任务结合当前工作树判断，不得覆盖未提交改动。
