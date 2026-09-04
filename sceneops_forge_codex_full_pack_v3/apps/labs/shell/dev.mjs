import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const directory = dirname(fileURLToPath(import.meta.url));
const webPort = process.env.LAB_WEB_PORT || '4310';
const apiPort = process.env.LAB_API_PORT || '8310';
const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children) if (child.exitCode === null) child.kill('SIGTERM');
}
function start(command, args, env = process.env) {
  const child = spawn(command, args, { cwd: directory, env, stdio: 'inherit' });
  children.push(child);
  child.on('error', error => { console.error(error.message); stop(1); });
  child.on('exit', code => { if (!stopping) stop(code || 0); });
}
const venvPython = resolve(directory, '../../../.venv/bin/python');
start(process.env.LAB_PYTHON || (existsSync(venvPython) ? venvPython : 'python3'), ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', apiPort], {
  ...process.env, LAB_WEB_PORT: webPort,
  PYTHONPATH: [resolve(directory, '../../../modules/conversation-home/backend/src'), process.env.PYTHONPATH].filter(Boolean).join(':'),
});
start(process.execPath, [resolve(directory, '../../../node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', webPort, '--strictPort'], { ...process.env, LAB_API_PORT: apiPort });
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
