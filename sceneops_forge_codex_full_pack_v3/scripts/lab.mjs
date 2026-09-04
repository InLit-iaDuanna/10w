import { existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const [id, ...args] = process.argv.slice(2);
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
if (!id || !/^[a-z][a-z0-9-]*$/.test(id)) {
  console.error('用法：pnpm lab <lab-id> [dev 参数]');
  process.exit(1);
}
const directory = resolve(root, 'apps/labs', id);
if (!existsSync(resolve(directory, 'package.json'))) {
  console.error(`工作台 ${id} 尚未安装：${directory}`);
  process.exit(1);
}
const child = spawn('pnpm', ['--dir', directory, 'dev', ...args], { stdio: 'inherit' });
child.on('error', (error) => { console.error(error.message); process.exitCode = 1; });
child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
