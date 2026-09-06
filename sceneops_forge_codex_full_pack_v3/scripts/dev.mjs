import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { randomBytes } from 'node:crypto';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { pythonEnvironment } from './python-workspace.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const python = process.env.SCENEOPS_PYTHON ?? path.join(root, '.venv/bin/python');
if (!existsSync(python) || !existsSync(path.join(root, 'node_modules/.bin/vite'))) {
  console.error('启动依赖尚未准备。请先按 README 的安装说明准备 pnpm 依赖与 Python .venv；启动器不会自动安装。');
  process.exit(1);
}
const env = pythonEnvironment({...process.env, SCENEOPS_LOCAL_TOKEN: randomBytes(32).toString('base64url'),
  SCENEOPS_WEB_PORT: process.env.SCENEOPS_WEB_PORT ?? '4300', SCENEOPS_API_PORT: process.env.SCENEOPS_API_PORT ?? '8300'});
const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) if (child.exitCode === null) child.kill('SIGTERM');
  process.exitCode = code;
}
function start(command, args) {
  const child = spawn(command, args, {cwd: root, env, stdio: 'inherit'});
  children.push(child);
  child.on('error', error => {console.error(error.message); stop(1);});
  child.on('exit', (code, signal) => {if (!stopping) stop(code ?? (signal ? 1 : 0));});
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
console.log(`SceneOps Forge · Web http://127.0.0.1:${env.SCENEOPS_WEB_PORT} · API http://127.0.0.1:${env.SCENEOPS_API_PORT}`);
console.log('空工作区启动；不安装依赖、不导入案例、不启动作业或 AI 推理。');
start(python, ['-m', 'uvicorn', 'services.api.app:create_app', '--factory', '--host', '127.0.0.1', '--port', env.SCENEOPS_API_PORT]);
// Expose the Web only after its API is ready, so initial queries cannot cache a startup 502.
const deadline = Date.now() + 60_000;
let ready = false;
while (!stopping && Date.now() < deadline) {
  try {
    const response = await fetch(`http://127.0.0.1:${env.SCENEOPS_API_PORT}/api/health`, {
      signal: AbortSignal.timeout(1000),
    });
    ready = response.ok && (await response.json()).status === 'ready';
  } catch { /* The API is still binding its loopback listener. */ }
  if (ready) break;
  await delay(200);
}
if (!stopping) {
  if (ready) start(path.join(root, 'node_modules/.bin/vite'), ['--config', 'apps/web/vite.config.ts']);
  else { console.error('API 在 60 秒内未就绪，请查看上方启动错误。'); stop(1); }
}
