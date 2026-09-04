# Production Planner Integration

## 依赖边界

`module.yaml` 声明三个必需模块：

- `core-kernel`：命令/事件 envelope、execution mode、ChangeSet、Approval、actor、artifact 与标准错误；
- `module-runtime`：manifest 校验、feature flag 和静态 catalog；
- `design-room`：Feature Spec 公开读取能力。

这些模块在当前起点均不存在。因此本模块只实现自身领域与端口，不新增共享合同，也不修改其他模块目录。

## Feature Spec Provider

真实 design-room 适配器需实现后端公开协议：

```python
class FeatureSpecProvider(Protocol):
    def get_planning_snapshot(
        self,
        feature_ref: FeatureSpecReference,
    ) -> FeaturePlanningSnapshot: ...
```

规则：

- 仅调用 design-room 公开 service/API；
- 稳定引用必须与请求完全一致；
- 保留 source contract version 与 source mode；
- planned/blocked snapshot 不得进入任务生成；
- 不读取 design-room 内部 repository、ORM 或文件路径。

默认 app 使用 `UnavailableExecutionContextProvider` 和其他 unavailable providers，因此缺失组合不会静默退化到 fixture。网络 body 只包含 `FeatureSpecReference`；actor、mode、时间、correlation、command 与 ChangeSet 来自可信 context provider。

## API composition

生产 API composition root 应创建 versioned repository、真实 Feature Spec/run/Approval providers 和 core context provider，再注册：

```python
service = ProductionPlannerService(
    repository,
    feature_spec_provider,
    run_evidence_provider,
    approval_provider,
)
api.include_router(create_router(service, execution_context_provider))
```

Router 只验证与委派。认证、request ID、权限、事务、可信 mode/actor/ChangeSet 和共享错误 envelope 仍由未来 core/API root 负责。当前 service 明确拒绝非 mock context。

Repository 必须实现 create-if-absent 和带 `expected_version` 的 replace。Feature revision 决定 plan ID；同修订 create 不得覆盖既有计划。

## Frontend client

前端通过 `ProductionPlannerApi` 注入端口调用 `createPlan`。生产 adapter 必须委派给唯一 shared generated client，不得在模块里实现 `fetch`、auth、base URL、timeout 或 request ID。

当前 DTO 由本模块 Pydantic/OpenAPI 生成到 `frontend/src/generated/contracts.ts`。等全仓 OpenAPI generator 可用后，应让 shared client generator 消费 `contracts/openapi.json`，模块继续只依赖其公开 client。

因为 React、Zod、EditorDefinition/WorkbenchCommandDefinition 和 TypeScript compiler 尚未提供，当前 `moduleContribution` 有意不注册 editors、commands 或 event handlers。`blockedFrontendContributions` 只记录将来的 ID 和原因，图数据仅作为 headless view model 测试，不宣称是 React UI。

## Shell registration

module-runtime 可用后：

1. 校验 `module.yaml` 及声明依赖；
2. 按共享类型实现真正的 React editors 和 Zod command input schema；
3. 将实现后的 contributions 从 blocked descriptor 移入 `moduleContribution`；
4. 将 `production.plan.create` 放入 command registry；
5. 让 chat action、按钮、菜单和快捷入口都调用该 command ID；
6. 将 `production.plan` 与 `production.task` 作为 lazy editors 注册；
7. 将 `workbench.open_editor` 的 context IDs 交给 shell 解析；
8. 验证 module disabled、permission 和 invalid layout 状态；
9. 补充 Dockview/React component 与 Playwright E2E。

任何 layout 改变都必须保留 `requireConfirmation: true`。

## Approval and ChangeSet

- AI context 必须由 core 标记并带 `change_set_id`；网络调用者不能提交该标记；
- plan/task approval 通过注入的 `ApprovalProvider` 验证 scope 与 scope ID，不能接受任意字符串；
- planner 不创建 Approval、审批人目录或审计历史；
- `production.plan.approved@1` 只提供 planner payload，core 添加 event envelope、actor、correlation、causation、mode 和时间。

## Comments and artifacts

Planner 只保留 `comment_thread_id`、`comment_id`、deliverable/artifact ID 与 evidence 引用。评论正文、版本历史、文件内容、checksum 和完整 provenance 由其拥有模块管理。

## Run evidence

Measured estimate 更新只接收 run/task stable IDs。`RunEvidenceProvider` 返回 verified start/completion time 与 mode，planner 自行计算 duration。Cached timing 必须带 originating live run ID；provider 未集成时返回 Blocked。

## 当前阻断验证

以下测试必须在前置模块合入后进行：

- 官方 manifest/dependency/catalog 生成；
- design-room live Feature Spec ingestion；
- core ChangeSet/Approval 权限与回调；
- trusted command context 与 live/cached mode；
- verified run timing provider；
- shared client 编译和 API integration；
- chat action 到 command registry 的 E2E parity；
- production.plan/task React + Dockview 挂载；
- planner mutation routes/typed commands（当前 edit/assignment/transition/evidence 等仅是 backend domain API）；
- 推荐 downstream editor ID 注册表校验；
- module feature flag disable/enable 集成。
