# 身份、Prefab、遥测与构建

## 身份链

```text
source asset ID
  -> source asset version ID
  -> source object ID / sceneops_id
  -> Unity asset GUID
  -> Prefab ID
  -> scene-instance ID
  -> runtime telemetry event
```

`SceneOpsIdentity` 序列化全部关系。重命名只改变 GameObject 展示名；复制保留资产、版本、对象和 Prefab 关系，但必须由 `unity.identity.map` 指定新场景实例 ID，并记录 `copiedFromSceneInstanceId`。创建实例或复制时还需使用 inspect 返回的 Unity `GlobalObjectId` 精确定位对象；它是定位符，不替代 SceneOps 主身份。通用 property 命令不能写这些字段。

导入合同 `unity-import-manifest.schema.json` 明确声明米制单位、handedness、up axis 与 forward axis。导入后，Prefab 映射通过 GUID 和稳定 ID 完成，不依赖层级路径或名称。

## Prefab 与资产设置

`unity.asset.import` 只接受匹配扩展名的 `.3ds`、`.dae`、`.dxf`、`.fbx` 和 `.obj`，manifest 必须位于 `Assets/` 且以 `.sceneops-unity.json` 结尾。`.cs`、`.dll`、`.asmdef`、`.rsp` 与其他可触发代码加载的格式不能进入导入路径。GLB 不会被假报为已导入；在安装并纳入类型化 glTF importer 合同前，上游需发布 FBX。manifest 的 project/source asset/version/source file 会在复制前与请求交叉验证。

允许的模型支持缩放、material import/external/none、自动 collider 和 LOD 阈值验证。`unity.prefab.upsert` 只添加固定组件集合；提供 LOD 阈值时，要求模型 renderer 使用 `LOD0`、`LOD1` 等前缀，缺失层级会返回 `UNITY_MISSING_REFERENCE`，不会静默跳过。

Prefab 保存前检查 missing script 和 missing material。检查器命令返回组件类型与缺失计数。

## 遥测

`SceneOpsTelemetryBridge` 的事件包含 event ID、UTC 时间、project/build、execution mode、`sceneops_id`、源资产/版本、Prefab 和 scene-instance ID。缓冲区有显式容量，不写入秘密或任意对象序列化数据。

## 构建清单

每个成功 live build 以 exclusive create 生成 `Artifacts/BuildManifests/<build_id>.json`；已有 build ID 会在调用 Unity 前返回 identity conflict，不覆盖清单。清单记录：

- build/project/profile 与 execution mode；
- Unity/Package/source commit；
- 场景、源资产版本和 build settings；
- 测试运行引用及其真实模式/状态；
- 构建 artifact 的路径、字节数和 SHA-256；
- UTC 生成时间。

Standalone `.app` 是目录，digest 按排序后的相对路径、文件大小和每文件 digest 组成，内容或重命名都会改变最终值。未提供真实测试证据时，required test run 在 manifest 中标记为 `blocked`，不会假报 passed。
