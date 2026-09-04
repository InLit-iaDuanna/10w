import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';
import { createServer as vite } from 'vite';
const root = fileURLToPath(new URL('.', import.meta.url));
const webPort = Number(process.env.WEB_PORT || 4311);
const apiPort = Number(process.env.API_PORT || 8311);
for (const port of [webPort, apiPort]) await new Promise((resolve, reject) => {
  const server = createServer();
  server.once('error', error => reject(new Error(error.code === 'EADDRINUSE' ? `127.0.0.1:${port} 已占用，请设置 WEB_PORT/API_PORT；未结束其他进程。` : `127.0.0.1:${port} 无法监听：${error.code} ${error.message}`)));
  server.listen(port, '127.0.0.1', () => server.close(resolve));
});
const api = spawn(process.env.PYTHON || 'python3', ['-m','uvicorn','api:app','--host','127.0.0.1','--port',String(apiPort)], {
  cwd: root, stdio: 'inherit', env: {...process.env, PYTHONDONTWRITEBYTECODE:'1', PYTHONPATH: [...['production-planner','design-room'].map(module => fileURLToPath(new URL(`../../../modules/${module}/backend/src`, import.meta.url))), fileURLToPath(new URL('../../../integrations/codebuddy-cli/src', import.meta.url))].join(':')},
});
const server = await vite({root, server:{host:'127.0.0.1',port:webPort,strictPort:true,fs:{allow:[fileURLToPath(new URL('../../../',import.meta.url))]},proxy:{'/v1':`http://127.0.0.1:${apiPort}`}},resolve:{dedupe:['react','react-dom','@tanstack/react-query'],alias:{react:fileURLToPath(new URL('node_modules/react',import.meta.url)),'react-dom':fileURLToPath(new URL('node_modules/react-dom',import.meta.url)),'@tanstack/react-query':fileURLToPath(new URL('node_modules/@tanstack/react-query',import.meta.url))}}});
await server.listen(); server.printUrls();
let closing = false;
async function close(code=0) { if(closing)return;closing=true;api.kill('SIGTERM');await server.close();process.exit(code); }
api.on('exit', code => close(code || 0));
api.on('error', error => { console.error('本地 API 启动失败：', error.message); close(1); });
process.on('SIGINT',()=>close()); process.on('SIGTERM',()=>close());
