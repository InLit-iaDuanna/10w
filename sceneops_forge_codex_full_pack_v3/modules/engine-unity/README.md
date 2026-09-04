# Unity Engine Integration

`engine-unity` 把已发布资产、稳定身份和构建意图安全地送入 Unity 2022.3 LTS。模块提供类型化适配器、Unity Package、身份映射、Prefab/组件操作、测试与构建任务、性能快照、构建清单，以及 Remember Home / Warehouse Escape 的确定性验证工程。

## 用户与边界

面向 Unity 工程师、技术美术、关卡设计、QA 和构建负责人。模块拥有 Unity 命令合同、执行策略、构建证据与 Unity 侧实现；不拥有 Blender 导出内部逻辑、ForgeShell、玩法图、AI playtest 或发布流程。

应用运行时不提供任意 C#、shell、反射方法名或任意文件访问。所有外部操作通过 16 个固定命令之一进入；Python 适配器与 Unity Package 都维护同一白名单。

## 公共入口

- 后端：`engine_unity`，公开 `UnityAdapter`、`UnityEngineService`、命令/结果模型和身份读模型。
- 前端：`frontend/src/index.ts`，注册 5 个延迟加载编辑器、16 个命令与工具库条目。
- Unity：UPM 包 `com.sceneops.forge.unity`，当前固定版本为 Unity `2022.3.62f3c1`。

`create_router(service, context_provider)` 暴露 `/api/modules/engine-unity/capabilities`、`/commands/preview` 和 `/commands/execute`。`context_provider` 必须由 composition root 从服务端配置、认证上下文和审批存储构造，不能接收客户端提供的权限、允许根目录或审批记录。执行上下文中的 `approved_change_sets` 保存完整可信快照，而非仅保存可复用 ID。

### 编辑器

| ID | 用途 |
|---|---|
| `unity.inspector` | 按 `sceneops_id` / 场景实例 ID 检查 GameObject |
| `unity.prefab.inspector` | 检查 Prefab 与源资产版本映射 |
| `unity.build.matrix` | 展示 profile、测试要求、目标和构建状态 |
| `unity.build.console` | 展示结构化日志、失败原因和重试入口 |
| `unity.profiler` | 展示显式模式标记的性能快照 |

前端状态覆盖 loading、empty、ready、offline、permission denied 和 failed；Live、Cached、Mock、Planned、Blocked 使用不同文本标签，不依赖颜色。

### 命令

| 类别 | 命令 |
|---|---|
| 连接/读取 | `unity.health`, `unity.project.scan`, `unity.game_object.inspect`, `unity.console.read` |
| 资产/身份 | `unity.asset.import`, `unity.identity.map`, `unity.prefab.upsert` |
| 安全变更 | `unity.component_property.set`, `unity.collider.upsert`, `unity.navmesh.run` |
| Editor 操作 | `unity.play.enter`, `unity.play.exit`, `unity.capture`, `unity.profiler.snapshot` |
| 验证/交付 | `unity.tests.run`, `unity.build.run` |

命令字段、权限、审批和路径规则见 [命令合同](docs/command-contract.md)。

### 事件

模块声明 `unity.project.scanned@1`、`unity.asset.imported@1`、`unity.identity.mapped@1`、`unity.prefab.updated@1`、`unity.test_run.completed@1`、`unity.profile.captured@1`、`unity.build.completed@1` 和 `unity.build.failed@1`。当前起点缺少 `core-events`，因此仅声明事件贡献，发布/消费接线为 planned；未伪造事件总线实现。

## 数据所有权

模块拥有：

- Unity 命令请求、结果和结构化错误；
- Unity 资产 GUID、Prefab ID、场景实例 ID 的映射读模型；
- Unity 测试与构建任务状态；
- 版本化导入清单和不可变构建清单；
- Unity 日志、测试 XML、性能快照和构建证据的引用。

资产 ID、资产版本 ID、`sceneops_id`、Prefab ID 和场景实例 ID 始终分离。名称和路径只用于显示或定位。

## 执行模式

