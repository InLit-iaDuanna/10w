# Third-Party Notices

本模块不包含第三方角色、动作、纹理或二进制素材。

直接运行依赖：

| Package | Pinned version | License |
|---|---:|---|
| FastAPI | 0.128.8 | MIT |
| Pydantic | 2.13.2 | MIT |
| PyYAML | 6.0.3 | MIT |
| React / React DOM | 19.1.1 | MIT |
| Zod | 4.1.5 | MIT |

直接开发/测试依赖：

| Package | Pinned version | License |
|---|---:|---|
| TypeScript | 5.9.2 | Apache-2.0 |
| Vitest | 3.2.7 | MIT |
| Testing Library React / jest-dom | 16.3.0 / 6.8.0 | MIT |
| jsdom | 26.1.0 | MIT |
| openapi-typescript | 7.9.1 | MIT |
| @types/node / react / react-dom | 22.18.0 / 19.1.12 / 19.1.9 | MIT |

完整 npm 传递依赖和精确完整性信息由 `frontend/package-lock.json` 固定。发布整库时，应由仓库级许可证生成器合并到根 `THIRD_PARTY_NOTICES.md`；当前规格基线尚无该根文件。
