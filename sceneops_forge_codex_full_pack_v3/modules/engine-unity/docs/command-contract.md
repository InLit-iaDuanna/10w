# Unity 命令合同

## 公共 envelope

每个请求包含 `request_id`、`idempotency_key`、`command`、`project_id`、`project_root`、`base_version`、`mode`、类型化 `payload`、可选 `change_set`、timeout、最大尝试次数和可选 cache key。

所有命令先验证：

1. 项目根恰好属于执行上下文配置的根集合；
2. 根目录是 Unity 项目，且所有路径解析后仍在根内；
3. 项目版本为 Unity 2022.3 LTS；
4. payload 符合命令专属 Pydantic 模型；
5. 调用者具备命令所需权限；
6. base version 与当前项目一致；
7. 组件、属性、碰撞体、build target 和命令均在固定白名单内；
8. 变更命令携带 ChangeSet；其 command、规范化 payload 与完整稳定目标集合逐项匹配；
9. 需要审批的 ChangeSet 与服务端执行上下文中的不可变审批快照完全匹配，客户端自报 `approved` 无效。

## 权限与审批

| 命令组 | 权限 | ChangeSet | 执行审批 |
|---|---|---:|---:|
| health / scan / inspect / console | `unity:read` | 否 | 否 |
| import / identity / prefab / property / collider / NavMesh | `unity:write` | 是 | 是 |
| enter / exit / capture | `unity:execute` | 是 | 否 |
| tests / profiler | `unity:execute` | 否 | 否 |
| build | `unity:build` | 是 | 是 |

Dry-run 可使用 pending ChangeSet；实际执行返回 `waiting_approval`，不会调用 Unity。

## 组件属性白名单

允许设置 Transform 的本地 position/rotation/scale，Box/Sphere/Capsule/Mesh Collider 的有限几何与触发字段，Rigidbody 的有限动力学字段，以及 Light 的 intensity/range/color。`m_Script`、MonoBehaviour 任意字段和 SceneOpsIdentity 字段都不能通过通用属性命令修改；身份只能通过 `unity.identity.map`。

Vector3 值使用 `{ "x": 0, "y": 1, "z": 0 }`，Quaternion 使用 `{ "x": 0, "y": 0, "z": 0, "w": 1 }`，Color 使用 `{ "r": 1, "g": 1, "b": 1, "a": 1 }`。单位为米，坐标空间为 Unity 左手坐标：Y-up、Z-forward。

## 重试、取消与幂等

- health、scan、inspect、capture、console、tests 和 profiler 可按策略自动重试；asset/scene/build 变更不自动重试。失败或取消的 build 只能由任务状态机在用户检查日志与输出后显式重新排队。
- `idempotency_key` 的成功结果只执行一次；重复调用返回 `cached` 并指向原请求。作用域同时包含 actor、project ID、规范化 project root、command 和 base version。
- 只有成功 live 结果可写入 replay cache。
- 显式 cached 请求必须复用相同 actor/root/command/base/key，且规范化 payload 与 ChangeSet 必须和原 live 请求一致。
- 取消会终止固定 Unity 子进程并保留日志尾部；timeout 采用同一补偿路径。
- build 成功后由幂等结果拦截重复副作用；同一 key 若对应不同 payload 或 ChangeSet 会返回 `UNITY_IDEMPOTENCY_CONFLICT`。

## 错误

结构化错误至少包括 code、message、retryable 和 details。已覆盖：路径越界、权限不足、ChangeSet/审批缺失或不匹配、base/version 不兼容、integration offline、timeout、cancel、compile/test/build failure、缺失 material/script/reference、identity conflict 和 cache miss。
