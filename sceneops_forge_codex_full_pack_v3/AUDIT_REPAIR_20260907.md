# 2026-09-07 审计问题修复

本次依据 `sceneops_forge_audit_evidence_20260907` 修复当前工作区中的问题，保留任务开始前已有的未提交修改。旧审计的 Python 3.13/DNS/浏览器限制是原环境事实；本次使用本机 Python 3.12、Node 22.22.0、pnpm 11.13.0，不将旧环境失败直接算作产品缺陷。

## 修复内容

| 问题 | 修复 |
| --- | --- |
| 模块 manifest、事件和依赖不一致 | 补齐声明和事件元数据，规范事件入口引用原 schema，保留原权限名称；纠正重复发布命令及静态扫描误报，重新生成目录。 |
| 目录生成后无法导入 | 后端目录静态绑定已声明的公开包与完整 manifest；前端补齐真实贡献导出，保持模块目录可加载。目录元数据不代表所有后端路由已自动挂载。 |
| AI 漏字段不纠错 | 将完整 Pydantic 字段、类型和业务校验放入同一最多两次生成循环；纠错仍失败返回上游 502，网络错误不会被该结构纠错流程重复调用。 |
| 缺失项目／不适用项目错误返回 500 | 公开 `ProjectNotFound` 和 `FolderProjectRequired`，统一映射 404／409 与不可重试状态；真正内部 `KeyError` 保持 500，未知 Agent 任务返回 404。 |
| Node 无法加载 TSX／部分测试未被发现 | 共享测试入口处理 TypeScript、TSX、JSON、目录导入，组件测试使用实际 Vitest；模块入口发现 backend/tests 与 TS/TSX/MJS 测试。补充固定版本测试依赖。 |
| Logic Studio 默认 Header 对象进入业务参数 | 使用 Annotated 保留 HTTP Header 元数据，Python 默认值恢复为真实 `None`。 |
| 过期测试与夹具 | Unity 测试核验当前明确的命令集合；补齐公开导出断言；回滚使用真实旧提交，锁 fixture 使用唯一递增 ID，发布断言使用项目作用域目录；建模和 Git 写入测试通过公开流程准备真实工程基线、注册 worktree。 |

没有关闭安全校验、移除失败断言或将固定模型响应冒充真实 AI。

## 已执行验证

- `module-validate`：32 个模块通过。
- `module-generate --check`：生成内容一致。
- 模块运行时 Python：25 项通过，覆盖原审计 5 个失败项；36 个事件 schema 引用可解析并拒绝空事件。
- 原审计其他 Python 失败：17 个定向用例通过；4 个建模失败用例通过。合计覆盖原 26 个失败方法。
- 原来缺少 hatchling 阻断的 wheel 打包测试：1 项通过。
- 策划完整结构纠错：6 个定向用例及原文件夹到版本／卡片／重开流程通过。
- 项目作用域 HTTP：4 个测试通过，包含原 6 个错误 500 场景、未知任务及内部异常对照；原项目隔离／revision 冲突用例通过。
- 原 23 个失败前端文件：66 个 Node 断言、18 个 Vitest 断言通过。明细日志：`.local/audit-repair-20260907/audit-frontend-recheck.log`。
- Conversation Home 原 `npm test`：47 项通过。
- `module-test logic-studio` 新入口：35 个 Python、6 个前端测试通过。
- 固定锁文件依赖安装成功，`pnpm-lock.yaml` 未改变；原 `pnpm dev` 在隔离数据目录、14300／18300 端口成功启动。
- 最终生成目录下 Vite 生产构建成功，输出到临时目录；仍有静态与动态导入重叠的分块提示，不影响构建完成。日志：`.local/audit-repair-20260907/sceneops-audit-build.log`。
- 真实浏览器加载最终源码前端，实际打开本地项目与生产计划；对话可在生产集成未连接时作为配置入口使用，后端执行授权不变。生产计划只注册一次，原项目选择／脏状态包装保留。

上述包含有意重叠的复验，不能相加为一个全库测试总数。原报告的 895 个 Python 方法和全部前端测试没有在本轮全量重跑。

## 复验入口

测试安装与执行说明见 [docs/testing.md](docs/testing.md)。项目作用域 HTTP 回归：

```sh
node scripts/python.mjs -m unittest discover -s services/api/tests -p test_project_scope.py -v
node scripts/python.mjs scripts/module-validate
node scripts/python.mjs scripts/module-generate --check
```

## Limitations

- 本轮没有重新执行真实供应商 AI → Blender／Unity → 浏览器游戏成品全链路；固定响应下的策划测试只证明业务处理、Git、SQLite 和文件操作行为。
- 前端构建和浏览器启动验证不等于所有编辑器、交互和生成游戏已验收。
- 本次结果针对当前工作区；仓库原有未提交改动仍需与本次修复一起审阅。未创建提交或发布。
