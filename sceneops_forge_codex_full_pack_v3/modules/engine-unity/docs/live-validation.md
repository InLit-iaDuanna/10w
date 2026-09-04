# Unity Live 验证记录

验证时间：2026-09-05（Asia/Shanghai）
宿主：macOS arm64
检测到的 Editor：Unity `2022.3.62f3c1`

## 已实际执行

- `Unity -version`：成功返回 `2022.3.62f3c1`。
- reference-assembly C# 编译：成功；4 个 Runtime、10 个 Editor、1 个 smoke fixture 源文件通过 Unity 2022.3 安装所带 Roslyn 与 Unity 引用程序集编译。
- Unity batch Edit Mode 测试：实际启动两次。沙箱内首次因 Licensing Client IPC/数据库权限退出，随后经授权在沙箱外重试。
- 后端完整 unittest：43 个通过；前端 Node 测试：6 个通过。以上完整套件与 C# 编译都发生在最终审批/导入/缓存加固之前、且在当前“仅允许最小烟测”规则下达之前。
- 最终加固后的授权内烟测：`PYTHONPYCACHEPREFIX=/tmp/sceneops-engine-unity-pycache python3 scripts/smoke_adapter.py`，exit code `0`；模块导入成功，可信 ChangeSet 审批快照驱动一次 `unity.component_property.set`，结果为 `mock/succeeded`，稳定目标为 `sobj_home_key`。
- 最终加固后的仅导入检查：全部 Python 测试模块加载成功（未执行测试）；前端 `src/index.ts` 加载成功（未执行 Node 测试）。

## Pending approval

最终安全加固后没有重跑完整 Python unittest、Node 测试、Unity reference-assembly C# 编译、Unity Editor 测试或 Unity build；这些均按当前测试授权规则标记为 `not run / pending approval`。先前成功结果仅是历史证据，不代表最终源码已由对应完整套件复验。

## Blocked

沙箱外重试可连接 Licensing Client，但宿主没有有效 Editor entitlement，Unity 在导入/编译测试前退出：

```text
[Licensing::Module] Error: 'com.unity.editor.headless' was not found.
No valid Unity Editor license found. Please activate your license.
```

精确结果：test process return code `1`，测试 XML 未生成；因此 Edit Mode 测试、Play Mode 测试、Remember Home A/B 和 Warehouse Escape playable build 均为 `blocked`，不是 live、cached 或 mock。

被忽略的本地日志位于 `modules/engine-unity/.artifacts/live-smoke/editmode-unity.log`。取得有效 Unity 2022.3 许可证后，按模块 README 中同一命令重跑；只有脚本输出 `execution_mode: live`、测试 XML 和 `live-smoke-evidence.json` 时才能解除阻塞。
