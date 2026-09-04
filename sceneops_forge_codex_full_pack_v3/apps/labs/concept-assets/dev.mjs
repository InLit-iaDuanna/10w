import { spawn } from 'node:child_process';
import net from 'node:net';
import { fileURLToPath } from 'node:url';
const cwd = fileURLToPath(new URL('.', import.meta.url));
const web = Number(process.env.WEB_PORT || 4312), api = Number(process.env.API_PORT || 8312);
for (const port of [web, api]) {
  await new Promise((resolve, reject) => {
    const s = net.createServer();
    s.once('error', () => reject(new Error(`127.0.0.1:${port} 已占用；请设置 WEB_PORT / API_PORT`)));
    s.listen(port, '127.0.0.1', () => s.close(resolve));
  });
}
const children = [
  spawn(`${cwd}.venv/bin/python`, ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', String(api)], { cwd, stdio: 'inherit' }),
  spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(web), '--strictPort'], { cwd, stdio: 'inherit', env: { ...process.env, API_PORT: String(api) } }),
];
let stopping = false;
function stop(code = 0) { if (stopping) return; stopping = true; for (const c of children) c.kill('SIGTERM'); process.exitCode = code; }
for (const c of children) { c.on('error', e => { console.error(e.message); stop(1); }); c.on('exit', code => stop(code || 0)); }
process.on('SIGINT', () => stop()); process.on('SIGTERM', () => stop());
