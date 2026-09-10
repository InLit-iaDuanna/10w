import { useEffect, useId, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import './gltf-preview.css';

type Settings = {speed:number;strength:number;yaw:number;exposure:number;light:number;grid:boolean;skeleton:boolean;loop:boolean;background:string};
const defaults:Settings={speed:1,strength:1,yaw:0,exposure:1,light:3,grid:true,skeleton:false,loop:true,background:'#e8ebe7'};
const names:Record<string,string>={Idle:'待机',Walk:'走路',Run:'跑步',Wave:'挥手'};
type CameraView = {position:number[];target:number[]};
type Controls = {capture:()=>CameraView;restoreView:(value:CameraView)=>void;select:(name:string)=>void;toggle:()=>void;seek:(time:number)=>void;apply:(settings:Settings)=>void;view:(name:string)=>void};
function dispose(root:THREE.Object3D){
  const geometry=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>(),textures=new Set<THREE.Texture>();
  root.traverse(object=>{if(object instanceof THREE.Mesh){geometry.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:[object.material]){materials.add(material);for(const value of Object.values(material))if(value instanceof THREE.Texture)textures.add(value);}}});
  geometry.forEach(item=>item.dispose());textures.forEach(item=>item.dispose());materials.forEach(item=>item.dispose());
}

