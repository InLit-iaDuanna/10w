# 统一制作分类与阶段衔接：给 GPT‑6 Pro 的讨论材料

我们正在开发 SceneOps Forge，一个以主对话为入口、可拉出并停靠专业工具的 AI 游戏制作工作台，希望用户从想法、可玩的草模初版，持续进入完整策划、分项细化、试玩和发布，每个阶段都延续同一个项目的真实产物。请先阅读本仓库代码，帮助我们讨论统一功能划分和少量可复用的游戏制作预设，不要立刻编写实现，也不要仅根据截图推断系统能力。宿主使用 React/TypeScript、Dockview、Python API 和模块注册体系，目前示例游戏采用 Three.js/TypeScript/Vite，仓库还包含 Blender、Unity 等集成，各条链路的完成度需要分别核实。我们的 test123 是第一人称波次生存射击原型，包含场景、玩家移动和视角、武器射击、敌人、波次、HUD、音效特效和流程状态，先前实际代码检查显示主要物体由代码生成几何体，并没有自动全部登记成专业编辑器可继续操作的模型资产。最近补通了“读取已有原型实际源码，整理策划和制作卡片”的流程：卡片绑定真实 source_ids，策划确认后可以在原工作区、原 Agent 会话中分项修改，再回到同一游戏构建和预览；示例生成了竞技场场景与画面、玩家视角与移动、武器与射击、敌人行为与受击、波次与生成、HUD 与结算界面、音效与特效反馈、流程状态与指针锁定八张卡。这解决了初版之后无处继续的问题，却没有解决生产结构复用：卡片仍由 AI 针对每个游戏自由命名拆分，主要是源码任务分类，换游戏就换一套，无法自然承接我们已经为建模、资产、材质、灯光和场景做好的专门功能。我们要求不同游戏共享稳定的功能分类、入口语义和数据关系，可以有少量经过讨论的预设细分，也可以合并相近功能，但不能每个游戏临时 DIY 顶层结构；一致不是强迫制作相同内容，而是复用专业工具、结构和阶段衔接，武器、敌人、谜题、作物等应成为统一体系内的对象或任务。现有宿主入口包括策划与制作卡片、制作进度、模型与资产、内置场景与资产、材质与灯光、环境场景、架构与源码、游戏试玩、导出、版本管理和本地服务；能力还不止这些，模块目录包含 concept-lab 概念设计、character-animation 角色动画、logic-studio 玩法和交互逻辑、ui-studio 界面流程、audio-studio 音频、render-ops 渲染、ai-playtest 试玩测试及问题回溯，以及 production-planner、engine-unity、version-collaboration、build-release 和 AI 执行、上下文、观察、恢复等基础能力。请全面盘点，区分宿主已接通的链路、模块已有但尚未接入当前游戏的实现、只有合同或模拟验证的部分，不要将模块 active 或存在 README 当成端到端完成。模型链路已有生成、GLB/FBX 导入、Blender 源保留、尺寸归一化、预览及资产版本；资产库包含项目资产和内置素材；场景模块包含资产实例化、变换及版本；材质模块已有 PBR、程序化图案、Shader 图、对象与材质槽定位、灯光环境、历史对比、保存应用和导出，文档明确区分编辑器预览灯光和真实游戏灯光。它们应在统一分类中有清楚的位置，并允许合理合并，不能直接把截图几个入口当最终答案。典型需求是第一阶段 AI 为玩法验证生成粗模，规整后得到有稳定身份、明确尺度、可编辑源、导出产物和版本的项目资产；第二阶段进入对应卡片就能编辑同一个模型，细化几何、材质、贴图、灯光或动画，并正确应用到原游戏目标实例，保留脚本、碰撞、行为和引用关系；共享模型应明确区分更新资产与更新单个实例。如果初版物体只存在于程序化代码中，应明确何时保留参数化生成器，何时提取或登记为资产，以及 GLB 无法保留哪些编辑信息，避免只有预览产物而失去可编辑性。请回答：统一分类应按生产专业、游戏系统、对象类型还是制作阶段组织，哪些固定为顶层，哪些属于对象列表、子任务、阶段状态或预设；请比较两到三套覆盖全部能力的精简方案，推荐一套并说明合并边界；少量游戏预设如何只改变能力启用和默认配置，而不复制出不兼容结构；统一卡片如何关联资产及其版本、场景实例、源码、行为组件、工具和验收状态，哪些关系一对多或多对多；草模阶段应遵循什么最小生成约定，既能快速试玩又能自然细化；test123 和现有自由拆分卡片怎样迁移，哪些自动映射，哪些需要人决定，避免重做游戏或丢失会话、代码和版本；是否需要明确的“整理进入细化”操作，是否真需要独立 Agent，还是现有会话按阶段调用工具即可，请用职责和产物解释；跨卡片依赖、外部代码修改与专业编辑器编辑如何保持一致，怎样防止 AI 下一轮重写覆盖已细化资产。最后请提供全量模块到统一功能分类及工具入口的映射表、草模到细化的完整数据流、最小数据示例、分步实施顺序和可观察的验收案例，并用射击与解谜或经营两种不同游戏证明结构可以复用，但不要宣称已经实测。我们希望先讨论透彻再修改实现，不接受仅改卡片标题或增设一个对话 Agent 就认定问题已解决。

## 代码阅读入口

- `apps/web/src/app/ShellWorkbench.tsx`：实际工具入口和宿主组合。
- `docs/module-map.md`、`modules/*/module.yaml`：全量模块及贡献；注册不等于完成。
- `modules/design-room/backend/src/sceneops_design_ai/existing_production.py`、`journey_models.py`、`journey.py`：源码整理、策划、卡片和状态。
- `modules/design-room/frontend/src/PlanningJourney.tsx`、`ProjectPlanningTools.tsx`：当前旅程和卡片。
- `modules/ai-agent-runtime/backend/src/sceneops_ai_agents/production_planning.py`、`native_production.py`：实际快照、原会话续作。
- `modules/ai-agent-runtime/frontend/src/DemoWorkbench.tsx`：源码卡片与试玩。
- `modules/asset-factory/README.md`、`modules/asset-library/README.md`：建模、导入、归一化、原生源与资产版本，继续追踪公开服务实现。
- `modules/world-composer/README.md`：场景实例和版本，继续追踪 environment_scene 实现。
- `modules/vfx-shader/docs/native-lookdev.md`、该模块 `backend/src/vfx_shader/lookdev_*.py` 和 `frontend/src/core/`：材质保存、应用、身份和游戏绑定。
- `modules/project-intake/backend/src/sceneops_project_workspace/`：工程内容与应用。
- `modules/concept-lab/`、`character-animation/`、`logic-studio/`、`ui-studio/`、`audio-studio/`、`render-ops/`、`ai-playtest/`、`production-planner/`、`engine-unity/`、`version-collaboration/`、`build-release/`（均在 modules 下）：其余功能边界与完成度。
- `architecture.md`、`product.md`、`design.md`、`FRONTEND_INTEGRATION.md`、`STATUS.md`：架构与演进记录，需与代码交叉核对。

## Limitations

本次是架构讨论用的源码快照，不是正式发布，未重新验证全部功能。历史文档有不同时期的设计和限制，需以具体实现与验证证据为准。test123 本地游戏工程及应用数据库不包含在此次同步中，游戏情况来自本会话此前的实际检查。统一分类和预设仍是待讨论需求，此次没有实施。
