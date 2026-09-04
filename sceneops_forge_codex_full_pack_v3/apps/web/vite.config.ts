import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  resolve: {dedupe: ['react', 'react-dom', '@tanstack/react-query', 'three']},
  server: {
    host: '127.0.0.1', port: Number(process.env.SCENEOPS_WEB_PORT ?? 4300), strictPort: true,
    proxy: Object.fromEntries(['/api', '/v1'].map(path => [path, {
      target: `http://127.0.0.1:${process.env.SCENEOPS_API_PORT ?? 8300}`,
      headers: {'X-SceneOps-Token': process.env.SCENEOPS_LOCAL_TOKEN ?? ''},
    }])),
  },
});
