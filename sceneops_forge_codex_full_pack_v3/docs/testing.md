# 独立测试入口

先安装应用依赖，再安装显式测试依赖：

```sh
uv pip install --python .venv/bin/python -r services/api/requirements.txt
uv pip install --python .venv/bin/python -r requirements-test.txt
pnpm install --frozen-lockfile
```

针对受影响的文件或模块执行；`all` 是完整测试，不属于默认烟测：

```sh
pnpm test:frontend modules/conversation-home/frontend/src/tests/local-transport.test.ts
pnpm test:module conversation-home
npm --prefix modules/conversation-home/frontend test
```

`module-test` 从 manifest 发现模块，在独立进程运行 `tests`、`backend/tests` 和后端包内测试，避免不同模块的同名 `support`/`tests` 互相污染。Python 使用 pytest，因此同时执行 unittest 类和 pytest 函数；模块内测试目录加入该进程的导入路径。测试依赖含 wheel 资源验证需要的 hatchling。

前端入口接受显式文件或目录，发现 `.test.ts`、`.test.tsx` 和 `.test.mjs`。Node 测试通过现有 TypeScript 编译器转换 TS/TSX，并按源码构建约定解析相对扩展名、目录入口和 JSON；CSS 只验证文件可读取，样式效果属于浏览器验收。使用 `vitest` 的组件测试交给已有 Vitest/jsdom 与 jest-dom setup，不能被 Node 错误执行。转换不是类型检查，也不代表真实外部工具已执行。
