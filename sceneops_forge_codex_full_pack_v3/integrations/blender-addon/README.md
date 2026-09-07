# SceneOps Blender typed adapter and add-on

This package is the only Blender process boundary for the 07 asset pipeline. It
accepts typed, allowlisted commands, validates every project path, launches only
the bundled bridge, maps failures to structured errors, and labels execution as
`live`, `cached`, `mock`, `planned`, or `blocked`.

## Supported operations

Health/capabilities are separate APIs. Commands cover scene scan, stable-ID
assignment, object inspection, transform/normals, bounded material and light
parameters, context capture, allowlisted AOV render, geometry checks,
conservative LOD/collider generation, snapshot/rollback, and GLB/FBX export.
There is deliberately no arbitrary Python or shell command.

`generate_lod` uses Blender's decimate modifier with declared ratios.
`generate_collider` supports only bounding-box and convex-hull strategies. These
are production proposals requiring inspection; the integration makes no claim of
automatic production-quality retopology.

## Live setup

Install or point the service at a supported Blender executable, then construct
`LiveBlenderAdapter(project_root, executable)`. Executable discovery is off by
default, the configured binary must be named Blender and pass `--version`, and
the Python bridge cannot be overridden. Commands run with `--background`,
`--factory-startup`, and `--disable-autoexec` through the fixed
`scripts/typed_bridge.py`; the add-on also disables Freestyle and compositor
nodes after loading an imported scene. All requested source/output paths remain
below the configured root. The bundled direct subprocess transport can run only
source-less live checks such as the smoke scan; it reports
`BLENDER_SANDBOX_REQUIRED` before opening any project `.blend`. Project-file
commands require an injected transport that truthfully advertises filesystem
isolation. Persistent scene mutations also require an existing, server-owned
per-run `operation_state_root` outside project content for locks and retry
journals.

When Blender is unavailable, `health_check()` returns `blocked`. Callers may
explicitly select `DeterministicMockBlenderAdapter`. `CachedBlenderAdapter`
becomes healthy only when trusted storage supplies a successful live-run record
for each workflow-slot/operation key. Run-directory paths are normalized only at
their structural segments; the remaining command, current source checksum, and
verified materialization blobs must match. Each side effect is materialized into
the new run and rechecked for byte size/checksum. The live adapter never auto-
falls back.

## Tests

```text
PYTHONPATH=integrations/blender-addon/src python3 -m unittest discover -s integrations/blender-addon/tests -v
```

The smoke test is not skipped: it asserts `live` when Blender is found and
otherwise asserts a structured `blocked` result.

## 任务级常驻 Blender 会话

公开入口 `BlenderAgentSession(workspace_root, state_root, executable=None)` 接收服务端
分配的工程目录与独立状态目录。实际内容位于 `workspace_root/blender`；新会话拒绝使用非空
内容目录。默认发现 `/Applications/Blender.app/Contents/MacOS/Blender`，沿用已安装版本。
`bind_authorization(grant)` 后调用同步 `start()` 打开可见空场景，返回真实版本、会话 ID、
进程、对象、可用能力及隔离探针证据。`inspect()` 回读尺寸、身份和文件；`stop()` 只关闭
已认证的自有会话。应用重启会重新连接既有会话，编辑器中断后从自有 `.blend` 和 SQLite
请求记录恢复。

授权字段为 `task_id / grant_id / project_id / workspace_root / allowed_capabilities /
expires_at`（UTC ISO 时间）。修改调用还必须带同一授权及 `action_id / capability_id /
change_set_id / approval_id`。能力仅有 `blender.scene.inspect`、`blender.asset.create`、
`blender.asset.export`。模型不提供这些授权字段；执行服务从已确认记录生成它们。

- `create_asset(request_id=..., asset_id=..., sceneops_id=..., dimensions_m=[x,y,z],
  authorization=..., name=None, dry_run=False)` 创建尺寸为 0.001–100 米的单个立方体并保存。
- `export_asset(request_id=..., asset_id=..., authorization=..., dry_run=False)` 复用已有
  类型化 FBX 导出器，返回 `fbx_path` 与 `manifest_path`，附 Unity 身份映射 sidecar。
- 相同请求与输入只执行一次；请求 ID 改绑其他输入被拒绝。`dry_run=True` 只返回计划写入
  路径，不启动 Blender。所有编辑操作都在 Blender 主线程计时器执行。

会话使用仅绑定 loopback 的认证传输；密钥保存在权限 0600 的状态文件，不进入响应或日志。
macOS `sandbox-exec` 默认拒绝访问，只允许 Blender 运行时与固定桥接源码读取、专属内容与
状态目录写入、loopback 网络。它不开放用户主目录，也不开放任意代码命令。每次启动必须
实际尝试并拒绝目录外 sentinel 写入后才能报告连接成功。符号链接输出越界也被拒绝。

