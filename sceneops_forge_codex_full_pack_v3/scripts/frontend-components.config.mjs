import { createRequire } from 'node:module';
const runtime = createRequire(new URL('../modules/character-animation/frontend/package.json', import.meta.url));
export default {
  resolve: { alias: { vitest: runtime.resolve('vitest/dist/index.js'), 'react-dom/client': runtime.resolve('react-dom/client') } },
  test: {
    environment: 'jsdom',
    setupFiles: ['modules/character-animation/frontend/src/tests/setup.ts'],
    include: ['modules/**/frontend/**/*.test.ts', 'modules/**/frontend/**/*.test.tsx', 'apps/web/src/**/*.test.tsx', 'packages/**/src/**/*.test.tsx'],
  },
};