| 模式 | 当前行为 |
|---|---|
| Live | 使用固定 Unity CLI 参数和固定 `SceneOpsBatchCommandRouter`；真实结果必须来自当次 Editor 进程 |
| Cached | 仅回放同一适配器进程中已成功完成的 live 结果，并保留原请求 ID |
| Mock | 读取 `fixtures/mock/command-results.json`；所有结果明确标记 `mock` |
| Planned | 完成路径、schema、权限、版本与 ChangeSet 校验，只返回 dry-run 预览 |
| Blocked | 未配置 Editor、缺少许可证或需交互式 Editor 时返回结构化阻塞原因 |

当前机器的真实 Unity Editor 测试/构建状态见 [Live 验证记录](docs/live-validation.md)。

## 安装与配置

在目标 Unity 2022.3 项目的 `Packages/manifest.json` 中引用包目录：

```json
{
  "dependencies": {
    "com.sceneops.forge.unity": "file:/absolute/path/to/integrations/unity-package"
  }
}
```

适配器上下文必须配置规范化项目根目录、调用者权限、当前 base version 和服务端审批快照。项目根必须包含 `Assets/`、`ProjectSettings/` 与 `ProjectSettings/ProjectVersion.txt`。导入源、manifest、场景、捕获、测试结果和构建输出都必须位于该根目录内。模型导入只接受 `.3ds/.dae/.dxf/.fbx/.obj`；GLB 需先由上游发布等价 FBX，直到另一个受支持的类型化 importer 被纳入合同。

## 测试

不启动 Unity 的最小适配器烟测：

```text
PYTHONPYCACHEPREFIX=/tmp/sceneops-engine-unity-pycache python3 scripts/smoke_adapter.py
```

完整验证命令：

```text
PYTHONPATH=backend/src python3 -m unittest discover -s backend/src/engine_unity/tests -v
node --test frontend/src/tests/*.test.mjs
python3 scripts/compile_unity_package.py --unity-app /Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app
```

有有效 Unity 许可证时运行真实 Editor 测试和三个 standalone build：

```text
python3 scripts/run_unity_smoke.py \
  --unity /Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app/Contents/MacOS/Unity
```

脚本在临时工程中嵌入 canonical Unity Package；`Library`、`Temp`、`Logs`、`obj` 和构建输出不会提交到 Git。成功时生成 `live-smoke-evidence.json` 和每个构建的 SHA-256 provenance 清单。

## 示例

- Remember Home A：低可见度钥匙、拾取、库存、家门和出口链路。
- Remember Home B：同一身份链上的批准可见度改动。
- Warehouse Escape：使用同一包与构建流程的开关、仓门、出口链路。

Mock 构建清单位于 `contracts/examples/unity-build-manifest.mock.json`，并明确指向非可玩 mock artifact。真实 smoke 绝不复用该文件冒充 live。

## Limitations

- 当前仓库起点尚无 `core-kernel`、`module-runtime`、artifact store、API composition root 或生成 catalog；manifest 已声明依赖，跨模块接线为 planned。
- 当前宿主 Unity 可执行文件存在，但无有效 Editor entitlement；真实 Edit Mode/Play Mode 测试和 playable build 为 blocked。
- CLI batch transport 无法进入交互式 Play Mode 或完成屏幕捕获；Unity Package 内的固定处理器已实现，连接式 Editor transport 需后续集成中心提供。
- 未运行的 Unity 测试或构建不会被标记为 live；C# reference-assembly 编译通过不等同于 Editor 测试通过。

## 2026-09-05 独立 Web 组合更新

`apps/labs/unity-build` 已提供中文 Unity 能力、连接阻塞原因、稳定对象 ID、静态命令记录与 ChangeSet 编辑/预览入口。
公共后端新增 `UnityWorkbenchService`、`UnityWorkbenchSnapshot` 和 `UnityProposalPreview`，供 build-release 组合。
此服务只配置 `unity_editor=None`，通过原 `UnityEngineService.preview` 做本地 dry-run 校验；不执行 fixture 命令，也不启动 Unity。
完整启动、接口和验证范围见 [工作台说明](../../apps/labs/unity-build/README.md)。Unity Package 与旧安全策略保持原样；所有外部操作本轮 **not run / pending approval**。
