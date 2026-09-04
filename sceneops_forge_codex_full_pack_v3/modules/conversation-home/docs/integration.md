# Conversation Home 接入说明

## 注册

模块运行时应从 `module.yaml` 生成 catalog，并从 `frontend/src/index.ts` 读取 `moduleContribution`。禁止在 Forge Shell 中硬编码 `assistant.conversation`。

```text
module.yaml
→ manifest/dependency validation
→ generated frontend catalog
→ EditorRegistry
→ lazy load assistant.conversation
```

`core-kernel` 和 `module-runtime` 是声明依赖。`llm-provider` 是可选集成：缺失时首屏仍能显示历史和命令入口，但发送区域必须展示 Blocked/Disconnected 原因，不能伪装成本地 AI。

## Home startup

Shell 读取 `chatOnlyHomeFixture` 时应遵守：

1. Fresh launch 且没有已保存布局、deep link、Judge Mode 时，使用 Home fixture。
2. Fixture 只有 `assistant.conversation`，四边 Drawer 都为 `hidden`。
3. 有已保存布局、deep link 或 Judge Mode 时，本模块返回 `delegated`，由 Shell 选择对应布局；不能额外自动打开模块。
4. 四边 hot zone、peek/pinned、Dockview 与布局 undo 都由 `forge-shell` 实现。

## WorkbenchCommandBus

应用将唯一的 `WorkbenchCommandBus` 适配到 `WorkbenchCommandBusPort`：

- `inspect`：返回命令可用性、缺失权限、缺失集成、审批状态、`layoutEffect` 和后续命令；
- `preview`：只生成预览，不改布局；
- `execute`：使用相同 command ID 和 input 执行，并由 Core 再次实施权限/审批检查。

本模块的 coordinator 不持有权限，不接收 `bypass`、`force` 或任意 shell/tool payload。Action `type` 与 command ID 一致，因此不存在第二份 action-to-handler 分发表。`workbench.open_editor` 或任何报告 `layoutEffect: material` 的命令都必须走预览与显式确认。

三个写操作 `project.create`、`feature.create`、`workflow.run` 都要求 input 中存在 stable `changeSetId`。组合根必须让该 ID 指向 Core 中真实、可审计的 ChangeSet；命令执行仍经过 Core 的权限和审批策略，不能把 `changeSetId` 当作批准凭据。

组合根通过 `createConversationEditorRuntime` 同时注入 Query-backed integration availability 和当前 `WorkbenchContext` 摘要。它们不写入 Editor layout state；layout 只保存未发送草稿与附件元数据，避免把 server/domain state 复制进工作区布局。

## ConversationTransport

LLM 或 API 集成实现 `ConversationTransport`：

```ts
interface ConversationTransport {
  start(request: ConversationRequest, signal: AbortSignal): Promise<ConversationRun>;
}
```

`ConversationRun.mode` 必须是 `live`、`cached`、`mock`、`planned` 或 `blocked`。流只产生版本化文本增量、结构化卡片与完成事件。取消使用同一个 `AbortSignal`；失败通过 `ConversationTransportError` 保留错误码、可重试性、缺失权限/集成和有效后续命令。

## 附件暂存

组合根还需注入 `ConversationAttachmentStager`：

```ts
interface ConversationAttachmentStager {
  stage(
    sources: BrowserAttachmentSource[],
    signal: AbortSignal,
  ): Promise<ConversationAttachment[]>;
}
```

浏览器 `File` 或 transient `browserEntry` 只在调用期间作为 source 交给 adapter；目录 adapter 可用 typed entry reader 遍历内容，再执行受控上传或导入暂存并返回 stable `attachmentId`。只有返回的附件元数据进入 Editor local state 和消息记录，原始路径、句柄与文件字节都不得序列化。目录 source 若尚无可用项目导入能力，应抛出可见的结构化失败，而不是伪造已导入结果。

## 持久化

组合根创建 `ConversationRepository`：

```ts
const repository = new ConversationRepository(
  window.localStorage,
  window.sessionStorage,
);
```

- `{ kind: 'project', projectId }` 只写入 persistent storage；
- `{ kind: 'pre_project', sessionId }` 只写入 temporary storage；
- 切换 scope 前先保存当前 record；
- storage 失败直接显示 `ConversationStorageFailure`，不得无提示地丢弃历史。

## 待集成验证

合并 01 和 03 后执行：

1. 用真实 core 类型替换/验证本模块的结构化端口兼容性，并把 mutation action 的 `changeSetId` 对接到 Core ChangeSet；
2. 运行 module manifest、依赖环和 public-import-boundary 校验；
3. 生成 frontend catalog 并确认 feature flag 可禁用；
4. 挂载 React Editor，运行 DOM 可访问性和 resize/maximize 测试；
5. 注入真实附件暂存 adapter，并用 Shell fake/real bus 验证 preview → confirm → execute 与权限拒绝；
6. 验证 saved layout、deep link、Judge Mode 不被 fresh fixture 覆盖。
