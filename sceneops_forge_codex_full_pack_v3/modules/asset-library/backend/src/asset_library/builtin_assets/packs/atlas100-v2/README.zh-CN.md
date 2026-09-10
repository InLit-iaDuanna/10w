# Atlas100 v2 · UV、材质、骨骼动画、LOD 与物理交互补全

本包升级的是上一版 Atlas100 的 **675 个模型与 100 个场景**，保留原资产 ID。原始压缩包没有被覆盖。**没有修改你的 GitHub 仓库，也没有读取或补全尚未提供的原项目本地模型。** 原库范围见 `reports/original-project-audit.json`。

## 交付数量

| 内容 | 实际交付 |
|---|---|
| 基础模型与场景 | 675 个模型、100 个场景；场景仍为 24 项引用、38 个实例 |
| 骨骼／动作 | 223 个带骨骼与动作的模型，共 521 段动作；80 件装备包含在内 |
| 静态对象 | 452 个静态建筑／道具，不添加无意义骨骼 |
| UV | 每个模型均含 UV0 材质坐标、UV1 独立三角面图集及 tangent 切线 |
| 纹理 | 10 种风格 × 5 个材质角色，共 50 套共享 PBR 材质、400 张 512×512 PNG |
| LOD | 每模型、每场景均有 LOD0 / LOD1 / LOD2，合计 2,325 个 GLB；各级实际减少三角面 |
| 物理绑定 | 675 份模型绑定、100 份场景绑定；含复合定向包围盒、动态／静态／运动学模式及动作配置 |
| 接入与工具 | 无依赖道具物理核心、Three.js 适配器、离线目录与 WebGL 预览、原库审计及本地 Blender 补全脚本 |

675 个模型合计 LOD0 为 **368,092** 三角面，LOD1 为 **226,652**，LOD2 为 **147,054**。后二者约为 LOD0 的 **61.6% / 40.0%**，不是改名复制。4 件弓类的弦增加了细分以支持变形；LOD0 轮廓及原包边界保持不变。

## 骨骼与动画的范围

装备有装备、卸下、检视、使用等动作；部分枪形工具有装填动作，弓有拉弦权重，折扇有扇骨与弧面权重。机械按配方配置转轮、摆锤、抽屉、门、升降、机械臂、机翼、螺旋桨、钟针等动作。服务机器人有机械分段骨骼与步行动作。

这不是完整人体角色自动蒙皮系统。胸甲、头盔、背包等是装备骨架，实际穿戴要映射游戏已有的 chest / head / back / hand 等挂点；不擅自猜测原角色的骨骼、身材或动作集。452 个静态对象的状态为“不适用骨骼”，不是漏做。

## UV 与 PBR 材质

8 个图像通道是 Base Color、Normal、Roughness、Metallic、AO、Height、Emissive、ORM。ORM 按 R=AO、G=Roughness、B=Metallic 打包；Normal 为 +Y 切线空间。材质槽已经实际连接纹理。

**50 套材质由同风格模型共享，不是 675 套独占手绘贴图。** UV0 是按原始几何做的投影／重复映射；UV1 为每模型独立三角面分岛，不是手工接缝拓扑，也不是整场景的统一烘焙图集。AO 表示程序化材质微表面凹陷，不是高模或整对象烘焙。Height 是额外源图，默认不增加位移细分。

为控制包体，GLB 自包含 **128×128** 内嵌纹理；`textures/` 同时交付完整 **512×512** 源图。使用 `AtlasRuntime` 时会按风格材质角色加载 512px 源图。仅复制单个 GLB，仍可得到内嵌纹理，但不会自动获得外部 512px 源图。

## 本地验看

解压后，在 `atlas100_v2` 目录运行：

```bash
python source_v2/serve.py --open
```

默认只监听 `127.0.0.1:8765`，不联网调用模型服务，不写项目，不运行源文件。浏览器中可以筛选场景／装备／模型，选择动作、切换 LOD，使用单件道具拾取及掉落演示。单景组合 GLB 的动作以实例 ID 区分。关闭详情页即停止对应渲染。

