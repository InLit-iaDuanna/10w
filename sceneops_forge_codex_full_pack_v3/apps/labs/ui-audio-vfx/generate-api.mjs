import { execFileSync } from 'node:child_process';
import { writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import openapiTS, { astToString } from 'openapi-typescript';
import { directory, root, modules, python, env } from './runtime.mjs';

for (const id of modules) {
  const moduleName = id.replaceAll('-', '_');
  const source = `import json\nfrom fastapi import FastAPI\nfrom ${moduleName} import create_lab_router\napp=FastAPI()\napp.include_router(create_lab_router())\nprint(json.dumps(app.openapi()))`;
  const schema = JSON.parse(execFileSync(python, ['-c', source], { cwd: directory, env, encoding: 'utf8' }));
  const output = astToString(await openapiTS(schema));
  await writeFile(resolve(root, 'modules', id, 'frontend/src/lab-api.ts'),
    '// Generated from the public Pydantic/OpenAPI router. Do not edit.\n' + output);
  console.log(`已生成 ${id} API 类型`);
}
