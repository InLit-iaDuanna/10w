import { defineConfig } from 'vite';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '../../..');
const local = (name: string) => resolve(import.meta.dirname, 'node_modules', name);
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: {
    '@sceneops/ui-studio': resolve(root, 'modules/ui-studio/frontend/src/index.ts'),
    '@sceneops/audio-studio-frontend': resolve(root, 'modules/audio-studio/frontend/src/index.ts'),
    '@sceneops/vfx-shader-frontend': resolve(root, 'modules/vfx-shader/frontend/src/index.ts'),
    'react': local('react'), 'react-dom': local('react-dom'),
    '@tanstack/react-query': local('@tanstack/react-query'),
  } },
  server: { host: '127.0.0.1', port: Number(process.env.LAB_WEB_PORT ?? 4315), strictPort: true,
    fs: { allow: [root] }, proxy: { '/api': `http://127.0.0.1:${process.env.LAB_API_PORT ?? 8315}` } },
});
