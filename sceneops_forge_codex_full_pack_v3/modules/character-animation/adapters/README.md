# Character Tool Adapter Extension

Python 公共协议由后端包的 `CharacterToolAdapter` 导出。实际 Blender、重定向或 Unity 实现应由对应 integration 模块拥有，并通过依赖注入提供给 `CharacterAnimationService`；不要把 vendor 代码复制到本目录。

本模块内只有两个参考实现：默认 offline adapter 和 deterministic mock fixture adapter。参见 `docs/integration.md`。
