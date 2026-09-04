# Audio Studio

Audio Studio 为游戏音频提供可追溯的任务规格、WAV 基础分析、事件绑定，以及经审查后发送给 Unity 的映射提案。首个纵切覆盖“拾取钥匙”和“门已解锁”两个事件；`warehouse-escape` 模板证明它不依赖特定游戏名称。

## 能力与边界

- 创建 `AudioSpec`，引用导入素材或 AI 生成提案；生成素材绝不是已发布资产。
- 解析 PCM WAV 的声道、采样率、位深、时长、峰值、近似 RMS dBFS 及固定 16 桶波形包络。近似 dBFS 不是 LUFS 测量。
- 校验基础格式、峰值和响度范围，绑定游戏事件。
- 仅通过 `EngineUnityAudioAdapter` 协议提出 `AudioSource` / `AudioMixer` 映射；适配器是否真正执行由调用方及其执行模式决定。
- 只有具备完整来源记录、已批准 ChangeSet、且资产已发布时，才可发布映射；dry-run 只产生提案。

## 公共入口

- 前端：`frontend/src/index.ts`，导出 `moduleContribution`、编辑器和命令定义。
- 后端：`audio_studio`，仅从 `backend/src/audio_studio/__init__.py` 导入 `AudioStudioService`、领域类型和 `EngineUnityAudioAdapter`。

## 状态与真实性

执行模式明确为 `live`、`cached`、`mock`、`planned` 或 `blocked`。模块本身不连接 Unity 或媒体生成器；测试中的 WAV 和 Unity 适配器都是明确标注的 `mock`。`disabled` 和 `offline` 返回可展示的降级状态；可选媒体失败不阻断核心构建。

## 快速示例

```python
service = AudioStudioService(module_enabled=True, unity_online=True)
analysis = service.inspect_wav(mock_key_pickup_wav(), "key-pickup.wav")
binding = service.bind_event("gameplay.key.picked_up", "aud_key_pickup_v1")
```

发布映射前，调用方必须先创建并批准一个包含基线、目标、前后值、风险、验证和回滚计划的 `ChangeSet`，并为资产提供完整 `Provenance`。详情见 `docs/integration.md`。

## 独立测试

```text
PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v
cd frontend && npm test
```

## 限制

当前仅解析未压缩 PCM WAV，响度为确定性的近似 RMS dBFS，而非广播级 LUFS。没有根运行时或真实 Unity 连接，因此没有声卡播放、媒体生成、文件上传或真实 Unity 写入。
