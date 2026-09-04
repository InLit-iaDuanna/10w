# 独立规划 Web 端口

参见 [工作台完整说明](../../../apps/labs/project-planning/README.md)。
新增前端公开 React loader、设计版本投影与 Pydantic 生成的 PlanningClient；后端新增 `create_planning_lab_app`。原 create/get/graph 与全部领域规则兼容保留。

隔离 mock source 按 project/feature/revision 储存一次投影，拒绝同一版本不同内容。所有变更提交 expected_version，并在本地串行临界区内检查。审批仅在用户点击 lab 确认端点时产生新的 mock Approval 引用，并经 typed provider 验证。不能用于正式生产授权。

重新生成本轮合同（不运行测试）：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=modules/production-planner/backend/src:modules/design-room/backend/src python3 modules/production-planner/backend/scripts/export_lab_contracts.py
```

实际烟测只覆盖 brief 到计划生成。其他新端点测试维护但 not run / pending approval。
