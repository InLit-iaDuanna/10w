import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

/** Read the exact registered artifact; playback never writes back a posed geometry. */
export function AssetAnimationPreview({url,suspended=false}:{url:string;suspended?:boolean}) {
 const host=useRef<HTMLDivElement>(null);const mixer=useRef<THREE.AnimationMixer|null>(null);
 const clips=useRef<THREE.AnimationClip[]>([]);const hidden=useRef(suspended);hidden.current=suspended;
 const [names,setNames]=useState<string[]>([]);const [selected,setSelected]=useState('');const [error,setError]=useState('');
 useEffect(()=>{
  let stopped=false;let root:THREE.Object3D|undefined;let renderer:THREE.WebGLRenderer|undefined;let controls:OrbitControls|undefined;let observer:ResizeObserver|undefined;
  const container=host.current!;setError('');setNames([]);setSelected('');
  void (async()=>{
   const gltf=await new GLTFLoader().loadAsync(url);root=gltf.scene;
   if(stopped){disposeModel(root);return;}
   clips.current=gltf.animations;setNames(gltf.animations.map(clip=>clip.name));
   mixer.current=new THREE.AnimationMixer(root);
   const scene=new THREE.Scene();scene.background=new THREE.Color('#20242a');scene.add(root);
   scene.add(new THREE.HemisphereLight('#ffffff','#555566',2));
   const light=new THREE.DirectionalLight('#ffffff',3);light.position.set(3,5,4);scene.add(light);
   const bounds=new THREE.Box3().setFromObject(root),center=bounds.getCenter(new THREE.Vector3());
   const size=bounds.getSize(new THREE.Vector3()).length();
   if(!Number.isFinite(size)||size<=0)throw new Error('模型没有可预览的几何范围。');
   const camera=new THREE.PerspectiveCamera(40,1,size/1000,size*100);
   camera.position.copy(center).add(new THREE.Vector3(size*.8,size*.4,size));
   renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.toneMapping=THREE.ACESFilmicToneMapping;
   renderer.domElement.setAttribute('aria-label','已登记模型的真实动画预览');container.appendChild(renderer.domElement);
   controls=new OrbitControls(camera,renderer.domElement);controls.target.copy(center);controls.update();
   const resize=()=>{const width=Math.max(container.clientWidth,1);renderer!.setSize(width,300);camera.aspect=width/300;camera.updateProjectionMatrix();};resize();observer=new ResizeObserver(resize);observer.observe(container);
   let previous=performance.now();renderer.setAnimationLoop(time=>{const dt=Math.min((time-previous)/1000,.1);previous=time;if(stopped||hidden.current)return;mixer.current?.update(dt);controls!.update();renderer!.render(scene,camera);});
  })().catch(e=>{if(!stopped)setError(e instanceof Error?e.message:String(e));});
  return()=>{stopped=true;observer?.disconnect();renderer?.setAnimationLoop(null);mixer.current?.stopAllAction();if(root){mixer.current?.uncacheRoot(root);disposeModel(root);}mixer.current=null;controls?.dispose();renderer?.dispose();renderer?.domElement.remove();};
 },[url]);
 return <section><p>实际资产 · 几何与动画预览。动画播放不改变保存源；Shader 效果在材质工具检查。</p><label>片段<select value={selected} onChange={e=>{setSelected(e.target.value);mixer.current?.stopAllAction();const clip=clips.current[Number(e.target.value)];if(e.target.value!==''&&clip)mixer.current?.clipAction(clip).play();}}><option value="">静止模型</option>{names.map((name,index)=><option key={index} value={index}>{name}</option>)}</select></label>{!names.length&&!error&&<p>此模型未包含动画片段。</p>}<div ref={host} style={{height:300,width:'100%'}}/>{error&&<p role="alert">模型动画读取失败：{error}</p>}</section>;
}
function disposeModel(root:THREE.Object3D){
 const materials=new Set<THREE.Material>(),textures=new Set<THREE.Texture>();
 root.traverse(node=>{if(node instanceof THREE.Mesh){node.geometry.dispose();(Array.isArray(node.material)?node.material:[node.material]).forEach(m=>materials.add(m));}});
 materials.forEach(material=>{Object.values(material).forEach(value=>{if(value instanceof THREE.Texture)textures.add(value);});material.dispose();});textures.forEach(texture=>texture.dispose());
}
