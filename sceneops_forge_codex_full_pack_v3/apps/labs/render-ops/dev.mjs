import { spawn } from 'node:child_process';
import { createServer as createNetServer } from 'node:net';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { createServer } from 'vite';

const here = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(here, '../../..');
const webPort = Number(process.env.RENDER_WEB_PORT || 4316);
const apiPort = Number(process.env.RENDER_API_PORT || 8316);
for (const port of [webPort, apiPort]) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('端口必须为 1024–65535 的整数。');
  await new Promise((accept, reject) => {
    const probe = createNetServer();
    probe.once('error', error => reject(error.code === 'EADDRINUSE'
      ? new Error(`127.0.0.1:${port} 已占用。请设置 RENDER_WEB_PORT / RENDER_API_PORT。`)
      : error));
    probe.listen(port, '127.0.0.1', () => probe.close(accept));
  });
}
const python = process.env.RENDER_PYTHON || resolve(here, '.venv/bin/python');
const api = spawn(python, ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', String(apiPort)], {
  cwd: here, stdio: 'inherit', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1',
    PYTHONPATH: resolve(root, 'modules/render-ops/backend/src') },
});
let server;
let closing = false;
async function stop(code = 0) {
  if (closing) return;
  closing = true;
  await server?.close();
  if (api.exitCode === null) api.kill('SIGTERM');
  process.exitCode = code;
}
api.once('error', error => { console.error(`API 无法启动：${error.message}。请先按 README 安装 Python 依赖。`); void stop(1); });
api.once('exit', code => { if (!closing) void stop(code || 1); });
process.once('SIGINT', () => void stop());
process.once('SIGTERM', () => void stop());
try {
  for (let attempt = 0; attempt < 80; attempt++) {
    if (closing) throw new Error('API 启动失败。');
    try {
      const response = await fetch(`http://127.0.0.1:${apiPort}/api/render-lab/health`);
      if (response.ok) break;
    } catch { /* API process is still starting; bounded startup readiness wait. */ }
    if (attempt === 79) throw new Error('API 在 20 秒内未能启动。');
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  server = await createServer({
    root: here, configFile: false,
    resolve: { alias: {
      react: resolve(here, 'node_modules/react'),
      'react-dom': resolve(here, 'node_modules/react-dom'),
      '@tanstack/react-query': resolve(here, 'node_modules/@tanstack/react-query'),
      'openapi-fetch': resolve(here, 'node_modules/openapi-fetch'),
    }, dedupe: ['react', 'react-dom'] },
    server: { host: '127.0.0.1', port: webPort, strictPort: true,
      fs: { allow: [root] }, proxy: { '/api': `http://127.0.0.1:${apiPort}` } },
  });
  await server.listen();
  console.log(`渲染与 AI 变体工作台（MOCK）→ http://127.0.0.1:${webPort}`);
} catch (error) { console.error(error.message); await stop(1); }
