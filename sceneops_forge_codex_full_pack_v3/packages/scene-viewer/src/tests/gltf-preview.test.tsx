import { act } from 'react';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { GltfPreview } from '../GltfPreview';
const runtime=createRequire(resolve('modules/character-animation/frontend/package.json'));
const {render,screen,fireEvent,cleanup}=runtime('@testing-library/react');
const state=vi.hoisted(()=>({model:null as any,renderer:null as any,frames:new Map<number,FrameRequestCallback>(),id:0}));
vi.mock('three',async importOriginal=>{
 const actual=await importOriginal<typeof import('three')>();
 class Renderer{
  domElement=document.createElement('canvas');shadowMap={enabled:false,type:0};toneMappingExposure=1;
  constructor(){state.renderer=this;}setPixelRatio(){}setSize(){}render(){}dispose(){}
 }
 return {...actual,WebGLRenderer:Renderer};
});
vi.mock('three/examples/jsm/loaders/GLTFLoader.js',()=>({GLTFLoader:class{load(_url:string,done:any){
 const model=new THREE.Group();model.name='Actor';model.add(new THREE.Mesh(new THREE.BoxGeometry(1,2,1),new THREE.MeshStandardMaterial()));state.model=model;
 const animations=['Idle','Walk','Run','Wave'].map(name=>new THREE.AnimationClip(name,1,[new THREE.VectorKeyframeTrack('Actor.position',[0,1],[0,0,0,1,0,0])]));
 queueMicrotask(()=>done({scene:model,animations}));
}}}));
vi.mock('three/examples/jsm/controls/OrbitControls.js',()=>({OrbitControls:class{
 target=new THREE.Vector3();addEventListener(){}update(){}dispose(){}
}}));
beforeEach(()=>{
 localStorage.clear();state.frames.clear();vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT',true);
 vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}});
 vi.stubGlobal('requestAnimationFrame',(fn:FrameRequestCallback)=>{const id=++state.id;state.frames.set(id,fn);return id;});
 vi.stubGlobal('cancelAnimationFrame',(id:number)=>state.frames.delete(id));
 Object.defineProperty(document,'hidden',{configurable:true,value:false});
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
async function mount(){let view:any;await act(async()=>{view=render(<GltfPreview url="/person.glb" label="角色预览" studio/>);});return view;}
it('plays Walk by default, scrubs a real animation mixer, and updates settings without reloading the model',async()=>{
 await mount();expect(screen.getByRole('button',{name:'走路'}).getAttribute('aria-pressed')).toBe('true');
 const model=state.model;
 fireEvent.change(screen.getByLabelText('动作进度'),{target:{value:'0.5'}});
 expect(screen.getByLabelText('播放动画')).toBeTruthy();expect(model.position.x).toBeCloseTo(.5);
 fireEvent.change(screen.getByLabelText('动作强度'),{target:{value:'0.5'}});expect(model.position.x).toBeCloseTo(.25);
 fireEvent.change(screen.getByLabelText('角色朝向'),{target:{value:'90'}});expect(model.rotation.y).toBeCloseTo(Math.PI/2);
 fireEvent.change(screen.getByLabelText('曝光'),{target:{value:'1.5'}});expect(state.renderer.toneMappingExposure).toBe(1.5);
 expect(state.model).toBe(model);
 fireEvent.click(screen.getByRole('button',{name:'保存调校'}));
 fireEvent.click(screen.getByRole('button',{name:'重置'}));expect(state.renderer.toneMappingExposure).toBe(1);
 fireEvent.click(screen.getByRole('button',{name:'读取已保存'}));expect(state.renderer.toneMappingExposure).toBe(1.5);
 fireEvent.click(screen.getByRole('button',{name:'跑步'}));expect(screen.getByRole('button',{name:'跑步'}).getAttribute('aria-pressed')).toBe('true');
 fireEvent.change(screen.getByLabelText('播放速度'),{target:{value:'2'}});
 const advance=(now:number)=>{const [id,callback]=[...state.frames.entries()][0];state.frames.delete(id);act(()=>callback(now));};
 advance(1000);advance(1250);expect(Number(screen.getByLabelText('动作进度').value)).toBeCloseTo(.5);
});
it('stops requesting frames when hidden, paused or unmounted',async()=>{
 const view=await mount();expect(state.frames.size).toBe(1);
 Object.defineProperty(document,'hidden',{configurable:true,value:true});fireEvent(document,new Event('visibilitychange'));expect(state.frames.size).toBe(0);
 Object.defineProperty(document,'hidden',{configurable:true,value:false});fireEvent(document,new Event('visibilitychange'));expect(state.frames.size).toBe(1);
 fireEvent.click(screen.getByLabelText('暂停动画'));expect(state.frames.size).toBe(0);
 fireEvent.click(screen.getByLabelText('播放动画'));expect(state.frames.size).toBe(1);
 view.unmount();expect(state.frames.size).toBe(0);
});
