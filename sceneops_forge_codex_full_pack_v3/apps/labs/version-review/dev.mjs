import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createRequire } from 'node:module';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../../..');
const webPort = Number(process.env.PORT ?? 4318);
const apiPort = Number(process.env.API_PORT ?? 8318);
const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill('SIGTERM');
  process.exitCode = code;
}
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => stop());

try {
  for (const port of [webPort, apiPort]) {
    if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error(`端口无效：${port}`);
    await new Promise((resolve, reject) => {
      const probe = createServer();
      probe.once('error', error => reject(new Error(error.code === 'EADDRINUSE'
        ? `127.0.0.1:${port} 已占用。请设置 PORT/API_PORT，不会终止其他进程。`
        : `无法绑定 127.0.0.1:${port}：${error.code} ${error.message}`)));
      probe.listen(port, '127.0.0.1', () => probe.close(resolve));
    });
  }
  if (webPort === apiPort) throw new Error('Web 和 API 必须使用不同端口。');
  const require = createRequire(import.meta.url);
  const vite = path.join(path.dirname(require.resolve('vite/package.json')), 'bin/vite.js');
  const environment = { ...process.env, API_PORT: String(apiPort), PORT: String(webPort),
    PYTHONPATH: path.join(root, 'modules/version-collaboration/backend/src') };
  for (const [command, args] of [
    [process.env.PYTHON ?? 'python3', ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', String(apiPort)]],
    [process.execPath, [vite, '--config', 'vite.config.ts']],
  ]) {
    const child = spawn(command, args, { cwd: directory, env: environment, stdio: 'inherit' });
    children.push(child);
    child.on('error', error => { console.error(error.message); stop(1); });
    child.on('exit', code => { if (!stopping) stop(code ?? 1); });
  }
  console.log(`版本评审 · http://127.0.0.1:${webPort} · API http://127.0.0.1:${apiPort}`);
} catch (error) { console.error(error.message); stop(1); }
