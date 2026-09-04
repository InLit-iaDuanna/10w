import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  resolve: {
    alias: {
      react: resolve('node_modules/react'),
      'react-dom': resolve('node_modules/react-dom'),
      '@tanstack/react-query': resolve('node_modules/@tanstack/react-query'),
      'openapi-fetch': resolve('node_modules/openapi-fetch'),
    },
    dedupe: ['react', 'react-dom'],
  },
  esbuild: { jsx: 'automatic' },
  server: {
    host: '127.0.0.1', port: Number(process.env.WEB_PORT || 4320), strictPort: true,
    fs: { allow: [resolve('../../..')] },
    proxy: { '/api': { target: `http://127.0.0.1:${process.env.API_PORT || 8320}`,
      headers: { 'x-integration-ops-token': process.env.INTEGRATION_OPS_TOKEN || '' } } },
  },
});
