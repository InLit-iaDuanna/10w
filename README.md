# SceneOps Forge

面向 3D 游戏制作的 AI 工作台。当前交互围绕单一主对话展开：创建文件夹项目、讨论 idea、显式进入 grill-me 对齐、确认大纲 v1，再进入 Three.js 方向与制作卡片。项目包含 Web 前端、Python API、功能模块以及 Blender、Unity 和 AI 提供方集成。

## 快速启动

准备 Node.js >= 22.12、pnpm 11.13.0、Python 3.12 和 uv。以下命令适用于 macOS / Linux。

```sh
git clone https://github.com/InLit-iaDuanna/10w.git
cd 10w/sceneops_forge_codex_full_pack_v3
pnpm install --ignore-scripts
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r services/api/requirements.txt
pnpm dev
```

打开 [Web 工作台](http://127.0.0.1:4300)，API 健康接口为 [api/health](http://127.0.0.1:8300/api/health)。启动器不会自动安装依赖或调用 AI。模型提供方需要单独配置；Blender、Unity 及对应插件按实际制作任务准备。

端口与 Python 路径可通过 `SCENEOPS_WEB_PORT`、`SCENEOPS_API_PORT`、`SCENEOPS_PYTHON` 指定。详细配置、数据保存和高级入口见 [应用 README](sceneops_forge_codex_full_pack_v3/README.md)。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| `sceneops_forge_codex_full_pack_v3/apps/web/` | 主 Web 工作台 |
| `sceneops_forge_codex_full_pack_v3/services/api/` | Python API 入口与依赖 |
| `sceneops_forge_codex_full_pack_v3/modules/` | 策划、资产、场景、制作和协作等功能模块 |
| `sceneops_forge_codex_full_pack_v3/packages/` | 公共合同、客户端与界面组件 |
| `sceneops_forge_codex_full_pack_v3/integrations/` | AI 提供方与外部制作工具集成 |
| `sceneops_ai_harness_v5/` | V5 架构与实施参考文档 |

## 文档导航

- [Agent-first 产品理解与下一步](sceneops_forge_codex_full_pack_v3/AGENT_FIRST_UNDERSTANDING.md)
- [游戏代码架构选择与真实工程里程碑](sceneops_forge_codex_full_pack_v3/GAME_CODE_ARCHITECTURE_MILESTONE.md)
- [当前状态与历史验证](sceneops_forge_codex_full_pack_v3/STATUS.md)
- [单人协作策划流程](sceneops_forge_codex_full_pack_v3/PLANNING_JOURNEY_STAGE1.md)
- [制作卡片模型流程](sceneops_forge_codex_full_pack_v3/CARD_ASSET_WORKFLOW_SMOKE.md)
- [架构](sceneops_forge_codex_full_pack_v3/architecture.md)与[模块合同](sceneops_forge_codex_full_pack_v3/MODULE_CONTRACT.md)
- [开发约定](sceneops_forge_codex_full_pack_v3/AGENTS.md)与[实施计划](sceneops_forge_codex_full_pack_v3/EXECUTION_PLAN.md)
- [第三方声明](sceneops_forge_codex_full_pack_v3/THIRD_PARTY_NOTICES.md)

## 上传与本地数据

仓库保存当前 `codex/harness-v5` 分支的源码、依赖清单、锁文件、测试和文档，以及该分支的提交历史。其他本地分支和独立 worktree 未在此次上传范围内。

`node_modules`、Python 虚拟环境、缓存、临时产物、环境密钥配置及 `.local/` 不纳入 Git。`.local/` 含本机项目数据库、聊天记录、资产和可能的提供方凭据；GitHub 源码仓库不是这些运行数据的完整备份。需要恢复原有数据时，应在停止应用后单独备份完整数据目录；外部项目文件夹也需要独立备份。

## Limitations

项目仍在开发，已有部分真实 Blender / Unity 路径的定向验证记录，但不代表完整游戏生产链已经验收。各项验证范围以对应文档日期为准。本次 GitHub 上传与 README 整理仅核对文件同步、文档链接和启动命令，不代表已重新安装、启动、构建或运行完整测试。
