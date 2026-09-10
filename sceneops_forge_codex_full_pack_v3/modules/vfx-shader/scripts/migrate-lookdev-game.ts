/** Typed WebGPU upgrade with awaited void-call propagation and serialized DOM RAF frames. */
import ts from 'typescript';
import { lstat, readdir, readFile, realpath, writeFile, rename, unlink } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { planAsyncFrames, updateAsyncFunction } from './async-frame-migration';

export interface MigrationReport { supported: boolean; changedFiles: string[]; requirements: string[]; applied: boolean }
type Change = { file: string; before: string; after: string };

async function sourceFiles(root: string): Promise<string[]> {
  const result: string[] = [];
  async function visit(directory: string) {
    for (const item of await readdir(directory, { withFileTypes: true })) {
      if (['node_modules', '.git', 'dist', 'build', '.sceneops'].includes(item.name)) continue;
      const file = path.join(directory, item.name);
      if (item.isSymbolicLink()) throw new Error(`Symbolic links are not supported: ${file}`);
      if (item.isDirectory()) await visit(file);
      else if (/\.(?:ts|tsx)$/.test(item.name) && !item.name.endsWith('.d.ts')) result.push(file);
    }
  }
  await visit(root);
  return result;
}


export async function migrateLookdevGame(directory: string, apply = false): Promise<MigrationReport> {
  const root = path.resolve(directory);
  if (await realpath(root) !== root || !(await lstat(root)).isDirectory()) throw new Error('Game root must be a real directory.');
  const files = await sourceFiles(root);
  const configPath = ts.findConfigFile(root, ts.sys.fileExists);
  const config = configPath ? ts.readConfigFile(configPath, ts.sys.readFile) : { config: {} };
  if (config.error) throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'));
  const options = ts.parseJsonConfigFileContent(config.config, ts.sys, root).options;
  const program = ts.createProgram(files, { ...options, moduleResolution: ts.ModuleResolutionKind.Bundler, module: ts.ModuleKind.ESNext, noEmit: true });
  const checker = program.getTypeChecker();
  const requirements: string[] = [];
  const changes: Change[] = [];
  let alreadyWebGPU = false;
  const isRendererSymbol = (symbol: ts.Symbol | undefined): boolean => {
    if (!symbol) return false;
    if (symbol.flags & ts.SymbolFlags.Alias) symbol = checker.getAliasedSymbol(symbol);
    return symbol.name === 'WebGLRenderer' && !!symbol.declarations?.some(declaration => declaration.getSourceFile().fileName.replaceAll('\\', '/').endsWith('/renderers/WebGLRenderer.d.ts'));
  };
  const rendererType = (type: ts.Type): boolean => {
    if (type.isIntersection()) return type.types.some(rendererType);
    if (type.isUnion()) return type.types.every(rendererType);
    return isRendererSymbol(type.getSymbol());
  };
  const isRenderer = (node: ts.Node) => rendererType(checker.getNonNullableType(checker.getTypeAtLocation(node)));
  const sourceTrees = files.map(file => program.getSourceFile(file)!);
  const allRenders = new Set<ts.CallExpression>();
  function findRenders(node: ts.Node) {
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'render' && isRenderer(node.expression.expression)) allRenders.add(node);
    ts.forEachChild(node, findRenders);
  }
  sourceTrees.forEach(findRenders);
  const frames = planAsyncFrames(sourceTrees, checker, allRenders);
  requirements.push(...frames.requirements);
  for (const file of files) {
    const source = program.getSourceFile(file)!;
    const constructors = new Set<ts.NewExpression>();
    const renders = new Set<ts.CallExpression>();
    const typeReferences = new Set<ts.TypeReferenceNode>();
    const names = new Set<string>();
    function inspect(node: ts.Node) {
      if (ts.isIdentifier(node)) names.add(node.text);
      if (ts.isNewExpression(node)) {
        let symbol = checker.getSymbolAtLocation(node.expression);
        if (symbol && symbol.flags & ts.SymbolFlags.Alias) symbol = checker.getAliasedSymbol(symbol);
        if (symbol?.name === 'WebGPURenderer' && symbol.declarations?.some(declaration => declaration.getSourceFile().fileName.replaceAll('\\', '/').endsWith('/renderers/webgpu/WebGPURenderer.d.ts'))) alreadyWebGPU = true;
      }
      if (ts.isNewExpression(node) && isRendererSymbol(checker.getSymbolAtLocation(node.expression))) constructors.add(node);
      if (ts.isTypeReferenceNode(node) && isRendererSymbol(checker.getSymbolAtLocation(node.typeName))) typeReferences.add(node);
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'render' && isRenderer(node.expression.expression)) {
        renders.add(node);
      }
      if (ts.isPropertyAccessExpression(node) && node.name.text === 'render' && isRenderer(node.expression) && !(ts.isCallExpression(node.parent) && node.parent.expression === node)) requirements.push(`${path.relative(root, file)}: Extracted render method requires explicit async migration.`);
      if (ts.isElementAccessExpression(node) && isRenderer(node.expression)) requirements.push(`${path.relative(root, file)}: Computed renderer access requires explicit async migration.`);
      if (ts.isVariableDeclaration(node) && ts.isObjectBindingPattern(node.name) && node.initializer && isRenderer(node.initializer)) requirements.push(`${path.relative(root, file)}: Destructured renderer methods require explicit async migration.`);
      if (ts.isIdentifier(node) && isRendererSymbol(checker.getSymbolAtLocation(node))) {
        const parent = node.parent;
        const reference = ts.isPropertyAccessExpression(parent) || ts.isQualifiedName(parent) ? parent : node;
        const owner = reference.parent;
        if (!ts.isImportSpecifier(parent) && !(ts.isNewExpression(owner) && owner.expression === reference) && !(ts.isTypeReferenceNode(owner) && owner.typeName === reference) && !ts.isExpressionWithTypeArguments(owner)) {
          requirements.push(`${path.relative(root, file)}: WebGLRenderer is used outside construction or a type annotation; migrate this usage explicitly.`);
        }
      }
      if (ts.isExpressionWithTypeArguments(node) && isRendererSymbol(checker.getSymbolAtLocation(node.expression))) requirements.push(`${path.relative(root, file)}: WebGLRenderer inheritance requires an explicit native renderer migration.`);
      ts.forEachChild(node, inspect);
    }
    inspect(source);
    const changesFrame = [...frames.functions, ...frames.calls, ...frames.schedules.keys()].some(node => node.getSourceFile() === source);
    if (!constructors.size && !renders.size && !typeReferences.size && !changesFrame) continue;
    let alias = 'SceneopsWebGPURenderer';
    while (names.has(alias)) alias += '_';
    const result = ts.transform(source, [context => {
      const f = context.factory;
      const visit: ts.Visitor = node => {
        if (frames.functions.has(node as never)) return updateAsyncFunction(ts.visitEachChild(node, visit, context) as Parameters<typeof updateAsyncFunction>[0], f);
        if (ts.isBlock(node) && frames.schedules.has(node.parent as never)) {
          const last = frames.schedules.get(node.parent as never)!;
          const schedule = last.expression as ts.CallExpression;
          let callbackName = 'sceneopsNextFrame';
          while (names.has(callbackName)) callbackName += '_';
          names.add(callbackName);
          const callback = f.createVariableStatement(undefined, f.createVariableDeclarationList([f.createVariableDeclaration(callbackName, undefined, undefined, ts.visitNode(schedule.arguments[0], visit) as ts.Expression)], ts.NodeFlags.Const));
          const statements = node.statements.map(statement => statement === last ? callback : ts.visitNode(statement, visit) as ts.Statement);
          statements.push(f.createExpressionStatement(f.updateCallExpression(schedule, schedule.expression, schedule.typeArguments, [f.createIdentifier(callbackName)])));
          return f.updateBlock(node, statements);
        }
        if (frames.calls.has(node as ts.CallExpression)) {
          const next = ts.visitEachChild(node, visit, context) as ts.CallExpression;
          return ts.isAwaitExpression(node.parent) ? next : f.createAwaitExpression(next);
        }
        if (constructors.has(node as ts.NewExpression)) {
          const original = node as ts.NewExpression;
          return f.updateNewExpression(original, f.createIdentifier(alias), original.typeArguments, original.arguments?.map(argument => ts.visitNode(argument, visit) as ts.Expression));
        }
        if (typeReferences.has(node as ts.TypeReferenceNode)) return f.createTypeReferenceNode(alias);
        if (renders.has(node as ts.CallExpression)) {
          const call = node as ts.CallExpression;
          const property = call.expression as ts.PropertyAccessExpression;
          const next = f.updateCallExpression(call, f.createPropertyAccessExpression(ts.visitNode(property.expression, visit) as ts.Expression, 'renderAsync'), call.typeArguments, call.arguments.map(argument => ts.visitNode(argument, visit) as ts.Expression));
          return ts.isAwaitExpression(call.parent) ? next : f.createAwaitExpression(next);
        }
        if (ts.isImportDeclaration(node) && node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) {
          const elements = node.importClause.namedBindings.elements.filter(element => !isRendererSymbol(checker.getSymbolAtLocation(element.name)));
          if (elements.length !== node.importClause.namedBindings.elements.length) {
            if (!elements.length && !node.importClause.name) return undefined;
            return f.updateImportDeclaration(node, node.modifiers, f.updateImportClause(node.importClause, node.importClause.isTypeOnly, node.importClause.name, elements.length ? f.updateNamedImports(node.importClause.namedBindings, elements) : undefined), node.moduleSpecifier, node.attributes);
          }
        }
        return ts.visitEachChild(node, visit, context);
      };
      return node => {
        const transformed = ts.visitNode(node, visit) as ts.SourceFile;
        const imported = f.createImportDeclaration(undefined, f.createImportClause(false, undefined, f.createNamedImports([f.createImportSpecifier(false, f.createIdentifier('WebGPURenderer'), f.createIdentifier(alias))])), f.createStringLiteral('three/webgpu'));
        return constructors.size || typeReferences.size ? f.updateSourceFile(transformed, [imported, ...transformed.statements]) : transformed;
      };
    }]);
    const after = ts.createPrinter().printFile(result.transformed[0] as ts.SourceFile);
    result.dispose();
    changes.push({ file, before: source.text, after });
  }
  if (!changes.length && !alreadyWebGPU) requirements.push('No typed Three.js WebGLRenderer found. Ensure game dependencies and types are installed; an existing WebGPU game needs no migration.');
  const packageFile = path.join(root, 'package.json');
  const packageStat = await lstat(packageFile);
  if (packageStat.isSymbolicLink()) throw new Error('Package manifest cannot be a symbolic link.');
  const before = await readFile(packageFile, 'utf8');
  const manifest = JSON.parse(before);
  manifest.dependencies = { ...manifest.dependencies, three: '0.185.1' };
  manifest.devDependencies = { ...manifest.devDependencies, '@types/three': '0.185.4' };
  if (manifest.devDependencies.three) manifest.devDependencies.three = '0.185.1';
  if (manifest.dependencies['@types/three']) manifest.dependencies['@types/three'] = '0.185.4';
  const after = JSON.stringify(manifest, null, 2) + '\n';
  if (JSON.stringify(JSON.parse(before)) !== JSON.stringify(manifest)) changes.push({ file: packageFile, before, after });
  const report = { supported: requirements.length === 0, changedFiles: changes.map(change => path.relative(root, change.file)), requirements, applied: false };
  if (!apply || !report.supported) return report;
  const written: Change[] = [];
  try {
    for (const change of changes) {
      if ((await lstat(change.file)).isSymbolicLink() || await readFile(change.file, 'utf8') !== change.before) throw new Error(`File changed during migration: ${change.file}`);
    }
    for (const change of changes) {
      const temporary = change.file + '.sceneops-webgpu-tmp';
      await writeFile(temporary, change.after, { flag: 'wx' });
      try { await rename(temporary, change.file); written.push(change); }
      catch (error) { await unlink(temporary); throw error; }
    }
    report.applied = true;
  } catch (error) {
    const failures: unknown[] = [];
    for (const change of written.reverse()) try { await writeFile(change.file, change.before); } catch (reason) { failures.push(reason); }
    if (failures.length) throw new AggregateError([error, ...failures], 'Migration failed and rollback needs attention.');
    throw error;
  }
  return report;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const [directory, mode] = process.argv.slice(2);
  if (!directory || (mode !== '--dry-run' && mode !== '--apply')) throw new Error('Usage: migrate-lookdev-game.ts REGISTERED_GAME_ROOT --dry-run|--apply');
  migrateLookdevGame(directory, mode === '--apply').then(report => process.stdout.write(JSON.stringify(report))).catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
}
