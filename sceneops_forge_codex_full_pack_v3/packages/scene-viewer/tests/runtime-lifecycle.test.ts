import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ContinuousViewportBudget,
  ResourceCacheError,
  SceneOverlayError,
  SceneOverlayRegistry,
  SharedResourceCache,
  ViewportLifecycleController,
  ViewportLifecycleError,
  type ViewportPixelSize,
  type ViewportRenderMode,
  type ViewportRuntimePort,
} from '../src/index.ts';

test('registers deterministic overlay payloads in stable order and exposes availability', () => {
  interface Context { readonly navMeshReady: boolean }
  interface Payload { readonly color: string }
  const registry = new SceneOverlayRegistry<Context, Payload>();
  const unregisterNavMesh = registry.register({
    id: 'scene.navmesh',
    label: 'NavMesh',
    layer: 'geometry',
    order: 20,
    isAvailable: (context) => context.navMeshReady,
    createPayload: () => ({ color: '#58c8c5' }),
  });
  registry.register({
    id: 'scene.object-ids',
    label: 'Object IDs',
    layer: 'metadata',
    order: 10,
    isAvailable: () => true,
    createPayload: () => ({ color: '#eca85b' }),
  });

  assert.deepEqual(
    registry.list({ navMeshReady: false }).map((item) => [item.id, item.available]),
    [['scene.object-ids', true], ['scene.navmesh', false]],
  );
  assert.deepEqual(
    registry.resolve('scene.navmesh', { navMeshReady: true }).payload,
    { color: '#58c8c5' },
  );
  assert.throws(
    () => registry.resolve('scene.navmesh', { navMeshReady: false }),
    (error) => error instanceof SceneOverlayError && error.code === 'OVERLAY_UNAVAILABLE',
  );
  assert.throws(
    () => registry.register({
      id: 'scene.navmesh',
      label: 'Duplicate',
      layer: 'geometry',
      order: 0,
      isAvailable: () => true,
      createPayload: () => ({ color: '#ffffff' }),
    }),
    (error) => error instanceof SceneOverlayError && error.code === 'DUPLICATE_OVERLAY',
  );
  unregisterNavMesh();
  assert.deepEqual(registry.list({ navMeshReady: true }).map((item) => item.id), ['scene.object-ids']);
});

test('resizes in device pixels and always suspends hidden or inactive viewports', () => {
  const runtime = viewportPort();
  const lifecycle = new ViewportLifecycleController('world-main', runtime.port);

  lifecycle.resize(640, 360, 2);
  assert.deepEqual(runtime.sizes, [{
    cssWidth: 640,
    cssHeight: 360,
    devicePixelRatio: 2,
    pixelWidth: 1280,
    pixelHeight: 720,
  }]);
  assert.equal(lifecycle.snapshot().renderMode, 'suspended');
  assert.equal(lifecycle.invalidate(), false);

  lifecycle.setVisibility(true, true);
  assert.equal(lifecycle.snapshot().renderMode, 'on-demand');
  assert.equal(lifecycle.invalidate(), true);
  lifecycle.requestContinuousRendering(true);
  lifecycle.setVisibility(false, true);
  assert.deepEqual(runtime.modes, ['suspended', 'on-demand', 'continuous', 'suspended']);
  assert.equal(lifecycle.invalidate(), false);

  lifecycle.setVisibility(true, false);
  assert.equal(lifecycle.snapshot().renderMode, 'suspended');
});

test('rejects invalid viewport dimensions without notifying the renderer', () => {
  const runtime = viewportPort();
  const lifecycle = new ViewportLifecycleController('world-main', runtime.port);
  assert.throws(
    () => lifecycle.resize(-1, 100, 1),
    (error) => error instanceof ViewportLifecycleError && error.code === 'INVALID_VIEWPORT_SIZE',
  );
  assert.equal(runtime.sizes.length, 0);
});

test('limits continuous rendering to two visible viewports and promotes a waiting comparison', () => {
  const budget = new ContinuousViewportBudget();
  const first = viewportPort();
  const second = viewportPort();
  const third = viewportPort();
  const controllers = [first, second, third].map(
    (runtime, index) => new ViewportLifecycleController(`world-${index}`, runtime.port, budget),
  );
  for (const controller of controllers) {
    controller.resize(640, 360, 1);
    controller.setVisibility(true, true);
    controller.requestContinuousRendering(true);
  }
  assert.deepEqual(controllers.map((controller) => controller.snapshot().renderMode), [
    'continuous',
    'continuous',
    'on-demand',
  ]);
  assert.deepEqual(budget.grantedViewportIds(), ['world-0', 'world-1']);

  controllers[0]?.setVisibility(false, true);
  assert.equal(controllers[2]?.snapshot().renderMode, 'continuous');
  assert.deepEqual(budget.grantedViewportIds(), ['world-1', 'world-2']);
  controllers.forEach((controller) => controller.dispose());
  controllers[0]?.dispose();
  assert.throws(
    () => controllers[0]?.setVisibility(true, true),
    (error) => error instanceof ViewportLifecycleError && error.code === 'VIEWPORT_DISPOSED',
  );
});

test('shares one in-flight resource load across viewports and disposes after explicit eviction', async () => {
  const disposed: string[] = [];
  let loadCount = 0;
  const cache = new SharedResourceCache<string, { readonly id: string }>(
    (value) => disposed.push(value.id),
  );
  const loader = async (key: string) => {
    loadCount += 1;
    await Promise.resolve();
    return { id: key };
  };

  const [left, right] = await Promise.all([
    cache.acquire('asset-home.glb', loader),
    cache.acquire('asset-home.glb', loader),
  ]);
  assert.equal(loadCount, 1);
  assert.strictEqual(left.value, right.value);
  assert.deepEqual(cache.inspect(), [{
    key: 'asset-home.glb',
    state: 'ready',
    referenceCount: 2,
  }]);
  assert.throws(
    () => cache.evict('asset-home.glb'),
    (error) => error instanceof ResourceCacheError && error.code === 'RESOURCE_IN_USE',
  );

  left.release();
  left.release();
  right.release();
  assert.equal(cache.evictUnused(), 1);
  assert.deepEqual(disposed, ['asset-home.glb']);
  cache.close();
  await assert.rejects(
    cache.acquire('other.glb', loader),
    (error) => error instanceof ResourceCacheError && error.code === 'CACHE_CLOSED',
  );
});

test('removes failed resource loads so a later acquisition can retry', async () => {
  const cache = new SharedResourceCache<string, { readonly id: string }>(() => undefined);
  let attempts = 0;
  const loader = async (key: string) => {
    attempts += 1;
    if (attempts === 1) throw new Error('fixture load failed');
    return { id: key };
  };

  await assert.rejects(cache.acquire('retry.glb', loader), /fixture load failed/);
  assert.deepEqual(cache.inspect(), []);
  const lease = await cache.acquire('retry.glb', loader);
  assert.equal(attempts, 2);
  lease.release();
  cache.close();
});

function viewportPort(): {
  readonly port: ViewportRuntimePort;
  readonly sizes: ViewportPixelSize[];
  readonly modes: ViewportRenderMode[];
} {
  const sizes: ViewportPixelSize[] = [];
  const modes: ViewportRenderMode[] = [];
  return {
    port: {
      resizeViewport: (size) => sizes.push(size),
      setRenderMode: (mode) => modes.push(mode),
      invalidateFrame: () => undefined,
    },
    sizes,
    modes,
  };
}
