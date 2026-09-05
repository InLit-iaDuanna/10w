import { readFileSync, realpathSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const applicationRoot = fileURLToPath(new URL('../', import.meta.url));

/** Use the same checked-in package sources for API startup and contract generation.
 * Only local packages explicitly declared in requirements participate; this is not
 * runtime plugin discovery and never inspects a user's production project.
 */
export function pythonEnvironment(environment = process.env) {
  const declarations = readFileSync(path.join(applicationRoot, 'services/api/requirements.txt'), 'utf8');
  const sources = declarations.split('\n').map(line => line.trim().replace(/^-e /, ''))
    .filter(line => /^(modules|packages|integrations)\/[a-zA-Z0-9/_-]+$/.test(line))
    .map(directory => {
      const source = realpathSync(path.join(applicationRoot, directory, 'src'));
      if (!source.startsWith(realpathSync(applicationRoot) + path.sep)) throw new Error('Python source is outside the application workspace');
      return source;
    });
  return {...environment, PYTHONPATH: sources.join(path.delimiter)};
}
