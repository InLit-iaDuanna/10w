import { createRequire } from 'node:module';
const runtime = createRequire(new URL('../modules/character-animation/frontend/package.json', import.meta.url));
export default {
  resolve: { alias: { vitest: runtime.resolve('vitest/dist/index.js'), 'react-dom/client': runtime.resolve('react-dom/client') } },
  test: { environment: 'jsdom', include: ['modules/design-room/frontend/src/tests/journey-ui-smoke.test.tsx'] },
};
