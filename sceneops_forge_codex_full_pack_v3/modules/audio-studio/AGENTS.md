# Audio Studio 模块规则

仅在本目录实现音频任务、分析、事件绑定和发布前审查。与 Unity 的交互只能通过 `engine-unity` 已声明的公开适配器协议；禁止导入其内部文件或直接操作 Unity 工程。

不把生成音频当作已发布资产。它必须携带来源信息，经 ChangeSet 批准后才可发布或绑定到生产映射。缺失、离线、禁用的可选媒体能力只能显示降级状态，不能阻断核心构建。

独立测试：`PYTHONPATH=backend/src python3 -m unittest discover -s backend/tests -v`
