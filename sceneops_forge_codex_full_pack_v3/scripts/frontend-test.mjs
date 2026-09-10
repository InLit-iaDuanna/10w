import { readdir, readFile, stat } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
async function discover(path) {
  if (!(await stat(path)).isDirectory()) return [path];
  const entries = await readdir(path, { withFileTypes: true });
  return (await Promise.all(entries.filter(entry => entry.name !== 'node_modules').map(entry => {
    const child = resolve(path, entry.name);
    return entry.isDirectory() ? discover(child) : /\.test\.(?:tsx?|mjs)$/.test(entry.name) ? [child] : [];
  }))).flat();
}
const requested = process.argv.slice(2);
if (!requested.length) throw new Error('Pass explicit test files or frontend test directories.');
const files = [...new Set((await Promise.all(requested.map(path => discover(resolve(path))))).flat())].sort();
if (!files.length) throw new Error('No frontend tests found.');
const nodeFiles = [], componentFiles = [];
for (const file of files) {
  (/from\s+['"]vitest['"]/.test(await readFile(file, 'utf8')) ? componentFiles : nodeFiles).push(file);
}
function run(args) {
  const result = spawnSync(process.execPath, args, { cwd: root, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
if (nodeFiles.length) run(['--import', resolve(root, 'scripts/frontend-test-register.mjs'), '--test', ...nodeFiles]);
if (componentFiles.length) {
  const runtime = createRequire(new URL('../modules/character-animation/frontend/package.json', import.meta.url));
  run([runtime.resolve('vitest/vitest.mjs'), 'run', '--config', 'scripts/frontend-components.config.mjs', ...componentFiles]);
}
