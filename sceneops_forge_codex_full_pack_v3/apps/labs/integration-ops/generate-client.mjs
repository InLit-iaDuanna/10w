import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { writeFileSync, unlinkSync } from 'node:fs';

const root = resolve('../../..');
const result = spawnSync('.venv/bin/python', ['-c',
  'import json; from api import create_app; print(json.dumps(create_app().openapi()))'], {
  encoding: 'utf8', env: { ...process.env, INTEGRATION_OPS_TOKEN: 'schema-generation-only',
    PYTHONDONTWRITEBYTECODE: '1', PYTHONPATH: `${root}/modules/integration-center/backend/src:${root}/modules/observability/backend/src` },
});
if (result.status !== 0) throw new Error(result.stderr);
writeFileSync('.openapi.json', result.stdout);
const generated = spawnSync('pnpm', ['exec', 'openapi-typescript', '.openapi.json', '-o',
  '../../../modules/integration-center/frontend/src/generated/operations-api.ts'], { stdio: 'inherit' });
unlinkSync('.openapi.json');
process.exitCode = generated.status || 0;
