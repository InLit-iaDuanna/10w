import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { mkdirSync, writeFileSync } from 'node:fs';
import openapiTS, { astToString } from 'openapi-typescript';

const here = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(here, '../../..');
const output = execFileSync(process.env.RENDER_PYTHON || resolve(here, '.venv/bin/python'),
  ['-c', 'import json; from api import app; print(json.dumps(app.openapi()))'],
  { cwd: here, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONPATH: resolve(root, 'modules/render-ops/backend/src') } });
const schema = JSON.parse(output.toString());
const types = await openapiTS(schema);
mkdirSync(resolve(root, 'modules/render-ops/frontend/src/generated'), { recursive: true });
writeFileSync(resolve(root, 'modules/render-ops/frontend/src/generated/lab-api.d.ts'),
  '// Generated from the local FastAPI OpenAPI document. Do not edit manually.\n' + astToString(types));
console.log('Generated Render Ops workbench API types.');
