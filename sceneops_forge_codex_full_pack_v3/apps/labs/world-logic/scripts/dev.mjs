import { spawn } from 'node:child_process';
import { createServer as createNetServer } from 'node:net';
import { fileURLToPath } from 'node:url';
import { delimiter, resolve } from 'node:path';
import { existsSync } from 'node:fs';
import { createServer } from 'vite';

const lab = fileURLToPath(new URL('../', import.meta.url));
const root = resolve(lab, '../../..');
const webPort = Number(process.env.WORLD_LOGIC_WEB_PORT || 4314);
const apiPort = Number(process.env.WORLD_LOGIC_API_PORT || 8314);
const python = process.env.WORLD_LOGIC_PYTHON || (existsSync(resolve(lab, '.venv/bin/python')) ? resolve(lab, '.venv/bin/python') : 'python3');
for (const port of [webPort, apiPort]) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error(`无效端口 ${port}`);
  await new Promise((accept, reject) => {
    const probe = createNetServer();
    probe.once('error', () => reject(new Error(`127.0.0.1:${port} 已被占用；请显式配置端口，不会结束其他进程。`)));
    probe.listen(port, '127.0.0.1', () => probe.close(accept));
  });
}
const PYTHONPATH = ['modules/logic-studio/backend/src', 'modules/world-composer/backend/src', 'packages/core-contracts/src'].map(p => resolve(root, p)).join(delimiter);
const dependencies = ['react', 'react-dom', 'three', '@tanstack/react-query', 'openapi-fetch'];
const server = await createServer({
  root: lab,
  esbuild: { jsx: 'automatic' },
  resolve: { alias: [
    { find: '@sceneops/scene-viewer/react', replacement: resolve(root, 'packages/scene-viewer/src/react.tsx') },
    { find: /^@sceneops\/scene-viewer$/, replacement: resolve(root, 'packages/scene-viewer/src/index.ts') },
    ...dependencies.map(name => ({ find: name, replacement: resolve(lab, 'node_modules', name) })),
  ], dedupe: dependencies },
  server: { host: '127.0.0.1', port: webPort, strictPort: true, fs: { allow: [root] }, proxy: { '/api': `http://127.0.0.1:${apiPort}` } },
});
await server.listen();
const api = spawn(python, ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', String(apiPort)], {
  cwd: lab, stdio: 'inherit', env: { ...process.env, PYTHONPATH, WORLD_LOGIC_WEB_PORT: String(webPort), WORLD_LOGIC_API_PORT: String(apiPort), PYTHONDONTWRITEBYTECODE: '1' },
});
let closing = false;
async function close(code = 0) {
  if (closing) return;
  closing = true;
  await server.close();
  if (api.exitCode === null) api.kill('SIGTERM');
  process.exitCode = code;
}
api.on('error', error => { console.error(error.message); void close(1); });
api.on('exit', code => { if (!closing) void close(code || 1); });
process.on('SIGINT', () => void close());
process.on('SIGTERM', () => void close());
server.printUrls();
