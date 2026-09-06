import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { environmentAssetUrl, type EnvironmentObject } from './environment-client.ts';


export function EnvironmentScenePreview({objects, selectedId, onSelect}: {
  objects: EnvironmentObject[]; selectedId: string | null; onSelect: (id: string | null) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const groupsRef = useRef(new Map<string, THREE.Group>());
  const selectionRef = useRef<THREE.BoxHelper | null>(null);
  const drawRef = useRef<() => void>(() => undefined);
  const selectedRef = useRef(selectedId);
  const [failure, setFailure] = useState('');
  useEffect(() => {
    selectedRef.current = selectedId;
    const helper = selectionRef.current;
    if (!helper) return;
    const selected = selectedId ? groupsRef.current.get(selectedId) : undefined;
    if (selected) { helper.setFromObject(selected); helper.visible = true; }
    else helper.visible = false;
    drawRef.current();
  }, [selectedId]);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    setFailure('');
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({antialias:true}); }
    catch { setFailure('当前浏览器无法创建 Three.js 场景。'); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#1b1b1b');
    const camera = new THREE.PerspectiveCamera(48, 1, .02, 2000);
    camera.position.set(12, 10, 15);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.5, -3);
    controls.enableDamping = false;
    scene.add(new THREE.HemisphereLight('#ffffff', '#242424', 2.1));
    const key = new THREE.DirectionalLight('#fff8ec', 3.4);
    key.position.set(8, 14, 7); key.castShadow = true; scene.add(key);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({color:'#222522',roughness:1}));
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
    const grid = new THREE.GridHelper(80, 80, '#484848', '#303030'); grid.position.y = .002; scene.add(grid);
    const root = new THREE.Group(); scene.add(root);
    const groups = new Map<string, THREE.Group>(); groupsRef.current = groups;
    const selection = new THREE.BoxHelper(new THREE.Object3D(), '#f1f1f1'); selection.visible = false; scene.add(selection);
    selectionRef.current = selection;
    let disposed = false;
    let visible = true;
    const draw = () => {
      if (disposed || !visible || document.hidden || !element.clientWidth || !element.clientHeight) return;
      renderer.setSize(element.clientWidth, element.clientHeight, false);
      camera.aspect = element.clientWidth / element.clientHeight; camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    };
    drawRef.current = draw;
    controls.addEventListener('change', draw);
    const loader = new GLTFLoader();
    const loaded = new Map<string, Promise<THREE.Object3D>>();
    const load = (object: EnvironmentObject) => {
      const url = environmentAssetUrl(object.source_asset_id, object.asset_version);
      let promise = loaded.get(url);
      if (!promise) {
        promise = loader.loadAsync(url).then(result => result.scene);
        loaded.set(url, promise);
      }
      return promise;
    };
    Promise.all(objects.map(async object => {
      const model = (await load(object)).clone(true);
      if (disposed) return;
      model.traverse(child => { const mesh = child as THREE.Mesh; if (mesh.isMesh) { mesh.castShadow = true; mesh.receiveShadow = true; } });
      const group = new THREE.Group();
      group.userData.sceneObjectId = object.id;
      group.position.set(...object.transform.position_m);
      group.rotation.y = THREE.MathUtils.degToRad(object.transform.rotation_y_deg);
      group.scale.setScalar(object.transform.scale);
      group.add(model); root.add(group); groups.set(object.id, group);
    })).then(() => {
      if (disposed) return;
      const bounds = new THREE.Box3().setFromObject(root);
      if (!bounds.isEmpty()) {
        const center = bounds.getCenter(new THREE.Vector3());
        const size = bounds.getSize(new THREE.Vector3());
        const radius = Math.max(size.x, size.y, size.z, 4);
        controls.target.copy(center);
        camera.position.copy(center).add(new THREE.Vector3(radius * 1.25, radius, radius * 1.4));
        controls.update();
      }
      const selected = selectedRef.current ? groups.get(selectedRef.current) : undefined;
      if (selected) { selection.setFromObject(selected); selection.visible = true; }
      draw();
    }).catch(() => { if (!disposed) setFailure('场景中的 GLB 读取失败，请检查资产版本。'); });
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const click = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects([...groups.values()], true)[0]?.object;
      let current: THREE.Object3D | null | undefined = hit;
      while (current && !current.userData.sceneObjectId) current = current.parent;
      onSelect(current?.userData.sceneObjectId ? String(current.userData.sceneObjectId) : null);
    };
    renderer.domElement.addEventListener('pointerup', click);
    const resize = new ResizeObserver(draw); resize.observe(element);
    const intersection = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? true; draw(); });
    intersection.observe(element);
    document.addEventListener('visibilitychange', draw);
    controls.update(); draw();
    return () => {
      disposed = true;
      resize.disconnect(); intersection.disconnect(); controls.removeEventListener('change', draw);
      renderer.domElement.removeEventListener('pointerup', click);
      document.removeEventListener('visibilitychange', draw); controls.dispose();
      root.traverse(object => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
        for (const material of materials) material.dispose();
      });
      ground.geometry.dispose(); (ground.material as THREE.Material).dispose();
      grid.geometry.dispose(); (grid.material as THREE.Material).dispose();
      selection.geometry.dispose(); (selection.material as THREE.Material).dispose();
      renderer.dispose(); renderer.domElement.remove();
      groupsRef.current = new Map(); selectionRef.current = null; drawRef.current = () => undefined;
    };
  }, [objects, onSelect]);
  return <div className="environment-scene-preview" ref={host} aria-label="Three.js 环境场景预览">
    {failure && <p role="alert">{failure}</p>}
    {!failure && objects.length === 0 && <span>场景为空 · 从资产库加入模型，或在左侧让 AI 搭建</span>}
  </div>;
}
