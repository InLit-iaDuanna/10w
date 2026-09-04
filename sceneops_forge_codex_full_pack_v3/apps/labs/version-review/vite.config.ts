import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { dedupe: ['react', 'react-dom', '@tanstack/react-query'] },
  server: {
    host: '127.0.0.1', port: Number(process.env.PORT ?? 4318), strictPort: true,
    fs: { allow: [fileURLToPath(new URL('../../..', import.meta.url))] },
    proxy: { '/api': { target: `http://127.0.0.1:${process.env.API_PORT ?? 8318}`, changeOrigin: false } },
  },
});
