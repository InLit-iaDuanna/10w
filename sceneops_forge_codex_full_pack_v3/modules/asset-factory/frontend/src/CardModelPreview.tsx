import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

export type CardModelPreviewHandle = {
  zoom(factor:number): void;
  rotate(degrees:number): void;
  view(direction:'front'|'back'|'left'|'right'): void;
  reset(): void;
};

type PreviewRuntime = {camera:THREE.PerspectiveCamera;controls:OrbitControls;center:THREE.Vector3;
  radius:number;homeOffset:THREE.Vector3;draw:()=>void};

export const CardModelPreview = forwardRef<CardModelPreviewHandle, {url:string;label:string}>(function CardModelPreview({ url, label }, ref) {
  const host = useRef<HTMLDivElement>(null);
  const runtime = useRef<PreviewRuntime|null>(null);
  const [failure, setFailure] = useState('');
  useImperativeHandle(ref, () => ({
    zoom(factor) {
      const current = runtime.current;
      if (!current) return;
      const offset = current.camera.position.clone().sub(current.controls.target);
      const distance = Math.min(current.radius * 20, Math.max(current.radius * .18, offset.length() * factor));
      current.camera.position.copy(current.controls.target).add(offset.setLength(distance));
      current.camera.updateProjectionMatrix(); current.controls.update(); current.draw();
    },
    rotate(degrees) {
      const current = runtime.current;
      if (!current) return;
      const offset = current.camera.position.clone().sub(current.controls.target)
        .applyAxisAngle(new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(degrees));
      current.camera.position.copy(current.controls.target).add(offset);
      current.controls.update(); current.draw();
    },
    view(direction) {
      const current = runtime.current;
      if (!current) return;
      const distance = Math.max(current.camera.position.distanceTo(current.controls.target), current.radius * 2.2);
      const vectors = {front:new THREE.Vector3(0,.15,1),back:new THREE.Vector3(0,.15,-1),
        left:new THREE.Vector3(-1,.15,0),right:new THREE.Vector3(1,.15,0)};
      current.controls.target.copy(current.center);
      current.camera.position.copy(current.center).add(vectors[direction].normalize().multiplyScalar(distance));
      current.controls.update(); current.draw();
    },
    reset() {
      const current = runtime.current;
      if (!current) return;
      current.controls.target.copy(current.center);
      current.camera.position.copy(current.center).add(current.homeOffset);
      current.controls.update(); current.draw();
    },
  }), []);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    setFailure('');
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({antialias:true, alpha:false}); }
    catch { setFailure('当前浏览器无法创建 3D 预览；模型文件仍可下载。'); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#1f1f1f');
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    scene.add(new THREE.HemisphereLight('#ffffff', '#303030', 2.4));
    const key = new THREE.DirectionalLight('#ffffff', 3.2); key.position.set(4, 7, 5); scene.add(key);
    const grid = new THREE.GridHelper(10, 20, '#555555', '#333333'); scene.add(grid);
    let model: THREE.Object3D | undefined;
    let visible = true;
    const draw = () => {
      if (!visible || document.hidden || !element.clientWidth || !element.clientHeight) return;
      renderer.setSize(element.clientWidth, element.clientHeight, false);
      camera.aspect = element.clientWidth / element.clientHeight; camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    };
    controls.addEventListener('change', draw);
    const loader = new GLTFLoader();
    loader.load(url, gltf => {
      model = gltf.scene; scene.add(model);
      const box = new THREE.Box3().setFromObject(model);
      if (box.isEmpty()) { setFailure('模型没有可预览的几何体。'); draw(); return; }
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const radius = Math.max(size.x, size.y, size.z, .1);
      controls.target.copy(center);
      const homeOffset = new THREE.Vector3(radius * 1.35, radius * .95, radius * 1.35);
      camera.position.copy(center).add(homeOffset);
      camera.near = Math.max(radius / 1000, .001); camera.far = Math.max(radius * 100, 100);
      camera.updateProjectionMatrix(); controls.update();
      runtime.current = {camera,controls,center,radius,homeOffset,draw}; draw();
    }, undefined, () => setFailure('GLB 预览读取失败；请查看资产错误或下载文件检查。'));
    const resize = new ResizeObserver(draw); resize.observe(element);
    const intersection = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? true; draw(); });
    intersection.observe(element);
    document.addEventListener('visibilitychange', draw);
    draw();
    return () => {
      runtime.current = null;
      resize.disconnect(); intersection.disconnect(); controls.removeEventListener('change', draw);
      document.removeEventListener('visibilitychange', draw); controls.dispose();
      if (model) model.traverse(object => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose?.();
        const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
        for (const material of materials) { for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose(); material.dispose(); }
      });
      grid.geometry.dispose(); (grid.material as THREE.Material).dispose(); renderer.dispose(); renderer.domElement.remove();
    };
  }, [url]);
  return <div className="card-model-preview" ref={host} aria-label={`${label} 3D 预览`}>{failure && <p role="alert">{failure}</p>}</div>;
});
