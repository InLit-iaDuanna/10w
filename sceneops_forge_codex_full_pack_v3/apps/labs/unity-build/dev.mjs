import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";
const cwd = fileURLToPath(new URL(".", import.meta.url));
const port = Number(process.env.API_PORT || 8317),
  web = Number(process.env.WEB_PORT || 4317);
for (const value of [port, web])
  await new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", () =>
      reject(
        new Error(
          `localhost:${value} 已占用；请显式设置 API_PORT / WEB_PORT，现有进程不会被关闭。`,
        ),
      ),
    );
    server.listen(value, "127.0.0.1", () => server.close(resolve));
  });
const python = process.env.PYTHON || `${cwd}.venv/bin/python`;
const api = spawn(
  python,
  ["-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", String(port)],
  {
    cwd,
    stdio: "inherit",
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  },
);
const vite = spawn(process.execPath, [`${cwd}node_modules/vite/bin/vite.js`], {
  cwd,
  stdio: "inherit",
});
const stop = () => {
  api.kill("SIGTERM");
  vite.kill("SIGTERM");
};
for (const child of [api, vite]) {
  child.on("error", (e) => {
    console.error(e.message);
    stop();
    process.exitCode = 1;
  });
  child.on("exit", (code) => {
    stop();
    process.exitCode = code || 0;
  });
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
