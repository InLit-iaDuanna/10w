# 工作台 04 — 角色与动画

独立 Web 入口，直接组合 `@sceneops/character-animation` 的公开工作台和后端 contribution。无需启动 Shell 或其他工作台。业务、六个懒加载编辑器、命令、检查、比较与映射服务均复用原模块；未建立第二套 core/runtime。

## 首次安装

需要 Node 22.12+、pnpm 11.13.0、Python 3.9+。从应用根执行：

```bash
pnpm install --lockfile=false --ignore-scripts
python3 -m venv apps/labs/character-animation/.venv
cd apps/labs/character-animation
.venv/bin/python -m pip install -r requirements.txt
cd ../../..
```

不写共享锁文件。保留模块原 npm lock 作为旧版本记录；当前入口使用 pnpm workspace，勿在模块目录执行 `npm ci` 来启动本工作台。

## 一条命令启动

从应用根执行：

```bash
CHARACTER_LAB_PYTHON="$PWD/apps/labs/character-animation/.venv/bin/python" pnpm --dir apps/labs/character-animation dev
```

已在当前 `python3` 安装后端依赖时可直接执行：

```bash
pnpm --dir apps/labs/character-animation dev
```

- Web：<http://127.0.0.1:4313>
- API / OpenAPI：<http://127.0.0.1:8313/docs>
- 只监听 `127.0.0.1`，Vite strictPort；端口占用会失败，不杀其他进程。
- Ctrl+C 关闭本启动器的子进程。API 进程退出也会停止本次 Web。
- 浏览器通过 Vite 同源 `/api` 代理访问 API，不需放宽 CORS。

## 手动操作

1. 查看归家者角色来源、稳定 ID、功能/任务关联。
2. 点击「运行本地检查」，查看右侧 15 项原始示例证据；切换 Rig 和蒙皮编辑器。
3. 打开动画时间线，改时长、循环、Root Motion 或事件时间，拖动时间游标；再运行检查，查看变化。缩短时长不自动缩放采样，越界会有检查证据。
4. 点击「与原始片段比较」查看版本差异。草稿采用新 Clip 版本 ID 并更新 Animator 引用，保留原版本；不发布到生产资产库。
5. 查看 Animator 状态转换及重定向骨骼映射。外部重定向和预览明确 blocked。
6. 「重置演示」丢弃当前草稿；到 Unity 页填三个不同 ID，生成 planned / waiting_approval / dry_run 提案，查看影响、验证、回退和审批要求。

## 数据与状态

确定性数据：`modules/character-animation/contracts/examples/remember-home-character.json`，经模块 fixture 导入，每个页面独立复制。浏览器草稿刷新后丢失；服务内存版本在 API 重启后清空，不接生产目录。

- 本地检查、版本比较、提案创建：真实调用现有服务；输入为 `mock` 演示数据。
- Unity 提案：`planned`，没有执行或模拟批准按钮。
- Unity、Blender、自动绑定、外部重定向、固定相机渲染：`blocked`，默认 Offline adapter。
- 草稿 provenance 校验值沿用 fixture 占位值，仅供 mock 演示，不是新内容摘要，不得用于发布。
- 时间游标是元数据编辑，不播放 3D 动画；不加载或渲染源模型。

## 本轮最小烟测（2026-09-05）

安装：`pnpm install --lockfile=false --ignore-scripts` 成功，存在 peer dependency 提示；未运行额外依赖审计。

启动：`pnpm --dir apps/labs/character-animation dev`，Vite 8 与 Uvicorn 启动成功。沙箱第一次禁止监听；授权 localhost 监听后成功，未占用其他进程。

入口 HTTP 检查：`/`、`/src/main.tsx`、`/src/transport.ts`、工作台 TSX 的 Vite 转换请求均 HTTP 200。不是浏览器渲染/E2E 验证。

唯一主路径：通过 Web 同源代理 POST 原始 fixture 到 `inspect` → `passed`、15 checks、`mock`；把返回 bundle POST 到 `unity-mappings/propose` → `planned`、`waiting_approval`、`dry_run=true`。没有调用 execute。

Not run / pending approval：完整单元、集成、组件、类型检查、E2E、安全、性能、构建；动画草稿/比较及页面交互需手动验证；未调用 Unity、Blender、渲染或 AI playtest。最后仅调整操作期间表单禁用与文档，未重复主路径烟测。

## 公共整合请求

- 已引入 Shell 共享启动骨架提交 `4f3416e830e1b99a0c2a2df18150d198ac7f21ae`，未改根启动器。
- 根锁文件由 Shell 统一生成；请收录本 lab 的 workspace 依赖。现有 npm lock 保留，未覆盖。
- 模块新增公开 `CharacterAnimationWorkbench` 和 generated `CharacterAnimationPaths` 类型出口，供该组合入口消费；网络合同、后端服务与审批规则没有改动。
- React/ReactDOM 19.2.8、TypeScript 6.0.3；新增 TanStack Query 5.90.21（MIT，服务结果状态）、openapi-fetch 0.15.0（MIT，生成 OpenAPI 类型驱动的传输）、Vite 8.0.0（MIT，开发服务）、Uvicorn 0.39.0（BSD-3-Clause，ASGI 启动）。