原先的 220 张目录缩略图保留为 **v1 静止几何预览**，不伪装成 v2 材质／动画截图。当前 v2 的实际证据在：

- `proofs/animation-proof.gif`：从导出 GLB 解算蒙皮的动作演示；
- `proofs/lod-comparison.png`：相同镜头下的实际减面模型；
- `proofs/pbr-maps.png`：交付 PNG 图像的拼版。

这些证据为 CPU 网格渲染／原图拼版，不是 Blender、Unity 或 GPU 验收结果。

## 接到 10w／实际游戏

**模型文件不是“导入即带物理游戏逻辑”。** GLB 保存几何、材质、UV、骨骼、动作；碰撞和交互由 `runtime/` 读取 `physics/` 显式实例化。本包未自动修改你的生产工作区、数据库或当前场景。

先做只读部署检查：

```bash
python integration/install.py --repo "/你的路径/10w"
```

再显式部署静态文件：

```bash
python integration/install.py --repo "/你的路径/10w" --apply
```

文件进入 `sceneops_forge_codex_full_pack_v3/apps/web/public/builtin/atlas100-v2/`，目录入口为 `/builtin/atlas100-v2/gallery.html`。安装器遇到已存在且内容不同的文件或符号链接会停止；不覆盖旧内置库、不自动导入、不编辑主界面。

实际游戏的开发服务器可能不同于工作台。运行时使用的资源应部署到**实际游戏自己的** public 目录：

```bash
python integration/install.py --public-dir "/你的游戏/public" --apply
```

包版本 2.0.0 与工作台数据库内部的资产版本号不是同一个字段；导入文件不会自动迁移或替换已有库条目。

把 `runtime/host-example.mjs` 的组合函数纳入现有 Three.js 游戏代码，传入现有 `scene` 和 `camera`。`AtlasRuntime` 通过依赖注入复用宿主的 Three.js 和 GLTFLoader；无需为道具物理额外安装库。现有循环中调用 `runtime.update(deltaSeconds)`，不要再建第二个渲染循环。完整示例见 `runtime/host-example.mjs`。

物理动作接口示例：

```js
runtime.interact(instanceId, 'equip', {
  actorPosition: player.position,
  mount: rightHandSocket,
});
runtime.interact(instanceId, 'use', { actorPosition: player.position });
runtime.interact(instanceId, 'drop', {
  actorPosition: player.position,
  velocity: [0, 1, 2],
});
```

`actorPosition` 是世界坐标，操作距离默认 2.5m；挂点由原游戏提供。场景载入为追加而非替换；加载失败会清理本次新增实例。资产与实例 ID 分开保存。LOD 根据距离切换，三个层级都有独立骨架与动作，避免错误地直接 clone 蒙皮对象。

物理核心有重力、定步长推进、复合 OBB 碰撞、摩擦／恢复、接触／触发事件、休眠／唤醒和拾取后的碰撞关闭。机械动作带动其碰撞盒，运动学机构能唤醒并推动相交的休眠道具。质量、摩擦是游戏默认值，不是实测。

**物理限制：**这是平移刚体／运动学道具求解器，不包含角动力学、连续碰撞检测、布料、布娃娃或完整角色控制器。弯曲模型使用近似盒体；模型须统一缩放。`toggle_light` 切换发光材质，不会创建游戏光源。`use` 播放动作并发出事件，伤害、弹药、种植等原玩法仍由原游戏处理。装备挂点、导航和玩法不凭资产名称自动生成。

## 原项目已有资产：审计与补全

本次读取的 GitHub 默认分支快照中没有找到 `.glb`、`.gltf`、`.fbx` 或 `.blend` 路径，未取得原内置库的模型文件。本次 **原项目模型修改数量为 0**，不把工具交付记成原资产已经处理。

本机可先审计明确选中的资产目录：

```bash
python source_v2/audit_existing.py "/你的路径/10w" --include-local --report "/新路径/original-audit.json"
```

