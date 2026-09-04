# SceneOps Forge 独立工作台

当前分支提供可独立启动的 **Shell 对话工作台**。首次安装与操作见 [apps/labs/shell/README.md](apps/labs/shell/README.md)。应用根执行 `pnpm lab shell`，默认 Web 4310 / API 8310；默认 MOCK 对话，可在输入框下方选择 CodeBuddy CLI 模型。

其他工作台接入规则见 [apps/labs/README.md](apps/labs/README.md)。业务继续归属 modules，入口只组合公开接口；统一 core/runtime、根工具链与锁文件由 Shell 维护。
