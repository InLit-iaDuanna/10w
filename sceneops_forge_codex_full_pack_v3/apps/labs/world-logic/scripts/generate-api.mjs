import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve, delimiter } from 'node:path';
import { writeFileSync, existsSync } from 'node:fs';
import openapiTS, { astToString } from './codegen/node_modules/openapi-typescript/dist/index.mjs';
const lab = fileURLToPath(new URL('../', import.meta.url));
const root = resolve(lab, '../../..');
const python = process.env.WORLD_LOGIC_PYTHON || (existsSync(resolve(lab, '.venv/bin/python')) ? resolve(lab, '.venv/bin/python') : 'python3');
const result = spawnSync(python, ['-c', 'import json; from api import app; print(json.dumps(app.openapi()))'], {
  cwd: lab, encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONPATH: ['modules/logic-studio/backend/src','modules/world-composer/backend/src','packages/core-contracts/src'].map(p => resolve(root,p)).join(delimiter) },
});
if (result.status !== 0) throw new Error(result.stderr);
const source = '// Generated from the local FastAPI OpenAPI schema. Do not edit.\n' + astToString(await openapiTS(JSON.parse(result.stdout)));
writeFileSync(resolve(root, 'modules/logic-studio/frontend/src/generated/workbench-api.ts'), source);
