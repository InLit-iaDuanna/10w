# Unity U1 资产与编辑往返接口

`UnityAgentSession` 继续使用已登记独立工程、任务授权与认证 mailbox；新增命令为
`unity.content.import/inspect/edit/focus/save/play`，不接受任意代码、外部端口或客户端工程路径。
模块 manifest 声明这些命令；它们由常驻会话执行，不由一次性 batch runner 执行。

- `import_content(*, request_id, asset_id, source_version, expected_source_version, fbx_path, node_ids, instance_ids, authorization)`：
  FBX 必须为任务工作区内真实派生产物。`node_ids` 为 `{frame,leaf,hinge}` 的不同源节点 ID；
  Blender FBX 必须输出 `sceneops_id` 自定义属性和 Empty 铰链节点。初次传两个服务端分配的不同实例 ID；
  后续使用相同实例 ID。初始 `expected_source_version=''`，升级传当前版本。
- `inspect_content()`：读取真实 Editor 对象，包含源版本、模型/外层 Prefab GUID、场景实例与源节点身份、
  位置 `[x,y,z]`、交互距离、钥匙要求、节点尺寸/碰撞体及运行输入结果。
- `edit_content(*, request_id, instance_id, expected, position=None, interaction_distance=None, requires_key=None, authorization)`：
  `expected` 含当前 `position/interaction_distance/requires_key`；只允许修改这三个字段，比较真实旧值后保存并回读。
- `focus_content(*, request_id, instance_id, authorization)`：定位真实 Inspector/Scene View 对象。
- `save_content(*, request_id, reopen=False, authorization)`：明确保存 Inspector 修改；重开需要先保存脏场景。
- `play_content(*, request_id, operation, input=None, authorization)`：`enter/exit/act`；输入为
  `move_x/move_z/interact/duration_frames`，每次最多 120 帧。实际 CharacterController 移动，
  与键盘 WASD/E 同一 Update 路径完成拾取、距离/钥匙判断、叶片转动和网格碰撞；未将运行态写回场景。

模型版本并列存入 `Assets/SceneOpsContent/Models/{asset_id}/{source_version}/model.fbx`，不覆盖旧 FBX 或 `.meta`。
外层 `DoorActor.prefab` 保持 GUID；升级仅更换受管模型子树，保留外层组件、实例位置与行为覆盖。
源节点使用导入器读取真实 FBX 自定义属性，不以名称/序号为身份。场景/Prefab 原文件在开始修改前
保存到 `.sceneops-agent/recovery/{request_id}`，旧版本模型留存。节点缺失在改变场景/Prefab 前拒绝；
版本不符、脏场景与真实字段冲突分别报错。

编译/导入中保持请求排队；一旦场景写入开始留下持久标记，未知结果不自动重放。
相同请求 ID 改变内容会拒绝；成功缓存响应单独附当前 live 回读。
标准保存值以 Editor Scene 为准，未实现 Unity 材质/模型修改回写 Blender。

## 验证边界

Python 定向测试覆盖参数绑定、两个版本保留、同版本冲突、节点与输入约束和权限拒绝。
安装的 Unity 2022.3.62f3c1 reference assembly 编译检查只证明 C# 类型/引用兼容。
真实 Editor、Inspector、产品 Agent 和升级/玩法的验收由本轮证据索引分别记录，不由本接口文档宣称通过。
