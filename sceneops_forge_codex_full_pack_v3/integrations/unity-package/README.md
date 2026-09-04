# SceneOps Forge Unity Package

这是 `engine-unity` 的 Unity 2022.3 LTS 侧实现，UPM 包名为 `com.sceneops.forge.unity`。

Runtime 提供：

- `SceneOpsIdentity`：源资产、版本、对象、Prefab 和场景实例身份；
- `SceneOpsTelemetryBridge`：带完整身份链和 execution mode 的运行时遥测；
- 可验证的 Remember Home / Warehouse Escape 示例玩法组件。

Editor 提供固定 `SceneOpsBatchCommandRouter`、路径/版本/ChangeSet 校验、导入 hook、Prefab/identity/组件操作、NavMesh、console、profiler 和 build。命令名和参数不能由调用者扩展成 C# 方法、脚本或 shell；模型导入仅允许固定非可执行格式，并在复制前核对 SceneOps manifest 与源身份。

包内 Edit Mode 测试覆盖身份 rename/copy/telemetry 与命令、路径、属性和审批安全边界。真实运行方法与当前宿主阻塞状态见 `modules/engine-unity/README.md`。

不要提交目标项目的 `Library`、`Temp`、`Logs`、`obj`、`UserSettings` 或 build output。
