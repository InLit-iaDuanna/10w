# S1 技能来源

适配版本：`sceneops-s1.1`。上游：https://github.com/majidmanzarpour/threejs-game-skills
固定提交：`e5f301d548bb18c530afbece78cd25082f4cda9c`。
保留的版权和完整许可见本目录 `LICENSE`。未复制示例素材、scaffold、依赖或执行脚本。

| SceneOps 资源 | 上游路径（均相对 skills/） | 适配说明 |
| --- | --- | --- |
| prompting.py 主制作角色 | threejs-game-director/SKILL.md、references/asset-recovery.md | 小任务保持范围、代表性场景、连续工作；保留原任务/预算/授权，不按凭据自动生成 |
| sceneops-threejs-gameplay/SKILL.md | threejs-gameplay-systems/SKILL.md、references/genre-design.md、references/physics-engine-selection.md | 对象组件/ECS/Miniplex 和原包管理器优先；无失败玩法有效；不导入 Rapier 偏好或固定策划文档 |
| references/time-and-state.md | threejs-gameplay-systems/references/game-feel.md、references/physics-engine-selection.md | 摘取输入/模拟/反馈与更新时间原则，加入冷却/暂停/重开适配；不复制震屏和音频代码 |
| sceneops-threejs-debug/SKILL.md | threejs-debug-profiler/SKILL.md、references/debug-playbook.md | 具体故障、归属与原路径复查；未观察不声称看过画面 |
| sceneops-threejs-qa/SKILL.md | threejs-qa-release/SKILL.md、references/release-checks.md | 有界类型化检查、结果新鲜度、分别报告验证范围；不引入浏览器执行器或固定 AAA 分数 |

这是应用随包知识，独立于用户全局 skill 安装和游戏目录同名文件。`skill_context.py` 只加载本包已知路径，记录真正读入的路径、适配版本与上游提交到已有 Harness 结果日志。缺资源返回明确诊断，不编造成功记录。

后续更新需人工审阅已采用文件的差异，并同步适配版本与对应测试；本轮不在运行中联网获取上游。回退本轮产品代码可恢复旧装配，不重写游戏成果或改变任务授权。