/** Static inspection remains demand-rendered. Studio settings update the existing viewer. */
export function GltfPreview({url,label,suspended=false,studio=false}:{url:string;label:string;suspended?:boolean;studio?:boolean}){
  const controlId=useId();
  const host=useRef<HTMLDivElement>(null),api=useRef<Controls|null>(null);
  const [status,setStatus]=useState('正在载入模型…'),[failure,setFailure]=useState('');
  const [clips,setClips]=useState<{name:string;duration:number}[]>([]),[clip,setClip]=useState('');
  const [playing,setPlaying]=useState(false),[time,setTime]=useState(0),[notice,setNotice]=useState('');
  const [settings,setSettings]=useState<Settings>({...defaults,background:studio?defaults.background:'#222b30'});
  const settingsRef=useRef(settings);settingsRef.current=settings;
  const selected=clips.find(item=>item.name===clip);
  const update=<K extends keyof Settings>(key:K,value:Settings[K])=>setSettings(current=>({...current,[key]:value}));
  useEffect(()=>{api.current?.apply(settings);},[settings]);
  useEffect(()=>{
    if(suspended)return;
    const element=host.current!;
    setStatus('正在载入模型…');setFailure('');setClips([]);setTime(0);setPlaying(false);
    let renderer:THREE.WebGLRenderer;
    try{renderer=new THREE.WebGLRenderer({antialias:true});}catch{setStatus('');setFailure('无法创建 3D 预览，请检查浏览器的图形加速设置。');return;}
    renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    element.append(renderer.domElement);
    const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.01,2000);
    const orbit=new OrbitControls(camera,renderer.domElement);orbit.enableDamping=false;
    const sun=new THREE.DirectionalLight('#fff0df',3),ambient=new THREE.HemisphereLight('#ecf3ff','#8a8076',1.8);
    sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.normalBias=.025;scene.add(sun,sun.target,ambient);
    let model:THREE.Group|null=null,mixer:THREE.AnimationMixer|null=null,action:THREE.AnimationAction|null=null;
    let grid:THREE.GridHelper|null=null,skeleton:THREE.SkeletonHelper|null=null,floor:THREE.Mesh|null=null;
    let active=true,running=false,frame:number|null=null,previous=0,lastReport=0,radius=1;
    const center=new THREE.Vector3();
    const draw=()=>{if(!active||document.hidden||!element.clientWidth||!element.clientHeight)return;renderer.render(scene,camera);};
    const resize=()=>{const width=element.clientWidth,height=element.clientHeight;if(!width||!height)return;renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();draw();};
    const tick=(now:number)=>{frame=null;if(!active||!running||document.hidden)return;
      if(previous)mixer?.update((now-previous)/1000);previous=now;draw();
      if(now-lastReport>80){setTime(action?.time??0);lastReport=now;}
      if(running)frame=requestAnimationFrame(tick);
    };
    const schedule=()=>{previous=0;if(running&&!document.hidden&&frame===null)frame=requestAnimationFrame(tick);};
    const stop=()=>{running=false;setPlaying(false);if(frame!==null)cancelAnimationFrame(frame);frame=null;};
    const visibility=()=>{if(document.hidden){if(frame!==null)cancelAnimationFrame(frame);frame=null;previous=0;}else{draw();schedule();}};
    const observer=new ResizeObserver(resize);observer.observe(element);orbit.addEventListener('change',draw);document.addEventListener('visibilitychange',visibility);
    new GLTFLoader().load(url,gltf=>{
      if(!active){dispose(gltf.scene);return;}
      model=gltf.scene;model.traverse(object=>{if(object instanceof THREE.Mesh){object.castShadow=true;object.receiveShadow=true;}});scene.add(model);
      const bounds=new THREE.Box3().setFromObject(model),size=bounds.getSize(new THREE.Vector3());bounds.getCenter(center);radius=Math.max(size.length()/2,.5);
      orbit.target.copy(center);orbit.minDistance=radius*.4;orbit.maxDistance=radius*8;camera.far=radius*40;camera.updateProjectionMatrix();
      sun.position.copy(center).add(new THREE.Vector3(-radius*2,radius*3,radius*2));sun.target.position.copy(center);
      Object.assign(sun.shadow.camera,{left:-radius*2,right:radius*2,top:radius*2,bottom:-radius*2,far:radius*12});sun.shadow.camera.updateProjectionMatrix();
      grid=new THREE.GridHelper(radius*6,24,'#747d79','#a0aaa3');grid.position.y=bounds.min.y-.008;scene.add(grid);
      floor=new THREE.Mesh(new THREE.PlaneGeometry(radius*12,radius*12),new THREE.ShadowMaterial({opacity:.17}));floor.rotation.x=-Math.PI/2;floor.position.y=bounds.min.y-.01;floor.receiveShadow=true;scene.add(floor);
      skeleton=new THREE.SkeletonHelper(model);scene.add(skeleton);
      mixer=new THREE.AnimationMixer(model);mixer.addEventListener('finished',()=>{stop();setTime(action?.getClip().duration??0);draw();});
      const apply=(value:Settings)=>{
        renderer.toneMappingExposure=value.exposure;scene.background=new THREE.Color(value.background);sun.intensity=value.light;
        model!.rotation.y=THREE.MathUtils.degToRad(value.yaw);grid!.visible=value.grid;skeleton!.visible=value.skeleton;
        if(action){action.setEffectiveTimeScale(value.speed);action.setEffectiveWeight(value.strength);action.setLoop(value.loop?THREE.LoopRepeat:THREE.LoopOnce,value.loop?Infinity:1);action.clampWhenFinished=true;mixer!.update(0);}
        draw();
      };
      const view=(name:string)=>{const direction=name==='front'?new THREE.Vector3(0,.12,1):name==='side'?new THREE.Vector3(1,.12,0):new THREE.Vector3(1,.5,1.5);
        orbit.target.copy(center);camera.position.copy(center).add(direction.normalize().multiplyScalar(radius*3.25));orbit.update();draw();};
      const select=(name:string)=>{const animation=gltf.animations.find(item=>item.name===name);if(!animation)return;
        mixer!.stopAllAction();action=mixer!.clipAction(animation).reset().play();apply(settingsRef.current);running=true;setPlaying(true);setClip(name);setTime(0);schedule();};
      api.current={apply,view,select,capture:()=>({position:camera.position.toArray(),target:orbit.target.toArray()}),restoreView:value=>{camera.position.fromArray(value.position);orbit.target.fromArray(value.target);orbit.update();draw();},toggle:()=>{if(running){action&&(action.paused=true);stop();}else if(action){if(action.time>=action.getClip().duration)action.reset();action.paused=false;running=true;setPlaying(true);schedule();}},
        seek:value=>{if(!action)return;stop();action.paused=true;action.time=value;mixer!.update(0);setTime(value);draw();}};
      setClips(gltf.animations.map(item=>({name:item.name,duration:item.duration})));
      apply(settingsRef.current);view('perspective');resize();setStatus('');
      if(gltf.animations.length)select(gltf.animations.some(item=>item.name==='Walk')?'Walk':gltf.animations[0].name);
    },undefined,()=>{if(active){setStatus('');setFailure('模型读取失败，请返回列表后重新打开。');}});
    return()=>{active=false;api.current=null;if(frame!==null)cancelAnimationFrame(frame);observer.disconnect();orbit.dispose();document.removeEventListener('visibilitychange',visibility);
      mixer?.stopAllAction();if(model){mixer?.uncacheRoot(model);dispose(model);}if(skeleton){skeleton.geometry.dispose();for(const material of Array.isArray(skeleton.material)?skeleton.material:[skeleton.material])material.dispose();}
      if(grid){grid.geometry.dispose();for(const material of Array.isArray(grid.material)?grid.material:[grid.material])material.dispose();}if(floor){floor.geometry.dispose();(floor.material as THREE.Material).dispose();}sun.shadow.map?.dispose();renderer.dispose();renderer.domElement.remove();};
  },[url,suspended]);
  const range=(key:'speed'|'strength'|'yaw'|'exposure'|'light',title:string,min:number,max:number,step:number,suffix:string)=>
    <div className="gltf-range"><span><label htmlFor={`${controlId}-${key}`}>{title}</label><output>{key==='strength'?Math.round(settings[key]*100):settings[key]}{suffix}</output></span><input id={`${controlId}-${key}`} aria-label={title} type="range" min={min} max={max} step={step} value={settings[key]} onChange={event=>update(key,Number(event.target.value))}/></div>;
  const save=()=>{try{localStorage.setItem(`sceneops-preview:${url}`,JSON.stringify({settings,camera:api.current?.capture()}));setNotice('调校已保存在此浏览器。');}catch{setNotice('无法保存，请检查浏览器存储权限。');}};
  const restore=()=>{try{const saved=localStorage.getItem(`sceneops-preview:${url}`);if(!saved){setNotice('此资产还没有保存的调校。');return;}
    const value=JSON.parse(saved);if(!value.settings||Object.keys(defaults).some(key=>typeof value.settings[key]!==typeof defaults[key as keyof Settings]))throw new Error();
    if(value.camera && ![value.camera.position,value.camera.target].every(items=>Array.isArray(items)&&items.length===3&&items.every(item=>typeof item==='number'&&Number.isFinite(item))))throw new Error();
    setSettings(value.settings);if(value.camera)api.current?.restoreView(value.camera);setNotice('已读取保存的调校。');
  }catch{setNotice('无法读取调校，请检查存储或重新保存。');}};

  return <section className={`gltf-preview ${studio?'gltf-studio':''}`} aria-label={label}>
    <div className="gltf-viewport"><div ref={host} className="gltf-canvas"/>
      <div className="gltf-viewport-top"><span><i/>{clips.length?'实时动作预览':'实时 3D 预览'}</span><div className="gltf-view-buttons">{[['front','正面'],['side','侧面'],['perspective','透视']].map(([value,text])=><button key={value} disabled={!!status||!!failure} onClick={()=>api.current?.view(value)}>{text}</button>)}</div></div>
      <span className="gltf-orbit-hint">拖动旋转 · 滚轮缩放</span>
      {(status||failure)&&<p className="gltf-message" role={failure?'alert':'status'}>{failure||status}</p>}
    </div>
    <aside className="gltf-inspector" aria-label="预览调校">
      <header><div><span>PREVIEW STUDIO</span><h4>预览调校</h4></div><button onClick={()=>{setSettings({...defaults});api.current?.view('perspective');setNotice('已恢复默认预览。');}}>重置</button></header>
      {!!clips.length&&<fieldset disabled={!!status||!!failure}><legend>动作</legend><div className="gltf-clips">{clips.map(item=><button aria-pressed={clip===item.name} key={item.name} onClick={()=>api.current?.select(item.name)}>{names[item.name]??item.name}</button>)}</div>
        {range('speed','播放速度',.25,2,.05,'×')}{range('strength','动作强度',0,1,.05,'%')}
        <label className="gltf-check"><input type="checkbox" checked={settings.loop} onChange={event=>update('loop',event.target.checked)}/>循环播放</label>
      </fieldset>}
      <fieldset disabled={!!status||!!failure}><legend>画面</legend>{range('yaw','角色朝向',-180,180,5,'°')}{range('exposure','曝光',.3,2,.05,'')}{range('light','主光强度',0,6,.1,'')}
        <div className="gltf-backgrounds" aria-label="背景颜色">{[['#e8ebe7','浅灰'],['#252d35','深蓝'],['#dfd2be','暖沙']].map(([color,name])=><button key={color} aria-label={`${name}背景`} aria-pressed={settings.background===color} style={{background:color}} onClick={()=>update('background',color)}/>)}</div>
        <div className="gltf-switches"><label className="gltf-check"><input type="checkbox" checked={settings.grid} onChange={event=>update('grid',event.target.checked)}/>地面网格</label>{!!clips.length&&<label className="gltf-check"><input type="checkbox" checked={settings.skeleton} onChange={event=>update('skeleton',event.target.checked)}/>显示骨架</label>}</div>
      </fieldset>
      {studio&&<footer><div><button onClick={save}>保存调校</button><button onClick={restore}>读取已保存</button></div><p role="status">{notice||'仅调整预览效果，不改动模型与原始动画。'}</p></footer>}
    </aside>
    {!!clips.length&&<div className="gltf-transport"><button className="gltf-play" disabled={suspended} onClick={()=>api.current?.toggle()} aria-label={playing?'暂停动画':'播放动画'}>{playing?'Ⅱ':'▶'}</button>{studio?<strong>{names[clip]??clip}</strong>:<select aria-label="预览动画" value={clip} onChange={event=>api.current?.select(event.target.value)}>{clips.map(item=><option value={item.name} key={item.name}>{names[item.name]??item.name}</option>)}</select>}
      <input type="range" aria-label="动作进度" min={0} max={selected?.duration??1} step={.001} value={time} onChange={event=>api.current?.seek(Number(event.target.value))}/>
      <output>{time.toFixed(2)} / {(selected?.duration??0).toFixed(2)} s</output>
    </div>}
  </section>;
}
