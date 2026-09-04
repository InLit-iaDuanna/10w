# 前端集成

模块注册两个 lazy editor：`concept.moodboard` 和 `concept.style_bible`。编辑器只调用 typed command client，不直接 fetch、不访问 Dockview、不访问图像服务。

Moodboard 提供 loading、empty、failed、offline、permission、disabled 和 ready 状态。图像生成 offline 时会引导用户走 `concept.reference.import`，因此核心导入流程不依赖生成服务。

ModuleRuntime 到位后需要完成两项组合工作：

1. 用 generated module catalog 注册 `moduleContribution`；
2. 用共享 generated OpenAPI client + TanStack Query 查询 `GET /v1/concepts/{concept_id}/review-workspace`，构造 editor presentation，并传给 lazy component。

这些组合工作属于 core runtime/shell，不应复制到本模块。对话和任务链接都调用公开 `openConcept()` handler，返回需确认的 `workbench.open_editor` action。
