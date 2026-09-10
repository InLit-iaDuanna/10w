import { useEffect, useRef, useState } from 'react';
export { GltfPreview } from './GltfPreview.tsx';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { SceneObjectIndex } from './scene-object-index.ts';
import type { CameraPose } from './camera.ts';
import type { Vector3 } from './spatial.ts';
import { SceneTransformResolver } from './scene-transforms.ts';

export interface ScenePreviewObject {
  sceneopsId: string;
  size: Vector3;
  color: string;
}
export interface ScenePreviewProps {
  index: SceneObjectIndex;
  objects: readonly ScenePreviewObject[];
  paths: readonly (readonly Vector3[])[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCamera: (camera: CameraPose) => void;
  camera: CameraPose;
  cameraRevision: number;
}

/** Demand-rendered proxy geometry. Identity and transforms use the shared index. */
export function ScenePreview(props: ScenePreviewProps) {
  const host = useRef<HTMLDivElement>(null);
  const current = useRef(props);
  current.current = props;
  const controlsRef = useRef<{ select: () => void; camera: () => void } | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    const element = host.current!;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true }); }
    catch (error) { setFailure(`3D 视图不可用：${String(error)}。仍可用对象列表选择。`); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#11181c');
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.maxPolarAngle = Math.PI / 2 - 0.04;
    controls.minDistance = 3;
    controls.maxDistance = 35;
    const resolver = new SceneTransformResolver(props.index);
    const selectable: THREE.Mesh[] = [];
    const labels = new Map<string, HTMLButtonElement>();
    scene.add(new THREE.HemisphereLight('#fce3b9', '#597580', 2.5));
    const sunlight = new THREE.DirectionalLight('#ffffff', 3);
    sunlight.position.set(3, 8, 4);
    scene.add(sunlight);
    scene.add(new THREE.GridHelper(16, 16, '#47616a', '#263a43'));
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(16, 16), new THREE.MeshStandardMaterial({ color: '#1b292e', roughness: 1 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.03;
    scene.add(floor);
    props.objects.forEach(object => {
      const material = new THREE.MeshStandardMaterial({ color: object.color, roughness: 0.6, metalness: 0.15 });
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(...object.size), material);
      const record = props.index.require(object.sceneopsId);
      // Resolve parent transforms through the canonical viewer, including rotation and scale.
      const matrix = resolver.worldMatrix(object.sceneopsId);
      mesh.applyMatrix4(new THREE.Matrix4().fromArray([...matrix]));
      mesh.userData.sceneopsId = object.sceneopsId;
      scene.add(mesh);
      selectable.push(mesh);
      const label = document.createElement('button');
      label.className = 'scene-object-label';
      label.textContent = record.name;
      label.dataset.sceneopsId = object.sceneopsId;
      label.onclick = () => current.current.onSelect(object.sceneopsId);
      element.appendChild(label);
      labels.set(object.sceneopsId, label);
    });
    props.paths.forEach(path => {
      const geometry = new THREE.BufferGeometry().setFromPoints(path.map(point => new THREE.Vector3(point[0], point[1] + 0.06, point[2])));
      scene.add(new THREE.Line(geometry, new THREE.LineDashedMaterial({ color: '#79b7b7', dashSize: 0.2, gapSize: 0.12 })).computeLineDistances());
    });
    let visible = true;
    const draw = () => {
      if (!visible || document.hidden || !element.clientWidth || !element.clientHeight) return;
      const width = element.clientWidth, height = element.clientHeight;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      for (const mesh of selectable) {
        const selected = mesh.userData.sceneopsId === current.current.selectedId;
        (mesh.material as THREE.MeshStandardMaterial).emissive.set(selected ? '#376e6d' : '#000000');
        const label = labels.get(mesh.userData.sceneopsId)!;
        const point = mesh.position.clone().add(new THREE.Vector3(0, 1, 0)).project(camera);
        label.style.left = `${(point.x + 1) / 2 * width}px`;
        label.style.top = `${(1 - point.y) / 2 * height}px`;
        label.style.display = Math.abs(point.z) > 1 ? 'none' : '';
        label.setAttribute('aria-pressed', String(selected));
      }
      renderer.render(scene, camera);
      current.current.onCamera({ projection: 'perspective', position: camera.position.toArray(), target: controls.target.toArray(), up: [0, 1, 0], verticalFovRadians: camera.fov * Math.PI / 180, nearClipMeters: camera.near, farClipMeters: camera.far, coordinateSpace: 'world', axisConvention: 'right-handed-y-up', units: 'meters' });
    };
    const restoreCamera = () => {
      const pose = current.current.camera;
      camera.position.fromArray([...pose.position]);
      controls.target.fromArray([...pose.target]);
      controls.update();
      draw();
    };
    controlsRef.current = { select: draw, camera: restoreCamera };
    controls.addEventListener('change', draw);
    let pointerStart = [0, 0];
    const pointerDown = (event: PointerEvent) => { pointerStart = [event.clientX, event.clientY]; };
    const pick = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - pointerStart[0], event.clientY - pointerStart[1]) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      const ray = new THREE.Raycaster();
      ray.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera);
      const hit = ray.intersectObjects(selectable)[0];
      if (hit) current.current.onSelect(hit.object.userData.sceneopsId);
    };
    renderer.domElement.addEventListener('pointerdown', pointerDown);
    renderer.domElement.addEventListener('pointerup', pick);
    const resize = new ResizeObserver(draw);
    resize.observe(element);
    const visibility = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; draw(); });
    visibility.observe(element);
    document.addEventListener('visibilitychange', draw);
    restoreCamera();
    return () => {
      controlsRef.current = null;
      resize.disconnect(); visibility.disconnect(); controls.dispose();
      document.removeEventListener('visibilitychange', draw);
      scene.traverse(object => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach(material => material.dispose());
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
      labels.forEach(label => label.remove());
    };
  }, [props.index, props.objects, props.paths]);
  useEffect(() => { controlsRef.current?.select(); }, [props.selectedId]);
  useEffect(() => { controlsRef.current?.camera(); }, [props.cameraRevision]);
  return <div className="scene-preview" ref={host} aria-label="可交互三维场景">{failure && <p role="alert">{failure}</p>}</div>;
}
