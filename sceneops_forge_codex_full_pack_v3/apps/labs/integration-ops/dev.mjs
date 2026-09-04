import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { randomBytes } from 'node:crypto';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { existsSync } from 'node:fs';

const lab = dirname(fileURLToPath(import.meta.url));
const root = resolve(lab, '../../..');
const webPort = Number(process.env.WEB_PORT || 4320);
const apiPort = Number(process.env.API_PORT || 8320);
const python = process.env.PYTHON || resolve(lab, '.venv/bin/python');
if (!existsSync(python)) throw new Error('缺少 Python 环境；请先按本工作台 README 安装依赖。');
for (const port of [webPort, apiPort]) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('端口必须在 1024–65535。');
  await new Promise((done, reject) => {
    const server = createServer();
    server.once('error', error => reject(new Error(error.code === 'EADDRINUSE'
      ? `127.0.0.1:${port} 已占用；请设置 WEB_PORT / API_PORT。`
      : `无法绑定 127.0.0.1:${port}：${error.code}。请检查宿主端口权限。`)));
    server.listen(port, '127.0.0.1', () => server.close(done));
  });
}
if (webPort === apiPort) throw new Error('Web 与 API 端口必须不同。');
const env = { ...process.env, WEB_PORT: String(webPort), API_PORT: String(apiPort),
  INTEGRATION_OPS_TOKEN: randomBytes(32).toString('hex'), PYTHONDONTWRITEBYTECODE: '1',
  PYTHONPATH: [resolve(root, 'modules/integration-center/backend/src'),
    resolve(root, 'modules/observability/backend/src')].join(':') };
const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) if (child.exitCode === null) child.kill('SIGTERM');
  process.exitCode = code;
}
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => stop());
const api = spawn(python, ['-m', 'uvicorn', 'api:create_app', '--factory', '--host', '127.0.0.1',
  '--port', String(apiPort), '--no-access-log'], { cwd: lab, env, stdio: 'inherit' });
children.push(api);
api.on('error', error => { console.error(error.message); stop(1); });
api.on('exit', code => stop(code || 0));
const web = spawn(process.execPath, [resolve(lab, 'node_modules/vite/bin/vite.js')],
  { cwd: lab, env, stdio: 'inherit' });
children.push(web);
web.on('error', error => { console.error(error.message); stop(1); });
web.on('exit', code => stop(code || 0));
console.log(`集成状态与运行日志： http://127.0.0.1:${webPort} （Mock 演示）`);
