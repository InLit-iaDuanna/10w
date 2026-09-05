# AI 生产计划

V5 AI Harness 垂直模块。公开 Python 包：`sceneops_ai_pipeline`；Pipeline 合同来自 `sceneops_harness`，不另复制网络模型。

当前 UI 刷新简化未选择项目的空态，保留「选择或创建本地项目」回调；三个步骤仅解释审阅/确认/观察流程，不代表已经开始执行。已有计划、运行和 AI 行为不变。

默认不执行；由明确用户请求或已授权的类型化 Pipeline 调用。真实外部能力不因本模块存在而变成 Live。遵守项目隔离、取消和预算边界。测试执行状态：not run，仅主代理进行最小烟测。
