import { defineConfig } from 'vite';

export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { dedupe: ['react', 'react-dom', '@tanstack/react-query'] },
  server: {
    host: '127.0.0.1', port: 4313, strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8313' },
  },
});