定向验证：

```sh
PYTHONPATH=integrations/blender-addon/src python3 -m unittest discover -s integrations/blender-addon/tests -p test_agent_session.py -v
# 显式真实验收：仅创建临时独立工程，打开 Blender，最后关闭自有进程。
PYTHONPATH=integrations/blender-addon/src python3 integrations/blender-addon/scripts/smoke_agent_session.py
```

真实验收脚本涵盖空场景、尺寸与 FBX 身份、目录外拒写、认证失败、幂等、重连、符号链接
越界、编辑器进程中断恢复及日志无密钥，保留独立目录下 `evidence.json`。当前操作系统
实现仅支持 macOS；缺少系统沙箱或编辑器时报告真实失败，没有 Mock 替换。

## 原生资产往返

`BlenderAgentSession(..., headless=True)` 使用相同认证与 macOS 沙箱在后台运行；默认仍打开
可见编辑器。后台固定桥接在 Blender 主线程处理队列，界面模式使用主线程 timer。

- `bootstrap_door(request_id, asset_id, candidate_id, node_ids, recipe, authorization)` 仅首次
  从配方创建源。`node_ids` 包含不同的 `frame / leaf / hinge`；recipe 是
  `width_m / height_m / thickness_m / material`，可带 `frame_width_m`；material 是
  `color_hex / roughness / metalness`。使用 `blender.asset.begin` 授权。
- `register_source(candidate_id, source_path)` 是服务端入口，将已登记且位于工程内的
  `.blend` 复制到新的候选文件；不暴露为模型工具，不覆盖已有候选。
- `open_source(..., candidate_id, authorization)` 打开候选原生源，使用 begin 授权。
- `edit_nodes(..., edits, authorization)` 接收 `node_id` 与可选 `dimensions_m`、
  `base_color`；尺寸是 Blender XYZ（Z 向上），颜色是 0–1 RGBA。允许网格节点及其网格分组。门框由独立左右柱与横梁组成，运行碰撞保留门洞。
  `save_source(...)` 保存当前人工编辑；二者使用 `blender.asset.edit` 授权。
- `export_source(..., formats=['glb'], authorization)` 显式保存当前编辑并导出 GLB，
  可选 FBX；使用 `blender.asset.publish` 授权。导出成功后候选不可再由 Agent 修改，
  下一轮先复制新候选。返回真实 `blend_path / glb_path`。

GLB 保留 `sceneops_id / sceneops_role / asset_id` extras，门扇在铰链节点下，门框独立。
GLB 为米、Y 向上；inspect 顶层 `dimensions_m` 是 Y-up 世界包围盒尺寸，objects 中尺寸
仍标注 `blender_z_up`。`current_candidate_id` 用于服务端核对当前源。恢复会话打开最后
活动的源文件，不重新运行配方。

`request_status(request_id)` 回读已知完成结果；没有完成日志的写入返回 `result_unknown`，
同请求不会盲目重做。`cancel_request(request_id)` 仅取消尚未执行的队列请求；返回 running
表示已经进入 Blender 主线程，不能声称取消成功。已取消队列状态目前随进程存在。

定向协议验证与显式真实工具验证：

```sh
PYTHONPATH=integrations/blender-addon/src python3 -m unittest discover -s integrations/blender-addon/tests -p test_source_protocol.py -v
PYTHONPATH=integrations/blender-addon/src python3 integrations/blender-addon/scripts/smoke_source_roundtrip.py --headless
```

真实脚本使用临时独立工程、保留 evidence.json 与两轮源/GLB，只关闭自有进程；涵盖原生
保存重开、第二轮保留首轮自由修改、语义节点、GLB 文件结构与重复导出请求。

显式保存/导出会为人工新建的未标记节点分配 UUID 稳定身份并归入当前候选资产，已有节点
身份保持。若场景含其他资产身份或重复节点身份，则拒绝保存导出，不静默丢弃几何。
`fixture_add_manual_handle.py` 仅为开发验收夹具，由独立沙箱 Blender 模拟新增未标记把手；
它不在运行时工具注册表，也不是人工 UI 操作证据。真实 smoke 验证该把手在第二轮源重开
与 GLB 导出中保留相同新身份。

`grant_content=True` 将新会话内容限制在 `workspace/blender/<grant_id>`；授权 ID 经原协议
验证，新授权使用独立状态目录和新会话，再从已登记源复制候选。旧会话不能更换授权。
`smoke_source_roundtrip.py --headless --grant-content` 实际验证新授权独立目录重开已有源。
