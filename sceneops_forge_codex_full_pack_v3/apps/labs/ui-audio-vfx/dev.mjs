import { spawn } from 'node:child_process';
import net from 'node:net';
import { resolve } from 'node:path';
import { directory, python, env } from './runtime.mjs';

const webPort = Number(process.env.LAB_WEB_PORT ?? 4315);
const apiPort = Number(process.env.LAB_API_PORT ?? 8315);
const children = [];
let stopping = false;
function stop(code) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children) child.kill('SIGTERM');
}
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => stop(0));
function start(command, args) {
  const child = spawn(command, args, { cwd: directory, env: { ...env,
    LAB_WEB_PORT: String(webPort), LAB_API_PORT: String(apiPort) }, stdio: 'inherit' });
  children.push(child);
  child.on('error', error => { console.error(`启动失败：${error.message}。请先完成 README 的安装步骤。`); stop(1); });
  child.on('exit', code => { if (!stopping) stop(code || 1); });
}
async function available(port) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('端口必须在 1024–65535 之间');
  await new Promise((done, reject) => {
    const server = net.createServer();
    server.once('error', () => reject(new Error(`127.0.0.1:${port} 已占用或不可绑定；请显式设置 LAB_WEB_PORT / LAB_API_PORT`)));
    server.listen(port, '127.0.0.1', () => server.close(done));
  });
}
try {
  if (webPort === apiPort) throw new Error('Web 与 API 必须使用不同端口');
  await Promise.all([available(webPort), available(apiPort)]);
  start(python, ['-m', 'uvicorn', 'server:app', '--host', '127.0.0.1', '--port', String(apiPort)]);
  start(process.execPath, [resolve(directory, 'node_modules/vite/bin/vite.js')]);
} catch (error) { console.error(error.message); stop(1); }
