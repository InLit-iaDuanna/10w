# 角色与动画质量检查

## 确定性检查

| Code | 判定 |
|---|---|
| `character.skeleton_hierarchy` | 单一根骨；Bone ID/名称唯一；父级存在；无循环 |
| `character.missing_bones` | CharacterSpec 的预期骨骼名称全部存在 |
| `character.scale_axis` | handedness、up/forward axis 与 meters-per-unit 精确匹配 |
| `character.skin_weights` | 每个样本有权重；0–1；和误差不超过 0.01；影响数未超上限；Bone ID 存在 |
| `animation.clip_length` | duration 和 sample rate 大于零 |
| `animation.event_markers` | Marker ID 唯一；按时间排序；落在 `[0,duration]` |
| `animation.root_motion` | 至少两个有序范围内样本；`in_place` 片段首尾根位移不超过 0.02 米 |
| `animation.loop_seam` | Loop 首尾根位移不超过 0.02 米且旋转向量差不超过 3 度 |
| `animation.animator_graph` | 状态 Clip 与 transition target 均存在；State ID 唯一 |
| `animation.retarget_profile` | Profile Rig ID 匹配；源/目标 Bone 存在；目标 Bone 不重复 |

## 启发式检查

`animation.foot_sliding` 比较同一脚掌被标记为 planted 时相对首个接触样本的最大位移。超过 0.025 米只产生 warning；样本少于两个时为 `blocked`，时间乱序或超出片段范围时为 `failed`，不会把缺失证据当作通过。

该值依赖接触标记、采样密度和角色比例，不能判断视觉可信度，也不能替代动画师逐帧检查。`QualityReport.human_quality_approval` 固定为 `false`；人工审批通过独立的版本 review 流程记录。

固定相机预览比较使用 adapter 提供的 `[0,1]` frame difference score。只有 camera 对象完全一致且 score 存在时才可比较；阈值 0.1 以内为通过，高于阈值为 warning。它同样不是质量审批。
