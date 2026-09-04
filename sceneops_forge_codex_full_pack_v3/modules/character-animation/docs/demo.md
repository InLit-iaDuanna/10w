# Remember Home：导入角色最短路径

1. 用 `character.inspect` 加载 `contracts/examples/remember-home-character.json`。
2. 在 Character Editor 查看 `asset_homekeeper_source → char_homekeeper → rig_homekeeper_v1 / skin_homekeeper_v1 / clip_*`，以及 `feature_key_door_branch` / `task_player_traversal` 链接。
3. 在 Rig Inspector、Skin QA 和 Animation Timeline 检查全部证据；注意滑步结论只是一条启发式信号。
4. 使用 `camera_character_regression_v1` 调用 `animation.preview.capture`。确定性演示返回 `mock`，真实 adapter 缺失时返回 `blocked`。
5. 比较同一固定相机的基线和候选预览；相机变化会直接阻断比较。
6. 调用 `character.unity-mapping.propose` 获得 `planned` Mapping 和 dry-run ChangeSet。
7. 未批准执行必须返回 `APPROVAL_REQUIRED`。当前真实 Unity adapter 缺失，因此即使审批完成，默认服务仍返回 `INTEGRATION_OFFLINE`；测试 fixture 的执行明确为 `mock`。

完整机器可读步骤见 `examples/remember-home/simple-character-path.json`。该示例不依赖角色生成或自动绑定。
