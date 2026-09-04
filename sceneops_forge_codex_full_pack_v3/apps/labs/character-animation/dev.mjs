import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const directory = dirname(fileURLToPath(import.meta.url));
const python = process.env.CHARACTER_LAB_PYTHON || 'python3';
const children = [];
let stopping = false;
function stop(code) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children) child.kill('SIGTERM');
}
async function ensurePort(port) {
  await new Promise((accept, reject) => {
    const socket = createServer();
    socket.once('error', (error) => reject(new Error(`127.0.0.1:${port} 无法绑定（${error.code}）：${error.message}。请检查端口占用或本地监听权限；未终止其他进程。`)));
    socket.listen(port, '127.0.0.1', () => socket.close(accept));
  });
}
function launch(command, args, env = process.env) {
  const child = spawn(command, args, { cwd: directory, env, stdio: 'inherit' });
  children.push(child);
  child.on('error', (error) => { console.error(`启动失败：${error.message}`); stop(1); });
  child.on('exit', (code) => { if (!stopping) stop(code || 1); });
}
try {
  await Promise.all([ensurePort(4313), ensurePort(8313)]);
  launch(python, ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8313'], {
    ...process.env, PYTHONDONTWRITEBYTECODE: '1',
    PYTHONPATH: resolve(directory, '../../../modules/character-animation/backend/src'),
  });
  launch('pnpm', ['exec', 'vite']);
  console.log('角色与动画：Web http://127.0.0.1:4313 · API http://127.0.0.1:8313');
} catch (error) { console.error(error.message); stop(1); }
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => stop(0));
