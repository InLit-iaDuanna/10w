# 当前 V5 能力目录

来源：`modules/ai-pipeline-compiler/backend/src/sceneops_ai_pipeline/capabilities.py`。HTTP 目录仅声明能力，不会触发生产。

| 能力 ID | V5 接入状态 | 实际边界 |
| --- | --- | --- |
| `workspace.project.read` | 有本地 handler | 读取当前项目记录；不是制作产物 |
| `workspace.draft.read` | 有本地 handler | 读取明确项目模块草稿；草稿不等于已执行 |
| `ai.agent.assess` | 有 AI handler | 结构化分析/建议；真实调用未验证 |
| `blender.scene.inspect` | planned / 无 handler | Blender 场景检查 |
| `blender.asset.export` | planned / 无 handler | 资产导出 |
| `character.prepare` | planned / 无 handler | 角色动画制作 |
| `world.apply` | planned / 无 handler | 场景写入 |
| `logic.apply` | planned / 无 handler | 玩法逻辑写入 |
| `ui.publish` | planned / 无 handler | 界面资源发布 |
| `audio.publish` | planned / 无 handler | 音频资源发布 |
| `vfx.publish` | planned / 无 handler | 特效发布 |
| `render.execute` | planned / 无 handler | 生产渲染 |
| `unity.asset.import` | planned / 无 handler | Unity 资产导入 |
| `unity.build` | planned / 无 handler | Unity 构建 |
| `playtest.run` | planned / 无 handler | 游戏游测 |
| `version.merge` | planned / 无 handler | 版本合并 |

外部 connector 当前全部 blocked；运行 authority 不含 `production:execute`。注册表中前三项的 `execution_mode=live` 表示 handler 通道，不是已执行成功证据；真实结果模式、状态及证据须以具体 Run 为准。页面“本地界面”也不代表任务已执行。
