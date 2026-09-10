import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import * as THREE from 'three/webgpu';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RectAreaLightTexturesLib } from 'three/addons/lights/RectAreaLightTexturesLib.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { LookdevProject, Selection } from './core/lookdev';
import { buildRenderScene, exportGlb, type RenderScene } from './core/render-scene';
import { appendCleanupFailure, validateRenderCandidate, withRenderLock } from './core/render-transaction';

export interface ViewportStats { fps: number; triangles: number; device: string }
export interface ThreeViewportHandle {
  apply(project: LookdevProject, source?: THREE.Object3D, resetView?: boolean, signal?: AbortSignal): Promise<void>;
  compare(project: LookdevProject | null): Promise<void>;
  screenshot(): Promise<Blob>;
  exportGlb(): Promise<ArrayBuffer>;
  getView(): LookdevProject['view'];
  frame(): void;
}
export interface LookdevViewportProps {
  suspended?: boolean;
  initialProject: LookdevProject; initialContent: THREE.Object3D;
  onSelect: (selection: Selection) => void; onStats: (stats: ViewportStats) => void;
  onReady: () => void; onError: (message: string) => void;
}
type Runtime = {
  renderer: THREE.WebGPURenderer; camera: THREE.PerspectiveCamera; controls: OrbitControls;
  source: THREE.Object3D; project: LookdevProject; active: RenderScene; previous: RenderScene | null;
  environment: THREE.Texture; paused: boolean; unavailable: string | null;
};
export const ThreeViewport = forwardRef<ThreeViewportHandle, LookdevViewportProps>(function ThreeViewport(props, ref) {
  const host = useRef<HTMLDivElement>(null);
  const callbacks = useRef(props);
  useEffect(() => { callbacks.current = props; });
  const runtime = useRef<Runtime | null>(null);
  const [error, setError] = useState('');

  function requireRuntime(r: Runtime | null): Runtime {
    if (!r) throw new Error('三维视口尚未就绪。');
    if (r.unavailable) throw new Error(r.unavailable);
    return r;
  }

  function markUnavailable(r: Runtime, reason: unknown) {
    const detail = reason instanceof Error ? reason.message : String(reason);
    const message = `WebGPU 设备已不可用：${detail || '设备连接已中断'}。请重新载入页面以重建设备。`;
    r.unavailable = message;
    r.paused = false;
    setError(message);
    callbacks.current.onError(message);
  }

  function draw(r: Runtime) {
    const { renderer, camera } = r;
    const size = renderer.getSize(new THREE.Vector2());
    if (r.previous) {
      camera.aspect = size.x / 2 / size.y; camera.updateProjectionMatrix();
      renderer.setScissorTest(true);
      renderer.setViewport(0, 0, size.x / 2, size.y);
      renderer.setScissor(0, 0, size.x / 2, size.y);
      renderer.render(r.previous.scene, camera);
      renderer.setViewport(size.x / 2, 0, size.x / 2, size.y);
      renderer.setScissor(size.x / 2, 0, size.x / 2, size.y);
      renderer.render(r.active.scene, camera);
      renderer.setScissorTest(false);
    } else {
      camera.aspect = size.x / size.y; camera.updateProjectionMatrix();
      renderer.setViewport(0, 0, size.x, size.y);
      renderer.render(r.active.scene, camera);
    }
  }

  useImperativeHandle(ref, () => ({
    async apply(project, source, resetView = false, signal) {
      const r = requireRuntime(runtime.current);
      await withRenderLock(r, '上一笔修改仍在编译中。', async () => {
        let candidate: RenderScene | null = null;
        let testTarget: THREE.RenderTarget | null = null;
        let failure: unknown;
        try {
          candidate = buildRenderScene(source ?? r.source, project, r.environment);
          const device = (r.renderer.backend as THREE.WebGPUBackend & { device: GPUDevice }).device;
          const size = r.renderer.getSize(new THREE.Vector2());
          testTarget = new THREE.RenderTarget(size.x, size.y);
          device.pushErrorScope('validation');
          await validateRenderCandidate({
            compileAndDraw: async () => {
              await r.renderer.compileAsync(candidate!.scene, r.camera);
              signal?.throwIfAborted();
              requireRuntime(r);
              r.renderer.setRenderTarget(testTarget);
              r.renderer.render(candidate!.scene, r.camera);
            },
            resetRenderTarget: () => r.renderer.setRenderTarget(null),
            popValidationError: () => device.popErrorScope(),
            disposeTarget: () => {
              const target = testTarget;
              testTarget = null;
              target?.dispose();
            },
          });
          signal?.throwIfAborted();
          requireRuntime(r);
          const old = r.active;
          r.active = candidate;
          try { draw(r); } catch (reason) { r.active = old; throw reason; }
          r.source = source ?? r.source;
          r.project = project;
          if (resetView) {
            r.camera.position.fromArray(project.view.position);
            r.controls.target.fromArray(project.view.target);
            r.controls.update();
          }
          candidate = null;
          old.dispose();
        } catch (reason) {
          failure = reason;
        } finally {
          const cleanup: unknown[] = [];
          if (testTarget) {
            const target = testTarget;
            testTarget = null;
            try { target.dispose(); } catch (reason) { cleanup.push(reason); }
          }
          if (candidate) {
            const rejected = candidate;
            candidate = null;
            try { rejected.dispose(); } catch (reason) { cleanup.push(reason); }
          }
          failure = appendCleanupFailure(failure, cleanup);
        }
        if (failure !== undefined) throw failure;
      });
    },
    async compare(project) {
      const r = requireRuntime(runtime.current);
      if (r.paused) throw new Error('三维视口正在准备。');
      if (!project) { r.previous?.dispose(); r.previous = null; return; }
      const candidate = buildRenderScene(r.source, project, r.environment);
      await withRenderLock(r, '三维视口正在准备。', async () => {
        let accepted = false;
        try {
          await r.renderer.compileAsync(candidate.scene, r.camera);
          requireRuntime(r);
          r.previous?.dispose(); r.previous = candidate; accepted = true;
        } finally {
          if (!accepted) candidate.dispose();
        }
      });
    },
    async screenshot() {
      const r = requireRuntime(runtime.current);
      draw(r);
      return new Promise<Blob>((resolve, reject) => {
        r.renderer.domElement.toBlob((blob) => blob ? resolve(blob) : reject(new Error('截图失败。')), 'image/png');
      });
    },
    async exportGlb() {
      const r = runtime.current;
      if (!r) throw new Error('三维视口尚未就绪。');
      return exportGlb(r.source, r.project);
    },
    getView() {
      const r = runtime.current;
      return r ? {
        position: r.camera.position.toArray() as [number, number, number],
        target: r.controls.target.toArray() as [number, number, number],
      } : callbacks.current.initialProject.view;
    },
    frame() {
      const r = runtime.current;
      if (!r) return;
      const bounds = new THREE.Box3().setFromObject(r.source);
      const center = bounds.getCenter(new THREE.Vector3());
      const radius = Math.max(...bounds.getSize(new THREE.Vector3()).toArray(), 0.1);
      r.camera.position.copy(center).add(new THREE.Vector3(1.35, 0.7, 1.8).multiplyScalar(radius));
      r.controls.target.copy(center); r.controls.update();
    },
  }), []);

  useEffect(() => {
    const container = host.current!;
    let disposed = false;
    let renderer: THREE.WebGPURenderer | undefined;
    let observer: ResizeObserver | undefined;
    let pmrem: THREE.PMREMGenerator | undefined;
    let environmentTarget: THREE.RenderTarget | undefined;
    async function init() {
      try {
        if (!navigator.gpu) throw new Error('需要支持 WebGPU 的桌面浏览器。请用新版 Chrome / Edge / Safari 打开。');
        const adapter = await navigator.gpu.requestAdapter();
        if (!adapter) throw new Error('浏览器未提供 WebGPU 设备，请启用硬件加速。');
        renderer = new THREE.WebGPURenderer({ antialias: true });
        await renderer.init();
        if (disposed) { renderer.dispose(); return; }
        if (!(renderer.backend as THREE.WebGPUBackend).isWebGPUBackend) throw new Error('WebGPU 初始化失败，无法启动本工作台。');
        THREE.RectAreaLightNode.setLTC(RectAreaLightTexturesLib.init());
        renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.setSize(Math.max(container.clientWidth, 1), Math.max(container.clientHeight, 1));
        renderer.domElement.className = 'three-canvas';
        renderer.domElement.setAttribute('aria-label', '模型三维视口');
        container.appendChild(renderer.domElement);
        pmrem = new THREE.PMREMGenerator(renderer);
        const room = new RoomEnvironment();
        environmentTarget = pmrem.fromScene(room, 0.04);
        room.dispose();
        const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 100000);
        camera.position.fromArray(callbacks.current.initialProject.view.position);
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.target.fromArray(callbacks.current.initialProject.view.target);
        const active = buildRenderScene(callbacks.current.initialContent, callbacks.current.initialProject, environmentTarget.texture);
        await renderer.compileAsync(active.scene, camera);
        if (disposed) { active.dispose(); controls.dispose(); renderer.dispose(); environmentTarget.dispose(); pmrem.dispose(); return; }
        const r: Runtime = {
          renderer, camera, controls, active, previous: null,
          source: callbacks.current.initialContent, project: callbacks.current.initialProject,
          environment: environmentTarget.texture, paused: false, unavailable: null,
        };
        runtime.current = r;
        const gpuDevice = (renderer.backend as THREE.WebGPUBackend & { device: GPUDevice }).device;
        void gpuDevice.lost.then((info) => {
          if (!disposed && runtime.current === r) markUnavailable(r, info.message || info.reason);
        });
        observer = new ResizeObserver(() => {
          renderer!.setSize(Math.max(container.clientWidth, 1), Math.max(container.clientHeight, 1));
        });
        observer.observe(container);
        const raycaster = new THREE.Raycaster();
        let down: [number, number] = [0, 0];
        renderer.domElement.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY]; });
        renderer.domElement.addEventListener('pointerup', (e) => {
          if (Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
          const bounds = renderer!.domElement.getBoundingClientRect();
          let x = (e.clientX - bounds.left) / bounds.width;
          if (r.previous) x = (x * 2) % 1;
          raycaster.setFromCamera(new THREE.Vector2(x * 2 - 1, 1 - (e.clientY - bounds.top) / bounds.height * 2), camera);
          const hit = raycaster.intersectObject(r.active.content, true)[0];
          if (hit?.object.userData.lookdevObjectId) callbacks.current.onSelect({
            objectId: hit.object.userData.lookdevObjectId,
            slot: hit.face?.materialIndex ?? 0,
          });
        });
        let frames = 0; let time = performance.now();
        const device = adapter.info?.description || [adapter.info?.vendor, adapter.info?.architecture].filter(Boolean).join(' ') || 'WebGPU';
        void renderer.setAnimationLoop(() => {
          if (r.paused || r.unavailable || callbacks.current.suspended) return;
          controls.update();
          try { draw(r); } catch (reason) {
            markUnavailable(r, reason);
          }
          frames++;
          const now = performance.now();
          if (now - time >= 1000) {
            callbacks.current.onStats({ fps: Math.round(frames * 1000 / (now - time)), triangles: renderer!.info.render.triangles, device });
            frames = 0; time = now;
          }
        });
        callbacks.current.onReady();
      } catch (reason) {
        const message = reason instanceof Error ? reason.message : String(reason);
        if (!disposed) { setError(message); callbacks.current.onError(message); }
      }
    }
    void init();
    return () => {
      disposed = true; observer?.disconnect();
      void renderer?.setAnimationLoop(null);
      runtime.current?.controls.dispose();
      runtime.current?.active.dispose(); runtime.current?.previous?.dispose();
      environmentTarget?.dispose(); pmrem?.dispose();
      renderer?.dispose(); renderer?.domElement.remove(); runtime.current = null;
    };
  }, []);
  return <div ref={host} className="three-host">{error && <div className="viewport-error"><strong>三维预览不可用</strong><p>{error}</p></div>}</div>;
});

export const LookdevViewport = ThreeViewport;
