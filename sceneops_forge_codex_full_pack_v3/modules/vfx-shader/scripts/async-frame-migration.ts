import ts from 'typescript';

type BodyFunction = ts.FunctionDeclaration | ts.FunctionExpression | ts.ArrowFunction | ts.MethodDeclaration;
export interface AsyncFramePlan {
  functions: Set<BodyFunction>;
  calls: Set<ts.CallExpression>;
  schedules: Map<BodyFunction, ts.ExpressionStatement>;
  requirements: string[];
}
const bodyFunction = (node: ts.Node): node is BodyFunction => ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) || ts.isArrowFunction(node) || ts.isMethodDeclaration(node);
const isAsync = (node: BodyFunction) => !!ts.getModifiers(node)?.some(modifier => modifier.kind === ts.SyntaxKind.AsyncKeyword);

/** Closed-world void-call propagation, ending only at existing async code or the DOM RAF boundary. */
export function planAsyncFrames(sources: ts.SourceFile[], checker: ts.TypeChecker, renders: Set<ts.CallExpression>): AsyncFramePlan {
  const plan: AsyncFramePlan = { functions: new Set(), calls: new Set(), schedules: new Map(), requirements: [] };
  const nodes: ts.Node[] = [];
  const affected = new Set<BodyFunction>();
  const queue: BodyFunction[] = [];
  const symbol = (node: ts.Node): ts.Symbol | undefined => {
    let result = checker.getSymbolAtLocation(node);
    if (result && result.flags & ts.SymbolFlags.Alias) result = checker.getAliasedSymbol(result);
    return result;
  };
  const domRaf = (call: ts.CallExpression) => {
    const value = symbol(call.expression);
    return value?.name === 'requestAnimationFrame' && value.declarations?.some(declaration => declaration.getSourceFile().fileName.replaceAll('\\', '/').endsWith('/lib.dom.d.ts'));
  };
  function collect(node: ts.Node) { nodes.push(node); ts.forEachChild(node, collect); }
  sources.forEach(collect);
  function enclosing(node: ts.Node): ts.Node {
    let current = node.parent;
    while (!ts.isSourceFile(current) && !ts.isFunctionLike(current) && !ts.isPropertyDeclaration(current) && !ts.isClassStaticBlockDeclaration(current)) current = current.parent;
    return current;
  }
  function fail(node: ts.Node, reason: string) {
    const source = node.getSourceFile();
    plan.requirements.push(`${source.fileName}:${source.getLineAndCharacterOfPosition(node.getStart()).line + 1}: ${reason}`);
  }
  function affect(node: ts.Node) {
    if (ts.isSourceFile(node)) {
      if (!ts.isExternalModule(node)) fail(node, 'Await requires an ES module.');
      return;
    }
    if (!bodyFunction(node) || !node.body) { fail(node, 'Synchronous constructor/accessor cannot await rendering.'); return; }
    if (affected.has(node)) return;
    affected.add(node);
    queue.push(node);
    if (isAsync(node)) return;
    const signature = checker.getSignatureFromDeclaration(node);
    if (!signature || !(checker.getReturnTypeOfSignature(signature).flags & ts.TypeFlags.Void)) {
      fail(node, 'Only void callers can be promoted; this function returns a synchronous value.'); return;
    }
    if (ts.getModifiers(node)?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword || modifier.kind === ts.SyntaxKind.DefaultKeyword)) {
      fail(node, 'Exported synchronous function requires an explicit public API migration.'); return;
    }
    if (ts.isMethodDeclaration(node) && ts.isClassDeclaration(node.parent) && ts.getModifiers(node.parent)?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword) && !ts.getModifiers(node)?.some(modifier => modifier.kind === ts.SyntaxKind.PrivateKeyword)) {
      fail(node, 'Exported public synchronous method requires an explicit public API migration.'); return;
    }
    plan.functions.add(node);
  }
  function affectCall(call: ts.CallExpression) {
    const owner = enclosing(call);
    if (bodyFunction(owner) && owner.body && (call.pos < owner.body.pos || call.end > owner.body.end)) {
      fail(call, 'Parameter initializers cannot become asynchronous.'); return;
    }
    affect(owner);
  }
  for (const call of renders) affectCall(call);
  for (let index = 0; index < queue.length; index++) {
    const fn = queue[index];
    const wasAsync = isAsync(fn);
    const identifiers = new Set<ts.Symbol>();
    if (fn.name) { const value = symbol(fn.name); if (value) identifiers.add(value); }
    if ((ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) && ts.isVariableDeclaration(fn.parent)) {
      const value = symbol(fn.parent.name); if (value) identifiers.add(value);
    }
    const references: ts.Node[] = [];
    for (const node of nodes) {
      if (!ts.isIdentifier(node) || !identifiers.has(symbol(node)!)) continue;
      if (node === fn.name || (ts.isVariableDeclaration(node.parent) && node.parent.initializer === fn)) continue;
      references.push(ts.isPropertyAccessExpression(node.parent) && node.parent.name === node ? node.parent : node);
    }
    if (!identifiers.size) references.push(fn);
    for (const reference of references) {
      const parent = reference.parent;
      if (ts.isCallExpression(parent) && domRaf(parent) && parent.arguments[0] === reference) continue;
      if (ts.isCallExpression(parent) && parent.expression === reference) {
        if (wasAsync) continue;
        const owner = parent.parent;
        const discarded = ts.isExpressionStatement(owner) || ts.isAwaitExpression(owner) || ts.isVoidExpression(owner) || ts.isReturnStatement(owner) || (ts.isArrowFunction(owner) && owner.body === parent);
        if (!discarded) { fail(parent, 'The synchronous call result is consumed; migrate its semantics explicitly.'); continue; }
        plan.calls.add(parent);
        affectCall(parent);
        continue;
      }
      fail(reference, 'Callback escapes the awaited call graph. Only DOM requestAnimationFrame is a supported asynchronous scheduling boundary; setAnimationLoop is not serialized.');
    }
  }
  for (const fn of affected) {
    if (!fn.body || !ts.isBlock(fn.body)) continue;
    const schedules = nodes.filter((node): node is ts.CallExpression => ts.isCallExpression(node) && !!domRaf(node) && enclosing(node) === fn);
    if (!schedules.length) continue;
    if (schedules.length > 1) { fail(fn, 'Multiple RAF schedules in one affected frame require explicit scheduling.'); continue; }
    const schedule = schedules[0];
    const statement = schedule.parent;
    if (!ts.isExpressionStatement(statement) || statement.parent !== fn.body) { fail(schedule, 'RAF handle assignment or conditional scheduling needs an explicit async migration.'); continue; }
    if (fn.body.statements.at(-1) === statement) continue;
    if (nodes.some(node => ts.isReturnStatement(node) && enclosing(node) === fn)) { fail(fn, 'Early returns prevent safely moving RAF scheduling after awaited rendering.'); continue; }
    const callback = schedule.arguments[0];
    if (!callback || schedule.arguments.length !== 1 || !ts.isIdentifier(schedule.expression)) { fail(schedule, 'Only a direct DOM RAF call with one callback can be rescheduled.'); continue; }
    plan.schedules.set(fn, statement);
  }
  return plan;
}

export function updateAsyncFunction(node: BodyFunction, factory: ts.NodeFactory): BodyFunction {
  const modifiers = [...(ts.getModifiers(node) ?? []), factory.createModifier(ts.SyntaxKind.AsyncKeyword)];
  const type = node.type ? factory.createTypeReferenceNode('Promise', [node.type]) : undefined;
  if (ts.isFunctionDeclaration(node)) return factory.updateFunctionDeclaration(node, modifiers, node.asteriskToken, node.name, node.typeParameters, node.parameters, type, node.body);
  if (ts.isFunctionExpression(node)) return factory.updateFunctionExpression(node, modifiers, node.asteriskToken, node.name, node.typeParameters, node.parameters, type, node.body);
  if (ts.isArrowFunction(node)) return factory.updateArrowFunction(node, modifiers, node.typeParameters, node.parameters, type, node.equalsGreaterThanToken, node.body);
  return factory.updateMethodDeclaration(node, modifiers, node.asteriskToken, node.name, node.questionToken, node.typeParameters, node.parameters, type, node.body);
}
