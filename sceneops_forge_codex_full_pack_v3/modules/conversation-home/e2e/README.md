# 手动即时反馈验证（显式 Mock）

仅在主动验证聊天 UI 时启动，不属于 `pnpm dev`，不访问真实模型、项目或数据库。端口需空闲。

在应用根分别启动：

```sh
.venv/bin/python modules/conversation-home/e2e/controlled_chat_api.py
SCENEOPS_WEB_PORT=4303 SCENEOPS_API_PORT=8303 pnpm exec vite --config apps/web/vite.config.ts
```

打开 4303；模型明确标记 Mock UI。发送任意测试文字，确认立即出现用户消息和流式等待状态，输入框可以继续写下一条。

```sh
curl -X POST http://127.0.0.1:8303/__test__/release
curl http://127.0.0.1:8303/__test__/received
```

release 让 SSE 返回显式 `error` 事件；received 只显示测试进程内存中的正文，用于核对重试未替换成新草稿。等待最多 60 秒后也会失败。不要输入真实敏感内容。验证后停止两个进程，关闭测试标签；不改变真实应用的 provider 设置。