仅检查模型文件，不读 SQLite、凭据 JSON 或脚本，不跟随符号链接。报告会区分已有皮肤／动作、缺失 UV、材质链接、未知 LOD／碰撞状态；缺少骨骼时先判断适用性，不添加假根骨骗过检查。

已有模型的本地补全脚本需要本机 Blender。默认只打印计划；使用新的输出目录，不覆盖原件：

```bash
python source_v2/upgrade_existing.py \
  --input "/原模型/door.glb" \
  --output "/新版本/door-v2" \
  --profile prop \
  --allow-flat-maps
```

加 `--apply` 才执行。脚本尝试保留已有骨骼／动作和材质链接，补缺失 UV，导出新的 `.blend`、三级 GLB、纹理和碰撞提案。`--allow-flat-maps` 明确允许按已有材质常量生成中性图；它不是纹理细节创作或高模烘焙。复杂 Shader、Morph LOD、非米制源和未知骨架会列为待处理，不静默破坏原设置。

批量路径：

```bash
python source_v2/upgrade_existing_batch.py \
  --audit "/新路径/original-audit.json" \
  --output "/新路径/original-upgrades" \
  --allow-flat-maps
```

加 `--apply` 才运行每个任务。可以通过 `--profiles profiles.json` 指定各文件的 `static` / `prop` / `equipment` 分类和 `rig_map`；未分类项按 `review` 处理并留下骨架／交互复核项。骨架映射目前只支持明确命名部件的刚性机构；人体自动蒙皮不在脚本能力内。原模型碰撞输出是提案，需要接到其真实游戏对象和骨架后验收。

**这些 Blender 补全脚本在当前环境未执行。** 它们不等于原库已完成，尤其不能据此宣称旧角色骨架、动画或现有玩法已验证。

## 本次执行的验证

| 检查 | 结果 |
|---|---|
| 876 份版本化 JSON 合约 | 已通过 JSON Schema 验证 |
| 2,325 个 GLB 的访问器、法线、切线、UV、骨骼权重、逆绑定矩阵、动作关键帧、文件 SHA | 已通过 |
| 50 套／400 张源 PNG 与 ORM 通道 | 已通过 |
| 223 个动画模型 × 各动作 × 3 LOD，共 1,563 个组合 | 已实际解算所有关键帧及区间中点，均有真实网格运动 |
| 道具物理核心 | 18 项 Node 测试通过 |
| 浏览器使用的 JS glTF 解析与蒙皮数学 | 4 项 Node 测试通过，含全部 GLB 解析与 Python 参考姿态对照 |
| 交互命令处理器 | 8 项最小场景图桩测试通过；不等于 Three.js 实测 |
| 原库审计和部署计划 | 8 项临时目录测试通过，未对真实原项目执行写入 |
| 当前浏览器三维与控制器验收 | 被浏览器策略 `ERR_BLOCKED_BY_ADMINISTRATOR` 阻断，未通过也未绕过 |
| 实际宿主 Three.js 接入、全项目构建、Blender／Unity | 未执行 |

复查命令（只针对本包，不是原仓库全量测试）：

```bash
python source_v2/validate.py
python source_v2/validate_motion.py
python source_v2/validate_contracts.py
node --test tests/*.test.mjs
python tests/local_tools_test.py
```

生成源依赖 Python、NumPy、Pillow；证据渲染另使用 Numba，JSON Schema 验证使用 jsonschema。依赖版本见 requirements-build.txt。版本记录见 `provenance.json`。运行时 JavaScript 本身不调用 Python、不读取工程文件系统、不联网购买／生成模型。

## 文件结构

`assets/` 为模型 LOD0，`scenes/` 为组合场景 LOD0 与实例 JSON，`lods/` 为 LOD1/2；`physics/` 为绑定，`textures/` 为源图，`runtime/` 为解析／预览／Three.js 适配；`source_v2/` 为补全生成与验证源，`source_v1/` 保留上一版几何生成器；`tests/`、`reports/`、`proofs/` 为验收范围与证据。675 个模型的具体补全内容见 `UPGRADE_MANIFEST.zh-CN.md`，100 个场景对应资产见 `CATALOG.zh-CN.md`。
