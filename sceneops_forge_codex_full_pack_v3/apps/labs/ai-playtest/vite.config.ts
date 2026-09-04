import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

const local = (path: string) => fileURLToPath(new URL(path, import.meta.url));
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: [
      { find: /^react-dom(\/.*)?$/, replacement: local("./node_modules/react-dom") + "$1" },
      { find: /^react(\/.*)?$/, replacement: local("./node_modules/react") + "$1" },
      { find: "zod", replacement: local("./node_modules/zod") },
    ],
    dedupe: ["react", "react-dom"],
  },
  server: { host: "127.0.0.1", port: 4319, strictPort: true, fs: { allow: [local("."), local("../../../modules/ai-playtest")] } },
});
