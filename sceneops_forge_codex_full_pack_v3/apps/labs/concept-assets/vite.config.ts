import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  resolve: { alias: {
    'react-dom/client': fileURLToPath(new URL('./node_modules/react-dom/client.js', import.meta.url)),
    'react': fileURLToPath(new URL('./node_modules/react', import.meta.url)),
    '@tanstack/react-query': fileURLToPath(new URL('./node_modules/@tanstack/react-query', import.meta.url)),
  } },
  server: { fs: { allow: [fileURLToPath(new URL('../../../', import.meta.url))] },
    proxy: { '/api': `http://127.0.0.1:${process.env.API_PORT || 8312}` } },
});
