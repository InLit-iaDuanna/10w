export type RenderLock = { paused: boolean };

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function combinedFailure(primary: unknown, cleanup: unknown[]): unknown {
  if (primary === undefined) {
    if (cleanup.length === 0) return undefined;
    if (cleanup.length === 1) return cleanup[0];
    return new Error(cleanup.map(message).join('；'));
  }
  if (cleanup.length === 0) return primary;
  return new Error(`${message(primary)}；清理也失败：${cleanup.map(message).join('；')}`);
}

export async function withRenderLock<T>(lock: RenderLock, busyMessage: string, operation: () => Promise<T>): Promise<T> {
  if (lock.paused) throw new Error(busyMessage);
  lock.paused = true;
  try {
    return await operation();
  } finally {
    lock.paused = false;
  }
}

export async function validateRenderCandidate(steps: {
  compileAndDraw(): Promise<void>;
  resetRenderTarget(): void;
  popValidationError(): Promise<{ message: string } | null>;
  disposeTarget(): void;
}): Promise<void> {
  let primary: unknown;
  const cleanup: unknown[] = [];
  let validationError: { message: string } | null = null;
  try {
    await steps.compileAndDraw();
  } catch (error) {
    primary = error;
  }
  try {
    steps.resetRenderTarget();
  } catch (error) {
    cleanup.push(error);
  }
  try {
    validationError = await steps.popValidationError();
  } catch (error) {
    cleanup.push(error);
  }
  try {
    steps.disposeTarget();
  } catch (error) {
    cleanup.push(error);
  }
  if (validationError) {
    const shaderError = new Error('着色器编译失败：' + validationError.message);
    primary = primary === undefined ? shaderError : new Error(`${message(primary)}；${shaderError.message}`);
  }
  const failure = combinedFailure(primary, cleanup);
  if (failure !== undefined) throw failure;
}

export function appendCleanupFailure(primary: unknown, cleanup: unknown[]): unknown {
  return combinedFailure(primary, cleanup);
}
