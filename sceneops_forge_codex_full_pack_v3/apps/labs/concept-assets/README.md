# 工作台 03 — 概念设计与资产制作

本入口连接 concept-lab → AssetSpecDraft → asset-factory → asset-library，复用原 Blender adapter 的显式 deterministic mock。入口只负责启动、依赖、API 注册与前端组合；领域操作位于模块公开接口。原 06 的整个 `modules/concept-lab` 已移动到应用根下，源码、测试、fixtures、合同、文档均保留。

## 独立启动

在本工作树的 `sceneops_forge_codex_full_pack_v3` 目录执行（Node 22、Python 3.12、uv）：

```sh
uv venv apps/labs/concept-assets/.venv --python 3.12
uv pip install --python apps/labs/concept-assets/.venv/bin/python -r apps/labs/concept-assets/requirements.txt
pnpm --dir apps/labs/concept-assets install --ignore-scripts
npm --prefix apps/labs/concept-assets run dev
```

安装主动跳过第三方 lifecycle scripts；不需要批准 esbuild 安装脚本，平台预编译依赖即可运行。当前宿主 pnpm 11 在 `pnpm dev` 前自动检查依赖，因被阻止的 esbuild lifecycle 返回 `ERR_PNPM_IGNORED_BUILDS`，所以本工作树使用已验证的 `npm … run dev`（脚本内部不安装、不构建）。也可以进入入口目录运行 `node dev.mjs`。没有修改宿主权限或安全配置。

Web：<http://127.0.0.1:4312>；API：<http://127.0.0.1:8312/docs>。

`WEB_PORT=4412 API_PORT=8412 npm --prefix apps/labs/concept-assets run dev` 可显式改端口。绑定仅 localhost，端口占用即报错，不终止其他进程。Ctrl-C 仅停止本命令启动的子进程。无需其他工作台。

## 手动验证路径

1. 首页点“打开工作台”，在概念板载入 Mock 参考方案。
2. 检查右侧风格规格、尺寸、平台预算和禁止元素；可以重复载入并选择方案进行对照。
3. 填写评审文字，添加评论，点击“记录风格符合证据”，再“批准概念”。缺少证据会显示服务返回的失败原因；拒绝保留原方案。
4. “编译 AssetSpecDraft”自动打开生产页；查看完整草稿、公开转换结果及生产 ChangeSet。
5. 点 Dry-run 查看 planned 步骤。审阅 ChangeSet 后点“批准此 ChangeSet 并制作 Mock 资产”。这是另一项显式生产批准。
6. 查看 succeeded / mock、步骤与检查结果，点“检查已入库 Mock 版本”，搜索名称或 ID，展开版本的几何信息、来源、身份、产物和质量记录。

业务请求经过实际本地 ConceptLabService、AssetPipelineService 和 AssetLibraryService。mock 产物仍经过既有审批作用域、路径、质量、身份与发布验证。UI 不宣称 mock GLB/FBX 是真实 Blender 资产。

## 数据与状态

- 默认概念和参考：`modules/concept-lab/backend/src/concept_lab/fixtures/hero-key-concept.json`、`generation-mock.json`。
- 图形仅是明确标记的钥匙符号示意，不是生成图片或渲染证据。
- 内存会话 + 系统临时目录 `sceneops-concept-assets-*`，与项目源文件隔离；重启即新会话。一个会话制作一个资产规格，成功后禁止重复发布。
- 本地领域处理实际执行，外部执行模式始终 `mock`；Dry-run 是 `planned`。
- 实际图像生成、Blender、渲染、Unity 未启用，外部真实运行 `blocked` / `planned`；没有自动降级或隐式调用。
- 本入口没有联网 AI 对话，首页按钮仅打开工具；没有复制 Shell 或核心 kernel。

## 公开合同

`asset_factory.asset_spec_from_concept(draft, asset_id=..., category="prop")` 返回 `ConceptAssetHandoff`。保留完整草稿中的审批、项目/任务、参考、材质、纹理预算和风格字段，同时映射 AssetSpec 的名称、用途、几何预算和米制尺寸。轴映射显式为 x=width、y=depth、z=height，右手 Z-up。草稿没有声明源坐标轴，所以消费者在生产前必须审阅该约定。

`ConceptAssetLab` 通过 concept_lab 公开服务取得已批准草稿；不接受浏览器提交的伪造批准草稿。生产批准只针对服务端保存的完整 ChangeSet 和现有 allowlisted workflow scope，使用原审批 authority。

本地 API：`GET /api/workspace`、`POST /api/actions`。`LabAction` 是 Pydantic 枚举命令，响应为 `LabSnapshot`。`openapi.json` 为实际 app 导出；`modules/asset-factory/frontend/src/generated/lab-api.ts` 由 openapi-typescript 生成。组件统一通过 labClient 调用，服务器状态由 TanStack Query 管理。

生成合同（不是测试）：

```sh
cd apps/labs/concept-assets
.venv/bin/python -c 'import json; from api import app; open("openapi.json", "w").write(json.dumps(app.openapi(), ensure_ascii=False, indent=2))'
node node_modules/openapi-typescript/bin/cli.js openapi.json -o ../../../modules/asset-factory/frontend/src/generated/lab-api.ts
```

## 本轮精确验证

2026-09-05，仅执行启动/导入检查 + 一条最小本地主路径：

- Python `api` 导入成功，OpenAPI 成功导出；Web HTTP 200；浏览器确认 React 首页正常加载。
- 单一 API 主路径：generate → evidence → approve → compile → preview → produce。
- 状态序列：in_review → in_review → approved → approved → planned → succeeded；最终 execution_mode=mock，error_code=null，资产库恰有 1 个发布版本。
- 独立启动 `npm --prefix … run dev` 成功，Vite 4312 / Uvicorn 8312。
- 未运行任何完整单元、集成、E2E、安全、性能、类型检查、构建、Blender、Unity、渲染或 AI playtest 套件，均 **not run / pending approval**。来源提交的历史测试结果不作为本轮证据。本轮未增加测试套件。

## Shell 整合请求

已只读对齐公共骨架提交 `4f3416e` 的 package.json/dev 接口，未编辑根 workspace、锁文件、脚本或共享 runtime。Shell 合并时请将本 lab 的 React 19.2.8、ReactDOM 19.2.8、TanStack Query 5.90.21、TypeScript 6.0.3、openapi-typescript 7.10.1 与 Vite 依赖纳入根锁文件；当前本入口独立使用 Vite 6.4.1，本地锁文件仅属于该入口。根统一启动 `pnpm lab concept-assets` 可消费同一 dev 脚本，宿主 pnpm 自动依赖检查问题应由 Shell 工具链统一处理，不通过修改权限规避。

## Limitations

内存与临时文件不提供跨重启持久化、多用户权限、异步 worker 队列或任意项目导入。参考图是 fixture，风格符合证据是人工声明；材质/纹理预算保留在 handoff 中，现有工厂尚不全面执行概念风格约束。生产步骤同步执行且仅 mock；取消、重试、回滚保留在原模块公开接口，但本入口尚未提供对应按钮。真实 3D 预览与外部工具仍待后续授权整合。
