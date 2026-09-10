import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { existsSync } from 'node:fs';
import { createServer } from 'node:http';
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
const webPort = process.env.SCENEOPS_WEB_PORT ?? '4300';
const apiPort = process.env.SCENEOPS_API_PORT ?? '8300';
const supervisorPort = process.env.SCENEOPS_SUPERVISOR_PORT ?? String(Number(apiPort) + 1);
const env = pythonEnvironment({...process.env, SCENEOPS_LOCAL_TOKEN: randomBytes(32).toString('base64url'),
  SCENEOPS_WEB_PORT: webPort, SCENEOPS_API_PORT: apiPort, SCENEOPS_SUPERVISOR_PORT: supervisorPort});
const children = new Set();
const expectedApiStops = new WeakSet();
let stopping = false;
let apiChild = null;
let webChild = null;
let restartPromise = null;
let supervisor = null;

function running(child) {
  return child && child.exitCode === null && child.signalCode === null;
}

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  if (supervisor?.listening) supervisor.close();
  for (const child of children) if (running(child)) child.kill('SIGTERM');
  process.exitCode = code;
}

function start(command, args, role) {
  const child = spawn(command, args, {cwd: root, env, stdio: 'inherit'});
  children.add(child);
  child.on('error', error => {
    console.error(`${role === 'api' ? '本地 API' : '网页服务'}启动失败：${error.message}`);
    if (role === 'web') stop(1);
  });
  child.on('exit', (code, signal) => {
    children.delete(child);
    if (role === 'api' && apiChild === child) apiChild = null;
    if (role === 'web' && webChild === child) webChild = null;
    if (stopping) return;
    if (role === 'web') stop(code ?? (signal ? 1 : 0));
    else if (!expectedApiStops.has(child)) console.error('本地 API 已停止，可在网页错误提示中点击“修复并重新检查”。');
  });
  return child;
}

function startApi() {
  apiChild = start(python, ['-m', 'uvicorn', 'services.api.app:create_app', '--factory',
    '--host', '127.0.0.1', '--port', apiPort], 'api');
  return apiChild;
}

async function apiReady() {
  try {
    const response = await fetch(`http://127.0.0.1:${apiPort}/api/health`, {
      signal: AbortSignal.timeout(1000),
    });
    return response.ok && (await response.json()).status === 'ready';
  } catch {
    return false;
  }
}

async function waitForApi(timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (!stopping && Date.now() < deadline) {
    if (await apiReady()) return true;
    await delay(200);
  }
  return false;
}

async function stopApi(child) {
  if (!running(child)) return;
  expectedApiStops.add(child);
  child.kill('SIGTERM');
  await Promise.race([once(child, 'exit'), delay(5000)]);
  if (running(child)) {
    child.kill('SIGKILL');
    await once(child, 'exit');
  }
}

async function restartApi() {
  if (restartPromise) return restartPromise;
  restartPromise = (async () => {
    console.log('网页请求修复：正在重启本地 API…');
    await stopApi(apiChild);
    const child = startApi();
    if (!await waitForApi(60_000) || apiChild !== child) {
      throw new Error('本地 API 在 60 秒内没有恢复。');
    }
    console.log('网页请求修复：本地 API 已恢复。');
    return {state: 'ready', message: '本地服务已重启，正在重新检查连接。'};
  })().finally(() => { restartPromise = null; });
  return restartPromise;
}

function respond(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, {'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload), 'Cache-Control': 'no-store'});
  response.end(payload);
}

async function startSupervisor() {
  const origins = new Set([`http://127.0.0.1:${webPort}`, `http://localhost:${webPort}`]);
  supervisor = createServer(async (request, response) => {
    if (request.method !== 'POST' || request.url !== '/__sceneops/runtime/restart-api') {
      respond(response, 404, {message: '未知的本地恢复操作。'});
      return;
    }
    if (!origins.has(request.headers.origin ?? '')
        || request.headers['x-sceneops-token'] !== env.SCENEOPS_LOCAL_TOKEN) {
      respond(response, 403, {message: '本地恢复请求未通过来源验证。'});
      return;
    }
    request.resume();
    try {
      respond(response, 200, await restartApi());
    } catch (error) {
      respond(response, 503, {message: error instanceof Error ? error.message : String(error)});
    }
  });
  supervisor.on('error', error => { console.error(`本地恢复服务启动失败：${error.message}`); stop(1); });
  supervisor.listen(Number(supervisorPort), '127.0.0.1');
  await once(supervisor, 'listening');
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
console.log(`SceneOps Forge · Web http://127.0.0.1:${env.SCENEOPS_WEB_PORT} · API http://127.0.0.1:${env.SCENEOPS_API_PORT}`);
console.log('空工作区启动；不安装依赖、不导入案例、不启动作业或 AI 推理。');
await startSupervisor();
startApi();
// Expose the Web only after its API is ready, so initial queries cannot cache a startup 502.
const ready = await waitForApi(60_000);
if (!stopping) {
  if (ready) webChild = start(path.join(root, 'node_modules/.bin/vite'),
    ['--config', 'apps/web/vite.config.ts'], 'web');
  else { console.error('API 在 60 秒内未就绪，请查看上方启动错误。'); stop(1); }
}
