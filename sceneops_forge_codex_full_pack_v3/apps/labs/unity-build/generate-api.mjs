import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const cwd = fileURLToPath(new URL(".", import.meta.url));
const result = spawnSync(
  process.env.PYTHON || `${cwd}.venv/bin/python`,
  ["-c", "import json; from api import app; print(json.dumps(app.openapi()))"],
  {
    cwd,
    encoding: "utf8",
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  },
);
if (result.status !== 0) throw new Error(result.stderr);
const { default: openapiTS, astToString } =
  await import("./contract-tools/node_modules/openapi-typescript/dist/index.mjs");
const { writeFileSync } = await import("node:fs");
writeFileSync(
  new URL(
    "../../../modules/build-release/frontend/src/workbench/api.generated.ts",
    import.meta.url,
  ),
  "// Generated from the local FastAPI OpenAPI contract. Do not edit.\n" +
    astToString(await openapiTS(JSON.parse(result.stdout))),
);
