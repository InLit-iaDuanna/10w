import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = path.join(root, '.venv/bin/python');
const runtimeRequirements = path.join(root, 'services/api/requirements-runtime.txt');
const webPort = process.env.SCENEOPS_WEB_PORT ?? '4300';
const apiPort = process.env.SCENEOPS_API_PORT ?? '8300';
const webUrl = `http://127.0.0.1:${webPort}`;
const apiHealthUrl = `http://127.0.0.1:${apiPort}/api/health`;

function commandWorks(command, args = ['--version']) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'ignore' });
  return !result.error && result.status === 0;
}

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: root, stdio: 'inherit' });
    child.once('error', reject);
    child.once('exit', (code, signal) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} 退出：${code ?? signal ?? 'unknown'}`));
    });
  });
}

function packageManager() {
  if (commandWorks('pnpm')) return { command: 'pnpm', prefix: [] };
  if (commandWorks('corepack')) return { command: 'corepack', prefix: ['pnpm'] };
  throw new Error('未找到 pnpm。请先安装 Node.js 22，再重新双击启动入口。');
}

async function ensureNodeDependencies() {
  if (existsSync(path.join(root, 'node_modules/.bin/vite'))) return;
  console.log('首次启动：正在准备网页依赖…');
  const manager = packageManager();
  await run(manager.command, [...manager.prefix, 'install', '--ignore-scripts']);
}

function pythonRuntimeReady() {
  if (!existsSync(python)) return false;
  const imports = 'import fastapi,httpx,jsonschema,pydantic,uvicorn,yaml';
  return commandWorks(python, ['-c', imports]);
}

async function ensurePythonRuntime() {
  const hasUv = commandWorks('uv');
  if (!existsSync(python)) {
    console.log('首次启动：正在创建 Python 3.12 环境…');
    if (hasUv) await run('uv', ['venv', '--python', '3.12', '.venv']);
    else if (commandWorks('python3.12')) await run('python3.12', ['-m', 'venv', '.venv']);
    else throw new Error('未找到 Python 3.12。请先安装 Python 3.12，再重新双击启动入口。');
  }
  if (pythonRuntimeReady()) return;
  console.log('首次启动：正在准备本地 API 依赖…');
  if (hasUv) await run('uv', ['pip', 'install', '--python', python, '-r', runtimeRequirements]);
  else await run(python, ['-m', 'pip', 'install', '-r', runtimeRequirements]);
  if (!pythonRuntimeReady()) throw new Error('Python 运行依赖未能完整安装。');
}

async function responseReady(url, expectedStatus) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(1000) });
    if (!response.ok) return false;
    if (!expectedStatus) return true;
    return (await response.json()).status === expectedStatus;
  } catch {
    return false;
  }
}

function openBrowser() {
  if (process.env.SCENEOPS_OPEN_BROWSER === '0') return;
  const target = `${webUrl}/`;
  let command;
  let args;
  if (process.platform === 'darwin') {
    command = 'open'; args = [target];
  } else if (process.platform === 'win32') {
    command = 'cmd'; args = ['/c', 'start', '', target];
  } else {
    command = 'xdg-open'; args = [target];
  }
  const opener = spawn(command, args, { detached: true, stdio: 'ignore' });
  opener.once('error', () => console.log(`请打开 ${target}`));
  opener.unref();
}

async function main() {
  const nodeVersion = process.versions.node.split('.').map(Number);
  if (nodeVersion[0] < 22 || (nodeVersion[0] === 22 && nodeVersion[1] < 12)) {
    throw new Error(`当前 Node.js 为 ${process.versions.node}，SceneOps 需要 22.12 或更高版本。`);
  }
  await ensureNodeDependencies();
  await ensurePythonRuntime();

  if (await responseReady(apiHealthUrl, 'ready') && await responseReady(`${webUrl}/`)) {
    console.log(`SceneOps 已在运行：${webUrl}`);
    openBrowser();
    return;
  }

  console.log('正在启动 SceneOps…');
  const child = spawn(process.execPath, [path.join(root, 'scripts/dev.mjs')], {
    cwd: root,
    env: { ...process.env, SCENEOPS_PYTHON: python },
    stdio: 'inherit',
  });
  let exitResult = null;
  const exitPromise = new Promise(resolve => child.once('exit', (code, signal) => {
    exitResult = { code, signal };
    resolve(exitResult);
  }));
  const stop = signal => {
    if (child.exitCode === null && !child.killed) child.kill(signal);
  };
  process.once('SIGINT', () => stop('SIGINT'));
  process.once('SIGTERM', () => stop('SIGTERM'));

  const deadline = Date.now() + 90_000;
  let webReady = false;
  while (!exitResult && Date.now() < deadline) {
    if (await responseReady(`${webUrl}/`)) {
      console.log(`SceneOps 已就绪：${webUrl}`);
      openBrowser();
      webReady = true;
      break;
    }
    await delay(250);
  }
  if (exitResult) throw new Error(`SceneOps 启动失败：${exitResult.code ?? exitResult.signal ?? 'unknown'}`);
  if (!webReady) {
    stop('SIGTERM');
    throw new Error('SceneOps 在 90 秒内未就绪，请查看上方提示。');
  }

  const result = await exitPromise;
  if (result.code !== 0 && result.signal !== 'SIGINT' && result.signal !== 'SIGTERM') {
    throw new Error(`SceneOps 已停止：${result.code ?? result.signal ?? 'unknown'}`);
  }
}

main().catch(error => {
  console.error(`\n无法启动：${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
