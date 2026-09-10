# UI Studio

UI Studio 把游戏 UI 流程、HUD、菜单、任务提示和 Unity 映射变成可审查的数据。此垂直切片已包含“找到钥匙 → 门锁提示 → 门解锁”的反馈流程，以及可配置的 Warehouse Escape 模板示例。

## 公开接口

- 前端：`frontend/src/index.ts` 导出 `moduleContribution`、编辑器、命令和 query keys。
- 后端：`ui_studio` 包导出 `UiStudioService`、UI 数据契约、`ChangeSet`、`UnityUiAdapter` 和路由描述。
- 编辑器：`ui.flow`、`ui.preview`；命令：验证流程、提议映射、批准、发布。

## 安全与执行状态

Unity 是可选集成，只能通过公开的 `UnityUiAdapter` 协议接入。没有 Unity 时，前端命令给出明确的 offline 状态，UI 流程创作与验证仍可使用；模块可由 `ui_studio` 功能开关禁用。任何 AI 或自动生成的映射先产生 `proposed` ChangeSet，只有明确批准后才可调用发布。

当前实现为确定性 `mock`：不会访问 Unity、不会写工程文件，也不会把模拟结果表示为 live。`fixtures/keyDoorVisualFixture.json` 是显式 mock 视觉回归基线，不是截图或缓存实跑结果。结构化视觉回归比较配置、锚点和提示内容；像素截图比较仍为 planned。编辑器在 loading、empty、failed、offline、permission、disabled 时都会显示中文状态，并通过 props 暴露本地化文案编辑、分辨率/安全区域与验证或 diff 状态。

映射产物溯源记录来源项目/版本/可选提交、关联 `sceneops_id`、配方与工作流版本、创建者、模式、UTC 时间、校验和、审批状态；AI 产物额外要求 provider、model、workflow hash、prompt、seed 与参数。发布前会验证完整溯源、审批人和审批时间，以及返回的 mapping/prefab/Canvas 是否与批准目标一致。

## 验证

```sh
cd sceneops_forge_codex_full_pack_v3/modules/ui-studio
PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v
cd frontend && npm test
```

覆盖 manifest/公共 API、流程成功与失败、元素安全区域、本地化溢出、视觉 fixture、禁用/离线展示、编辑器状态、溯源、全部事件 JSON Schema、Unity 协议与完整 ChangeSet 批准流程。

## 限制

根运行时和 engine-unity 的公共实现尚未存在，因此这里仅声明协议和 mock。实际 Unity 映射、像素截图比较、core-kernel 命令契约替换及 OpenAPI 路由注册需要由相应的宿主/engine-unity 所有者实现，且不得绕过本模块的 ChangeSet 批准语义。

统一应用现公开 `loadIntegratedWorkbench()`；空态、自有草稿、样例边界与验证限制见 [统一编辑器说明](docs/unified-workbench.md)。

统一工作台从 `prj_<uuid>` 项目身份提取稳定 UUID 作为 `X-Lab-Session`，并同时发送项目作用域；UI、音频和 VFX 提案因此保持项目隔离且满足后端会话合同。无请求参数的音频夹具检查仍发送显式空 JSON 写入体。
