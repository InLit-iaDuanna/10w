# Third-Party Notices

本模块不包含第三方角色、动作、纹理或二进制素材。

直接运行依赖：

| Package | Pinned version | License |
|---|---:|---|
| FastAPI | 0.128.8 | MIT |
| Pydantic | 2.13.2 | MIT |
| PyYAML | 6.0.3 | MIT |
| React / React DOM | 19.2.8 | MIT |
| TanStack React Query | 5.90.21 | MIT |
| Zod | 4.1.5 | MIT |

直接开发/测试依赖：

| Package | Pinned version | License |
|---|---:|---|
| TypeScript | 6.0.3 | Apache-2.0 |
| Vitest | 3.2.7 | MIT |
| Testing Library React / jest-dom | 16.3.0 / 6.8.0 | MIT |
| jsdom | 26.1.0 | MIT |
| openapi-typescript | 7.9.1 | MIT |
| @types/node / react / react-dom | 22.18.0 / 19.1.12 / 19.1.9 | MIT |

`frontend/package-lock.json` 保留原 npm 安装记录，未同步本轮 pnpm workspace 版本；本轮安装没有覆盖锁文件，统一锁文件由 Shell 整合。TanStack Query 用于本地服务请求状态。独立 lab 另使用 openapi-fetch 0.15.0（MIT）、Vite 8.0.0（MIT）、Uvicorn 0.39.0（BSD-3-Clause），详见 lab README。发布整库时，应由仓库级许可证生成器合并到根 notices。
