import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
const local = (path: string) => fileURLToPath(new URL(path, import.meta.url));
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      react: local("./node_modules/react"),
      "react-dom": local("./node_modules/react-dom"),
      "@tanstack/react-query": local("./node_modules/@tanstack/react-query"),
      "openapi-fetch": local("./node_modules/openapi-fetch"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: Number(process.env.WEB_PORT || 4317),
    strictPort: true,
    fs: { allow: [local("../../../")] },
    proxy: { "/api": `http://127.0.0.1:${process.env.API_PORT || 8317}` },
  },
});
