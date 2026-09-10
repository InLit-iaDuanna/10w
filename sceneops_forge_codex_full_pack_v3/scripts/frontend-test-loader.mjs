import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

// Match TypeScript/Vite source resolution for Node's independent module tests.
export async function resolve(specifier, context, nextResolve) {
  try {
    return await nextResolve(specifier, context);
  } catch (error) {
    if (!['ERR_MODULE_NOT_FOUND', 'ERR_UNSUPPORTED_DIR_IMPORT'].includes(error.code) || !specifier.startsWith('.') || /\.[a-z]+$/i.test(specifier)) throw error;
    for (const suffix of ['.ts', '.tsx', '.js', '/index.ts', '/index.tsx']) {
      try { return await nextResolve(specifier + suffix, context); }
      catch (candidateError) { if (!['ERR_MODULE_NOT_FOUND', 'ERR_UNSUPPORTED_DIR_IMPORT'].includes(candidateError.code)) throw candidateError; }
    }
    throw error;
  }
}

export async function load(url, context, nextLoad) {
  if (url.endsWith('.json')) return nextLoad(url, { ...context, importAttributes: { type: 'json' } });
  if (url.endsWith('.css')) {
    // Node contract tests have no document; browser/component suites validate styles.
    await readFile(new URL(url));
    return { format: 'module', source: 'export default {};', shortCircuit: true };
  }
  if (/\.tsx?$/.test(url)) {
    const source = await readFile(new URL(url), 'utf8');
    const result = ts.transpileModule(source, {
      fileName: fileURLToPath(url),
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX, sourceMap: false },
    });
    return { format: 'module', source: result.outputText, shortCircuit: true };
  }
  return nextLoad(url, context);
}
